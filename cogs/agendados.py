import os
from datetime import datetime, timedelta

import discord
from discord import ui
from discord.ext import commands, tasks

import config
from utils import storage

DATA_FILE = "agendados.json"
PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "agendados_imagens")
INTERVALO_REPETICAO = {"diario": timedelta(days=1), "semanal": timedelta(days=7)}
PALAVRAS_REPETICAO = {"diario": "diario", "diário": "diario", "semanal": "semanal"}
NOMES_REPETICAO = {"diario": "todo dia", "semanal": "toda semana"}


class NovoAgendamentoModal(ui.Modal, title="Novo agendamento"):
    def __init__(self, cog, canal_id, repeticao):
        super().__init__()
        self.cog, self.canal_id, self.repeticao_escolhida = cog, canal_id, repeticao
        self.data = ui.TextInput(label="Data", placeholder="DD/MM/AAAA", max_length=10)
        self.hora = ui.TextInput(label="Hora", placeholder="HH:MM", max_length=5)
        self.texto = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, max_length=4000)
        for campo in (self.data, self.hora, self.texto): self.add_item(campo)

    async def on_submit(self, interaction):
        try:
            momento = datetime.strptime(f"{self.data.value.strip()} {self.hora.value.strip()}", "%d/%m/%Y %H:%M").replace(tzinfo=config.TZ_BRASILIA)
        except ValueError:
            await interaction.response.send_message("Data ou hora inválida. Use `DD/MM/AAAA` e `HH:MM`.", ephemeral=True); return
        if momento <= datetime.now(config.TZ_BRASILIA):
            await interaction.response.send_message("Escolha uma data e hora futuras.", ephemeral=True); return
        texto = self.texto.value.strip()
        if not texto:
            await interaction.response.send_message("A mensagem não pode ficar vazia.", ephemeral=True); return
        item = await self.cog.criar_agendamento(self.canal_id, momento, texto, self.repeticao_escolhida, interaction.user.id)
        await interaction.response.send_message(f"✅ Agendamento **ID {item['id']}** criado e enviado ao canal de avisos.", ephemeral=True)


class EscolherCanalAgendamentoView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=120)
        self.cog = cog
        self.add_item(self.EscolherCanal())

    class EscolherCanal(ui.ChannelSelect):
        def __init__(self):
            super().__init__(
                placeholder="Escolha o canal de publicação",
                channel_types=[discord.ChannelType.text, discord.ChannelType.news],
                min_values=1,
                max_values=1,
            )

        async def callback(self, interaction):
            await interaction.response.edit_message(
                content="Escolha a frequência do agendamento:",
                view=EscolherFrequenciaAgendamentoView(self.view.cog, self.values[0].id),
            )


class EscolherFrequenciaAgendamentoView(ui.View):
    def __init__(self, cog, canal_id):
        super().__init__(timeout=120)
        self.cog, self.canal_id = cog, canal_id
        self.add_item(self.EscolherFrequencia())

    class EscolherFrequencia(ui.Select):
        def __init__(self):
            super().__init__(
                placeholder="Escolha a frequência",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(label="Uma única vez", value="unica", emoji="1️⃣"),
                    discord.SelectOption(label="Diariamente", value="diario", emoji="🔁"),
                    discord.SelectOption(label="Semanalmente", value="semanal", emoji="📅"),
                ],
            )

        async def callback(self, interaction):
            repeticao = None if self.values[0] == "unica" else self.values[0]
            await interaction.response.send_modal(NovoAgendamentoModal(self.view.cog, self.view.canal_id, repeticao))


