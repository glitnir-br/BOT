import asyncio
import re
from types import SimpleNamespace

import discord
from discord.ext import commands

import config
from utils import storage

DATA_FILE = "guildas.json"


class FormularioGuilda(discord.ui.Modal, title="Criar guilda"):
    nome = discord.ui.TextInput(label="Nome da guilda", max_length=80)
    icone = discord.ui.TextInput(label="Ícone do chat", placeholder="Exemplo: ⚔️", max_length=20)

    async def on_submit(self, interaction):
        nome = str(self.nome).strip()
        icone = str(self.icone).strip()
        if not nome or not icone or re.search(r"[\r\n]", nome + icone):
            await interaction.response.send_message("Informe um nome e um ícone válidos.", ephemeral=True)
            return
        nome_final = f"{icone} {nome}"
        if len(nome_final) > 100:
            await interaction.response.send_message("O nome completo, incluindo o ícone, deve ter no máximo 100 caracteres.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Criar o cargo e o canal **{discord.utils.escape_markdown(nome_final)}**?",
            view=ConfirmarCriacao(interaction.user.id, nome_final), ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ConfirmarCriacao(discord.ui.View):
    def __init__(self, autor_id, nome):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.nome = nome
        self.usado = False

    @discord.ui.button(label="Criar guilda", style=discord.ButtonStyle.success)
    async def criar(self, interaction, button):
        if interaction.user.id != self.autor_id or self.usado:
            await interaction.response.send_message("Esta confirmação não está disponível.", ephemeral=True)
            return
        self.usado = True
        self.stop()
        await interaction.response.edit_message(content="Criando sua guilda...", view=None)
        cog = interaction.client.get_cog("Guildas")
        if not cog:
            await interaction.followup.send("O sistema de guildas está indisponível.", ephemeral=True)
            return
        await cog.criar(interaction, self.nome)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Esta confirmação pertence a outro usuário.", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(content="Criação cancelada.", view=None)


class PainelGuildas(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Criar chat de guilda", emoji="🛡️", style=discord.ButtonStyle.primary, custom_id="guildas:criar")
    async def criar(self, interaction, button):
        await interaction.response.send_modal(FormularioGuilda())


class EscolherMembro(discord.ui.UserSelect):
    def __init__(self, acao):
        super().__init__(placeholder="Selecione um membro do Discord", min_values=1, max_values=1)
        self.acao = acao

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Guildas")
        if not cog:
            await interaction.response.send_message("Sistema de guildas indisponível.", ephemeral=True)
            return
        await cog.alterar_membro(interaction, self.values[0], self.acao)


class EscolhaView(discord.ui.View):
    def __init__(self, acao):
        super().__init__(timeout=60)
        self.add_item(EscolherMembro(acao))


class ControlesGuilda(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def escolher(self, interaction, acao):
        cog = interaction.client.get_cog("Guildas")
        if not cog or not cog.eh_lider(interaction):
            await interaction.response.send_message("Somente o líder desta guilda pode usar este controle.", ephemeral=True)
            return
        await interaction.response.send_message("Selecione o membro:", view=EscolhaView(acao), ephemeral=True)

    @discord.ui.button(label="Adicionar membro", style=discord.ButtonStyle.success, custom_id="guildas:adicionar")
    async def adicionar(self, interaction, button):
        await self.escolher(interaction, "adicionar")

    @discord.ui.button(label="Remover membro", style=discord.ButtonStyle.danger, custom_id="guildas:remover")
    async def remover(self, interaction, button):
        await self.escolher(interaction, "remover")

    @discord.ui.button(label="Selecionar vice-líder", style=discord.ButtonStyle.primary, custom_id="guildas:vice")
    async def vice(self, interaction, button):
        await self.escolher(interaction, "vice")


class Guildas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dados = storage.load_json(DATA_FILE, default={})
        self.lock = asyncio.Lock()

    def salvar(self):
        storage.save_json(DATA_FILE, self.dados)

    async def cog_load(self):
        self.bot.add_view(PainelGuildas())
        self.bot.add_view(ControlesGuilda())

    @commands.Cog.listener()
    async def on_ready(self):
        # Reconcilia saídas ocorridas enquanto o bot estava desligado.
        for dados in list(self.dados.values()):
            guild = self.bot.get_guild(dados["guild_id"])
            lider = dados.get("lider")
            if not guild or not lider:
                continue
            try:
                await guild.fetch_member(lider)
            except discord.NotFound:
                await self.on_member_remove(SimpleNamespace(guild=guild, id=lider))
            except discord.HTTPException as erro:
                print(f"[Guildas] Não foi possível verificar o líder {lider}: {erro}")

    def eh_lider(self, interaction):
        registro = self.dados.get(str(interaction.channel_id))
        return bool(registro and registro["guild_id"] == interaction.guild_id and registro.get("lider") == interaction.user.id)

    async def criar(self, interaction, nome):
        guild = interaction.guild
        categoria = guild.get_channel(config.CATEGORIA_GUILDAS_ID)
        if not isinstance(categoria, discord.CategoryChannel):
            await interaction.followup.send("Categoria de guildas não configurada. Avise a equipe.", ephemeral=True)
            return
        async with self.lock:
            if any(d["guild_id"] == guild.id and d.get("lider") == interaction.user.id for d in self.dados.values()):
                await interaction.followup.send("Você já é líder de uma guilda.", ephemeral=True)
                return
            cargo = canal = None
            try:
                cargo = await guild.create_role(name=nome, reason=f"Guilda solicitada por {interaction.user.id}")
                await interaction.user.add_roles(cargo, reason="Líder da guilda")
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
                    cargo: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=True, read_message_history=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=True, read_message_history=True, manage_channels=True),
                }
                canal = await guild.create_voice_channel(name=nome, category=categoria, overwrites=overwrites, reason="Canal de guilda")
                self.dados[str(canal.id)] = {"guild_id": guild.id, "cargo": cargo.id, "lider": interaction.user.id, "vice": None}
                self.salvar()
                await canal.send("🛡️ **Gestão da guilda**\nSomente o líder pode gerenciar os membros e selecionar um vice-líder.", view=ControlesGuilda())
            except (discord.HTTPException, OSError) as erro:
                if canal:
                    self.dados.pop(str(canal.id), None)
                    try:
                        self.salvar()
                        await canal.delete(reason="Falha na criação da guilda")
                    except (discord.HTTPException, OSError):
                        pass
                if cargo:
                    try:
                        await cargo.delete(reason="Falha na criação da guilda")
                    except discord.HTTPException:
                        pass
                print(f"[Guildas] Erro ao criar guilda: {erro}")
                await interaction.followup.send("Não foi possível criar a guilda. Avise a equipe para verificar as permissões.", ephemeral=True)
                return
        await interaction.followup.send(f"Guilda criada: {canal.mention}", ephemeral=True)

    async def alterar_membro(self, interaction, usuario, acao):
        if not self.eh_lider(interaction):
            await interaction.response.send_message("Somente o líder desta guilda pode usar este controle.", ephemeral=True)
            return
        dados = self.dados[str(interaction.channel_id)]
        cargo = interaction.guild.get_role(dados["cargo"])
        membro = interaction.guild.get_member(usuario.id)
        if not membro:
            try:
                membro = await interaction.guild.fetch_member(usuario.id)
            except discord.HTTPException:
                await interaction.response.send_message("Membro não encontrado no servidor.", ephemeral=True)
                return
        if not cargo or membro.bot or membro.id == dados["lider"]:
            await interaction.response.send_message("Não é possível alterar este membro ou cargo.", ephemeral=True)
            return
        if acao in ("remover", "vice") and cargo not in membro.roles:
            await interaction.response.send_message("Este jogador não é membro da guilda.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            if acao == "adicionar":
                await membro.add_roles(cargo, reason=f"Adicionado pelo líder {interaction.user.id}")
                mensagem = "Membro adicionado."
            elif acao == "remover":
                await membro.remove_roles(cargo, reason=f"Removido pelo líder {interaction.user.id}")
                if dados.get("vice") == membro.id:
                    dados["vice"] = None
                    self.salvar()
                mensagem = "Membro removido."
            else:
                dados["vice"] = membro.id
                self.salvar()
                mensagem = "Vice-líder selecionado."
            await interaction.followup.send(mensagem, ephemeral=True)
        except (discord.HTTPException, OSError) as erro:
            print(f"[Guildas] Erro ao atualizar membro: {erro}")
            await interaction.followup.send("Não foi possível concluir a operação. Avise a equipe.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        async with self.lock:
            for canal_id, dados in self.dados.items():
                if dados["guild_id"] != member.guild.id:
                    continue
                if dados.get("lider") == member.id:
                    vice = member.guild.get_member(dados.get("vice")) if dados.get("vice") else None
                    cargo = member.guild.get_role(dados["cargo"])
                    if vice is None and dados.get("vice"):
                        try:
                            vice = await member.guild.fetch_member(dados["vice"])
                        except discord.HTTPException:
                            pass
                    dados["lider"] = vice.id if vice and cargo and cargo in vice.roles else None
                    dados["vice"] = None
                    self.salvar()
                    canal = member.guild.get_channel(int(canal_id))
                    if canal:
                        try:
                            texto = f"<@{vice.id}> agora é o líder da guilda." if dados["lider"] else "O líder saiu e não há vice-líder disponível. Um administrador precisa definir um novo líder."
                            await canal.send(texto)
                        except discord.HTTPException:
                            pass
                elif dados.get("vice") == member.id:
                    dados["vice"] = None
                    self.salvar()

    @commands.command(name="guilda_lider")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def definir_lider(self, ctx, membro: discord.Member):
        dados = self.dados.get(str(ctx.channel.id))
        if not dados or dados["guild_id"] != ctx.guild.id:
            await ctx.send("Use este comando no chat do canal de voz da guilda.")
            return
        cargo = ctx.guild.get_role(dados["cargo"])
        if not cargo or cargo not in membro.roles or membro.bot:
            await ctx.send("O novo líder precisa ser membro da guilda.")
            return
        dados["lider"] = membro.id
        if dados.get("vice") == membro.id:
            dados["vice"] = None
        self.salvar()
        await ctx.send(f"{membro.mention} agora é o líder da guilda.")


async def setup(bot):
    await bot.add_cog(Guildas(bot))
