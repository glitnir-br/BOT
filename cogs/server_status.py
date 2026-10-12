import asyncio
import os

import a2s
import discord
from dotenv import load_dotenv
from discord.ext import commands, tasks

load_dotenv()

CHANNEL_ID = 1543025024645210303
MESSAGE_ID = 1543039966890823694
INTERVALO_NORMAL = 60
INTERVALO_COM_FALHA = 300
FALHAS_PARA_BACKOFF = 5
WORLD_BIOME = os.getenv("WORLD_BIOME", "Prado")


def servidor(*, nome, ip, porta):
    return {
        "nome": nome,
        "ip": ip,
        "porta": porta,
    }


SERVIDORES = (
    servidor(nome="Glitnir Northbound — Server 1", ip="162.43.190.115", porta=2461),
    servidor(nome="Glitnir Northbound — Server 2", ip="162.43.190.115", porta=2457),
)


class ServerStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.falhas_seguidas = 0
        self.status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()

    async def consultar_servidor(self, config):
        if not config["ip"]:
            return {"online": False, "configurado": False}
        try:
            info = await asyncio.wait_for(asyncio.to_thread(a2s.info, (config["ip"], config["porta"]), timeout=5), timeout=10)
            return {"online": True, "configurado": True, "jogadores": info.player_count, "max_jogadores": info.max_players}
        except Exception as erro:
            print(f'[Server Status] Erro ao consultar {config["nome"]}: {erro}')
            return {"online": False, "configurado": True}

    def criar_embed(self, config, status):
        nome = config["nome"]
        if not status["configurado"]:
            embed = discord.Embed(title=f"⚔️ {nome}", description="⚪ **Servidor não configurado**", color=discord.Color.light_grey())
        elif status["online"]:
            embed = discord.Embed(title=f"⚔️ {nome}", description="🟢 **Servidor Online**", color=discord.Color.green())
            embed.add_field(name="👥 Jogadores", value=f'**{status["jogadores"]} / {status["max_jogadores"]}**', inline=True)
            embed.add_field(name="🗺️ Bioma atual", value=f"**{WORLD_BIOME}**", inline=True)
        else:
            embed = discord.Embed(title=f"⚔️ {nome}", description="🔴 **Servidor Offline**", color=discord.Color.red())
        embed.set_footer(text="Glitnir • Status automático")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @tasks.loop(seconds=INTERVALO_NORMAL)
    async def status_loop(self):
        statuses = await asyncio.gather(*(self.consultar_servidor(config) for config in SERVIDORES))
        embeds = [self.criar_embed(config, status) for config, status in zip(SERVIDORES, statuses)]
        houve_falha = any(status["configurado"] and not status["online"] for status in statuses)
        self.falhas_seguidas = self.falhas_seguidas + 1 if houve_falha else 0

        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"[Server Status] Canal {CHANNEL_ID} não encontrado.")
        elif MESSAGE_ID:
            try:
                mensagem = await channel.fetch_message(MESSAGE_ID)
                await mensagem.edit(embeds=embeds)
                print("[Server Status] Mensagens atualizadas.")
            except discord.NotFound:
                print("[Server Status] Mensagem não encontrada.")
            except Exception as erro:
                print(f"[Server Status] Erro ao editar mensagem: {erro}")
        else:
            try:
                mensagem = await channel.send(embeds=embeds)
                print(f"[Server Status] NOVA MENSAGEM CRIADA: MESSAGE_ID = {mensagem.id}")
            except Exception as erro:
                print(f"[Server Status] Erro ao criar mensagem: {erro}")

        novo_intervalo = INTERVALO_COM_FALHA if self.falhas_seguidas >= FALHAS_PARA_BACKOFF else INTERVALO_NORMAL
        if self.status_loop.seconds != novo_intervalo:
            print(f"[Server Status] Ajustando intervalo para {novo_intervalo}s.")
            self.status_loop.change_interval(seconds=novo_intervalo)

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))
