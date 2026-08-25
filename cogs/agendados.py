import os
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

import config
from utils import storage

DATA_FILE = "agendados.json"
PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "agendados_imagens")

INTERVALO_REPETICAO = {
    "diario": timedelta(days=1),
    "semanal": timedelta(days=7),
}

PALAVRAS_REPETICAO = {
    "diario": "diario",
    "diário": "diario",
    "semanal": "semanal",
}


class Agendados(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        dados = storage.load_json(DATA_FILE, default={"itens": [], "proximo_id": 1})
        self.itens = dados.get("itens", [])
        self.proximo_id = dados.get("proximo_id", 1)
        os.makedirs(PASTA_IMAGENS, exist_ok=True)
        self.verificar_agendados.start()

    def cog_unload(self):
        self.verificar_agendados.cancel()

    def _salvar(self):
        storage.save_json(DATA_FILE, {"itens": self.itens, "proximo_id": self.proximo_id})

    @commands.command(name="agendar")
    @commands.has_permissions(administrator=True)
    async def agendar(self, ctx: commands.Context, data: str, hora: str, *, texto: str):
        """Agenda um post (texto + imagem opcional) pra uma data/hora específica.
        Ex: !agendar 25/12/2026 19:00 Feliz Natal, guerreiros! (anexa uma imagem se quiser)
        Pra repetir, coloque "diario" ou "semanal" logo antes do texto:
        Ex: !agendar 18/08/2026 08:00 diario Bom dia, Glitnir!"""
        try:
            momento = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M").replace(tzinfo=config.TZ_BRASILIA)
        except ValueError:
            await ctx.send(
                "Formato inválido! Use: `!agendar DD/MM/AAAA HH:MM Sua mensagem aqui`\n"
                "Ex: `!agendar 25/12/2026 19:00 Feliz Natal, guerreiros!`\n"
                "Pra repetir: `!agendar 18/08/2026 08:00 diario Sua mensagem aqui` "
                "(ou `semanal` no lugar de `diario`)",
                delete_after=15,
            )
            return

        primeira_palavra = texto.split(" ", 1)[0].lower()
        repeticao = PALAVRAS_REPETICAO.get(primeira_palavra)
        if repeticao:
            resto = texto.split(" ", 1)
            if len(resto) < 2 or not resto[1].strip():
                await ctx.send(f"Faltou o texto da mensagem depois de \"{primeira_palavra}\"!", delete_after=10)
                return
            texto = resto[1].strip()

        agora = datetime.now(config.TZ_BRASILIA)
        if momento <= agora:
            await ctx.send("Essa data/hora já passou! Escolhe um momento no futuro.", delete_after=10)
            return

        item_id = self.proximo_id
        self.proximo_id += 1

        caminho_imagem = None
        if ctx.message.attachments:
            anexo = ctx.message.attachments[0]
            if anexo.content_type and anexo.content_type.startswith("image/"):
                extensao = os.path.splitext(anexo.filename)[1] or ".png"
                caminho_imagem = os.path.join(PASTA_IMAGENS, f"{item_id}{extensao}")
                await anexo.save(caminho_imagem)

        self.itens.append({
            "id": item_id,
            "canal_id": ctx.channel.id,
            "data_hora": momento.isoformat(),
            "texto": texto,
            "imagem": caminho_imagem,
            "criado_por": ctx.author.id,
            "repeticao": repeticao,
        })
        self._salvar()

        nomes_repeticao = {"diario": "todo dia", "semanal": "toda semana"}
        repeticao_texto = f"\n🔁 Repete {nomes_repeticao[repeticao]}, nesse mesmo horário." if repeticao else ""
        embed = discord.Embed(
            description=(
                f"✅ Agendado com sucesso! **ID: {item_id}**\n\n"
                f"📅 {momento.strftime('%d/%m/%Y às %H:%M')}\n"
                f"📍 {ctx.channel.mention}"
                f"{repeticao_texto}\n\n"
                f"Pra cancelar: `!cancelar_agendamento {item_id}`"
            ),
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!agendar): {e}")

    @commands.command(name="agendados")
    @commands.has_permissions(administrator=True)
    async def listar_agendados(self, ctx: commands.Context):
        """Lista todos os posts agendados que ainda não foram enviados."""
        if not self.itens:
            await ctx.send("Nenhum post agendado no momento.", delete_after=10)
            return

        embed = discord.Embed(title="📅 Posts Agendados", color=config.COR_GLITNIR)
        for item in sorted(self.itens, key=lambda i: i["data_hora"]):
            momento = datetime.fromisoformat(item["data_hora"])
            canal = self.bot.get_channel(item["canal_id"])
            canal_texto = canal.mention if canal else "canal não encontrado"
            preview = item["texto"][:80] + ("..." if len(item["texto"]) > 80 else "")
            repete = f" 🔁 ({item['repeticao']})" if item.get("repeticao") else ""
            embed.add_field(
                name=f"ID {item['id']} — {momento.strftime('%d/%m/%Y às %H:%M')}{repete}",
                value=f"{canal_texto}\n{preview}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.command(name="cancelar_agendamento")
    @commands.has_permissions(administrator=True)
    async def cancelar_agendamento(self, ctx: commands.Context, item_id: int):
        """Cancela um post agendado pelo ID (veja os IDs com !agendados)."""
        item = next((i for i in self.itens if i["id"] == item_id), None)
        if not item:
            await ctx.send(f"Não encontrei nenhum agendamento com ID {item_id}.", delete_after=10)
            return

        self.itens.remove(item)
        self._salvar()

        if item.get("imagem") and os.path.exists(item["imagem"]):
            try:
                os.remove(item["imagem"])
            except Exception as e:
                print(f"Erro ao apagar imagem do agendamento cancelado: {e}")

        await ctx.send(f"❌ Agendamento **ID {item_id}** cancelado.", delete_after=10)

    @tasks.loop(minutes=1)
    async def verificar_agendados(self):
        agora = datetime.now(config.TZ_BRASILIA)
        pendentes = []
        mudou = False

        for item in self.itens:
            momento = datetime.fromisoformat(item["data_hora"])
            if agora >= momento:
                await self._publicar(item)
                mudou = True

                repeticao = item.get("repeticao")
                if repeticao and repeticao in INTERVALO_REPETICAO:
                    nova_data = momento + INTERVALO_REPETICAO[repeticao]
                    item["data_hora"] = nova_data.isoformat()
                    pendentes.append(item)
                else:
                    caminho_imagem = item.get("imagem")
                    if caminho_imagem and os.path.exists(caminho_imagem):
                        try:
                            os.remove(caminho_imagem)
                        except Exception as e:
                            print(f"Erro ao limpar imagem do agendamento {item['id']}: {e}")
            else:
                pendentes.append(item)

        if mudou:
            self.itens = pendentes
            self._salvar()

    async def _publicar(self, item: dict):
        canal = self.bot.get_channel(item["canal_id"])
        if not canal:
            print(f"Canal do agendamento {item['id']} não encontrado, cancelando envio.")
            return

        embed = discord.Embed(description=item["texto"], color=config.COR_GLITNIR)

        arquivo = None
        caminho_imagem = item.get("imagem")
        if caminho_imagem and os.path.exists(caminho_imagem):
            nome_arquivo = os.path.basename(caminho_imagem)
            arquivo = discord.File(caminho_imagem, filename=nome_arquivo)
            embed.set_image(url=f"attachment://{nome_arquivo}")

        try:
            if arquivo:
                await canal.send(embed=embed, file=arquivo)
            else:
                await canal.send(embed=embed)
        except Exception as e:
            print(f"Erro ao publicar agendamento {item['id']}: {e}")

    @verificar_agendados.before_loop
    async def before_verificar_agendados(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Agendados(bot))