class AgendamentoPanelView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(label="Novo agendamento", emoji="➕", style=discord.ButtonStyle.success, custom_id="agendados:novo")
    async def novo(self, interaction, button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Apenas administradores podem criar agendamentos.", ephemeral=True); return
        await interaction.response.send_message("Escolha o canal onde a mensagem será publicada:", view=EscolherCanalAgendamentoView(self.cog), ephemeral=True)


class EditarAgendamentoModal(ui.Modal, title="Editar agendamento"):
    def __init__(self, cog, item):
        super().__init__()
        self.cog, self.item_id = cog, item["id"]
        momento = datetime.fromisoformat(item["data_hora"])
        self.hora = ui.TextInput(label="Hora", default=momento.strftime("%H:%M"), max_length=5)
        self.texto = ui.TextInput(label="Mensagem", default=item["texto"], style=discord.TextStyle.paragraph, max_length=4000)
        for campo in (self.hora, self.texto): self.add_item(campo)

    async def on_submit(self, interaction):
        item = self.cog.buscar_item(self.item_id)
        if not item:
            await interaction.response.send_message("Este agendamento não existe mais.", ephemeral=True); return
        try:
            hora = datetime.strptime(self.hora.value.strip(), "%H:%M").time()
            momento = datetime.fromisoformat(item["data_hora"]).replace(hour=hora.hour, minute=hora.minute)
        except ValueError:
            await interaction.response.send_message("Hora inválida. Use `HH:MM`.", ephemeral=True); return
        if momento <= datetime.now(config.TZ_BRASILIA):
            await interaction.response.send_message("Escolha uma data e hora futuras.", ephemeral=True); return
        texto = self.texto.value.strip()
        if not item or not texto:
            await interaction.response.send_message("O agendamento não existe mais ou a mensagem está vazia.", ephemeral=True); return
        item.update(data_hora=momento.isoformat(), texto=texto)
        self.cog._salvar(); await self.cog.atualizar_card(item)
        await interaction.response.send_message("✅ Agendamento atualizado.", ephemeral=True)


class AgendamentoCardView(ui.View):
    def __init__(self, cog, item_id):
        super().__init__(timeout=None)
        self.cog, self.item_id = cog, item_id
        self.editar.custom_id, self.cancelar.custom_id = f"agendados:editar:{item_id}", f"agendados:cancelar:{item_id}"

    async def _item_admin(self, interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Apenas administradores podem alterar agendamentos.", ephemeral=True); return None
        item = self.cog.buscar_item(self.item_id)
        if not item: await interaction.response.send_message("Este agendamento não existe mais.", ephemeral=True)
        return item

    @ui.button(label="Editar", emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="agendados:editar")
    async def editar(self, interaction, button):
        item = await self._item_admin(interaction)
        if item: await interaction.response.send_modal(EditarAgendamentoModal(self.cog, item))

    @ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.danger, custom_id="agendados:cancelar")
    async def cancelar(self, interaction, button):
        item = await self._item_admin(interaction)
        if item:
            await interaction.response.defer(ephemeral=True)
            await self.cog.cancelar_item(item, interaction.user)
            await interaction.followup.send("❌ Agendamento cancelado.", ephemeral=True)


class Agendados(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        dados = storage.load_json(DATA_FILE, default={"itens": [], "proximo_id": 1})
        self.itens, self.proximo_id = dados.get("itens", []), dados.get("proximo_id", 1)
        self.views = set(); os.makedirs(PASTA_IMAGENS, exist_ok=True)
        self.bot.add_view(AgendamentoPanelView(self))
        self.verificar_agendados.start()

    def cog_unload(self): self.verificar_agendados.cancel()
    def _salvar(self): storage.save_json(DATA_FILE, {"itens": self.itens, "proximo_id": self.proximo_id})
    def buscar_item(self, item_id): return next((x for x in self.itens if x["id"] == item_id), None)

    async def criar_agendamento(self, canal_id, momento, texto, repeticao, criado_por, imagem=None):
        item_id = self.proximo_id; self.proximo_id += 1
        item = {"id":item_id, "canal_id":canal_id, "data_hora":momento.isoformat(), "texto":texto, "imagem":imagem, "criado_por":criado_por, "repeticao":repeticao}
        self.itens.append(item); self._salvar()
        try: await self.criar_card(item)
        except Exception as erro: print(f"Erro ao criar card: {erro}")
        return item

    async def canal_avisos(self):
        canal = self.bot.get_channel(config.CANAL_AVISOS_ID) if config.CANAL_AVISOS_ID else None
        if not canal and config.CANAL_AVISOS_ID:
            try: canal = await self.bot.fetch_channel(config.CANAL_AVISOS_ID)
            except Exception as erro: print(f"Canal de avisos indisponível: {erro}")
        return canal

    def embed_card(self, item, status="agendado", detalhe=""):
        momento = datetime.fromisoformat(item["data_hora"])
        destino = self.bot.get_channel(item["canal_id"])
        titulo = {"agendado":"📅 Mensagem agendada", "cancelado":"❌ Agendamento cancelado", "publicado":"✅ Agendamento publicado"}[status]
        cor = {"agendado":config.COR_GLITNIR, "cancelado":discord.Color.red(), "publicado":discord.Color.green()}[status]
        embed = discord.Embed(title=titulo, color=cor)
        embed.add_field(name="Quando", value=momento.strftime("%d/%m/%Y às %H:%M"), inline=True)
        embed.add_field(name="Destino", value=destino.mention if destino else f"ID `{item['canal_id']}`", inline=True)
        embed.add_field(name="Repetição", value=NOMES_REPETICAO.get(item.get("repeticao"), "não se repete"), inline=True)
        embed.add_field(name="Mensagem", value=item["texto"][:1024], inline=False)
        if detalhe: embed.add_field(name="Status", value=detalhe, inline=False)
        embed.set_footer(text=f"Agendamento ID {item['id']} • Criado por {item.get('criado_por', 'desconhecido')}")
        return embed

    def registrar_view(self, item):
        mensagem_id = item.get("aviso_message_id")
        if mensagem_id and mensagem_id not in self.views:
            self.bot.add_view(AgendamentoCardView(self, item["id"]), message_id=mensagem_id); self.views.add(mensagem_id)

    async def criar_card(self, item):
        canal = await self.canal_avisos()
        if not canal: return
        mensagem = await canal.send(embed=self.embed_card(item), view=AgendamentoCardView(self, item["id"]))
        item.update(aviso_channel_id=canal.id, aviso_message_id=mensagem.id)
        self._salvar(); self.registrar_view(item)

    async def atualizar_card(self, item, status="agendado", detalhe=""):
        canal_id, mensagem_id = item.get("aviso_channel_id"), item.get("aviso_message_id")
        canal = self.bot.get_channel(canal_id) if canal_id else None
        if canal_id and not canal:
            try: canal = await self.bot.fetch_channel(canal_id)
            except Exception: canal = None
        if canal and mensagem_id:
            try:
                mensagem = await canal.fetch_message(mensagem_id)
                await mensagem.edit(embed=self.embed_card(item, status, detalhe), view=AgendamentoCardView(self, item["id"]) if status == "agendado" else None)
                if status == "agendado": self.registrar_view(item)
                return
            except Exception as erro: print(f"Erro ao atualizar card {item['id']}: {erro}")
        if status == "agendado": await self.criar_card(item)

    async def sincronizar_cards(self):
        for item in self.itens:
            if item.get("aviso_message_id"): self.registrar_view(item)
            else:
                try: await self.criar_card(item)
                except Exception as erro: print(f"Erro ao criar card {item['id']}: {erro}")

    async def cancelar_item(self, item, usuario=None):
        self.itens.remove(item); self._salvar()
        if item.get("imagem") and os.path.exists(item["imagem"]):
            try: os.remove(item["imagem"])
            except Exception as erro: print(f"Erro ao apagar imagem: {erro}")
        await self.atualizar_card(item, "cancelado", f"Cancelado por {usuario.mention}" if usuario else "Cancelado")

    @commands.command(name="agendar")
    @commands.has_permissions(administrator=True)
    async def agendar(self, ctx, data, hora, *, texto):
        try: momento = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M").replace(tzinfo=config.TZ_BRASILIA)
        except ValueError:
            await ctx.send("Formato inválido! Use: `!agendar DD/MM/AAAA HH:MM Sua mensagem aqui`.", delete_after=15); return
        primeira = texto.split(" ", 1)[0].lower(); repeticao = PALAVRAS_REPETICAO.get(primeira)
        if repeticao:
            partes = texto.split(" ", 1)
            if len(partes) < 2 or not partes[1].strip():
                await ctx.send("Faltou o texto da mensagem.", delete_after=10); return
            texto = partes[1].strip()
        if momento <= datetime.now(config.TZ_BRASILIA):
            await ctx.send("Essa data/hora já passou!", delete_after=10); return
        item_id = self.proximo_id; imagem = None
        if ctx.message.attachments:
            anexo = ctx.message.attachments[0]
            if anexo.content_type and anexo.content_type.startswith("image/"):
                imagem = os.path.join(PASTA_IMAGENS, f"{item_id}{os.path.splitext(anexo.filename)[1] or '.png'}")
                await anexo.save(imagem)
        item = await self.criar_agendamento(ctx.channel.id, momento, texto, repeticao, ctx.author.id, imagem)
        await ctx.send(f"✅ Agendamento **ID {item['id']}** criado. O card foi enviado ao canal de avisos.")
        try: await ctx.message.delete()
        except Exception: pass

    @commands.command(name="painel_agendamentos")
    @commands.has_permissions(administrator=True)
    async def painel_agendamentos(self, ctx):
        """Publica o painel de criação de agendamentos no canal #bot-manager."""
        if not config.CANAL_BOT_MANAGER_ID:
            await ctx.send("Configure `CANAL_BOT_MANAGER_ID` no .env antes de publicar o painel.", delete_after=15); return
        canal = self.bot.get_channel(config.CANAL_BOT_MANAGER_ID)
        if not canal:
            try: canal = await self.bot.fetch_channel(config.CANAL_BOT_MANAGER_ID)
            except Exception:
                await ctx.send("Não encontrei o canal bot-manager configurado.", delete_after=15); return
        embed = discord.Embed(
            title="📅 Gerenciador de agendamentos",
            description="Clique no botão abaixo para agendar uma mensagem. Você escolherá o canal, data, hora, frequência e texto de forma privada.",
            color=config.COR_GLITNIR,
        )
        await canal.send(embed=embed, view=AgendamentoPanelView(self))
        await ctx.send(f"✅ Painel publicado em {canal.mention}.", delete_after=10)

    @commands.command(name="agendados")
    @commands.has_permissions(administrator=True)
    async def listar_agendados(self, ctx):
        if not self.itens:
            await ctx.send("Nenhum post agendado no momento.", delete_after=10); return
        embed = discord.Embed(title="📅 Posts Agendados", color=config.COR_GLITNIR)
        for item in sorted(self.itens, key=lambda x:x["data_hora"]):
            momento = datetime.fromisoformat(item["data_hora"]); canal = self.bot.get_channel(item["canal_id"])
            preview = item["texto"][:80] + ("..." if len(item["texto"]) > 80 else "")
            embed.add_field(name=f"ID {item['id']} — {momento.strftime('%d/%m/%Y às %H:%M')}", value=f"{canal.mention if canal else 'canal não encontrado'}\n{preview}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="cancelar_agendamento")
    @commands.has_permissions(administrator=True)
    async def cancelar_agendamento(self, ctx, item_id:int):
        item = self.buscar_item(item_id)
        if not item:
            await ctx.send(f"Não encontrei nenhum agendamento com ID {item_id}.", delete_after=10); return
        await self.cancelar_item(item, ctx.author); await ctx.send(f"❌ Agendamento **ID {item_id}** cancelado.", delete_after=10)

    @tasks.loop(minutes=1)
    async def verificar_agendados(self):
        agora, pendentes, mudou = datetime.now(config.TZ_BRASILIA), [], False
        for item in self.itens:
            momento = datetime.fromisoformat(item["data_hora"])
            if agora < momento: pendentes.append(item); continue
            publicado = await self._publicar(item); mudou = True; repeticao = item.get("repeticao")
            if repeticao in INTERVALO_REPETICAO:
                item["data_hora"] = (momento + INTERVALO_REPETICAO[repeticao]).isoformat(); pendentes.append(item)
                await self.atualizar_card(item, detalhe="Mensagem publicada; próxima execução atualizada.")
            else:
                if item.get("imagem") and os.path.exists(item["imagem"]):
                    try: os.remove(item["imagem"])
                    except Exception: pass
                await self.atualizar_card(item, "publicado" if publicado else "cancelado", "Mensagem publicada." if publicado else "A publicação falhou.")
        if mudou: self.itens = pendentes; self._salvar()

    async def _publicar(self, item):
        canal = self.bot.get_channel(item["canal_id"])
        if not canal: return False
        embed = discord.Embed(description=item["texto"], color=config.COR_GLITNIR); arquivo = None
        if item.get("imagem") and os.path.exists(item["imagem"]):
            nome = os.path.basename(item["imagem"]); arquivo = discord.File(item["imagem"], filename=nome); embed.set_image(url=f"attachment://{nome}")
        try:
            await canal.send(embed=embed, file=arquivo) if arquivo else await canal.send(embed=embed)
            return True
        except Exception as erro: print(f"Erro ao publicar {item['id']}: {erro}"); return False

    @verificar_agendados.before_loop
    async def antes(self):
        await self.bot.wait_until_ready(); await self.sincronizar_cards()


async def setup(bot):
    await bot.add_cog(Agendados(bot))
