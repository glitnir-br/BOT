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

SERVIDORES = (
    {"nome": "Glitnir Northbound - Server 1", "ip": "162.43.190.115", "porta": 2461},
    {"nome": "Glitnir Northbound - Server 2", "ip": "162.43.190.115", "porta": 2457},
)


class ServerStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.falhas_seguidas = 0
        self.status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()

    async def consultar_servidor(self, config):
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(
                    a2s.info, (config["ip"], config["porta"]), timeout=5
                ),
                timeout=10,
            )
            return {
                "online": True,
                "jogadores": info.player_count,
                "max_jogadores": info.max_players,
            }
        except Exception as erro:
            print(f'[Server Status] Erro ao consultar {config["nome"]}: {erro}')
            return {"online": False}

    def criar_painel(self, statuses):
        online = sum(status["online"] for status in statuses)
        if online == len(statuses):
            cor = discord.Color.green()
            resumo = "Todos os servidores est\u00e3o online"
        elif online == 0:
            cor = discord.Color.red()
            resumo = "Nenhum servidor est\u00e1 respondendo"
        else:
            cor = discord.Color.gold()
            resumo = "Opera\u00e7\u00e3o parcial"

        embed = discord.Embed(
            title="STATUS DOS SERVIDORES",
            description=(
                f"**{resumo}**\n"
                "Atualiza\u00e7\u00e3o autom\u00e1tica a cada minuto."
            ),
            color=cor,
        )

        for config, status in zip(SERVIDORES, statuses):
            if status["online"]:
                indicador = "\N{LARGE GREEN CIRCLE} ONLINE"
                detalhes = (
                    f"**{indicador}**\n"
                    f"\N{BUSTS IN SILHOUETTE} Jogadores: "
                    f'**{status["jogadores"]} / {status["max_jogadores"]}**\n'
                    f"\N{WORLD MAP} Bioma: **{WORLD_BIOME}**"
                )
            else:
                detalhes = (
                    "**\N{LARGE RED CIRCLE} OFFLINE**\n"
                    "O servidor n\u00e3o respondeu \u00e0 consulta."
                )

            embed.add_field(name=config["nome"], value=detalhes, inline=False)

        embed.set_footer(text="Glitnir | Status autom\u00e1tico")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @tasks.loop(seconds=INTERVALO_NORMAL)
    async def status_loop(self):
        statuses = await asyncio.gather(
            *(self.consultar_servidor(config) for config in SERVIDORES)
        )
        painel = self.criar_painel(statuses)

        houve_falha = any(not status["online"] for status in statuses)
        self.falhas_seguidas = self.falhas_seguidas + 1 if houve_falha else 0

        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            print(f"[Server Status] Canal {CHANNEL_ID} n\u00e3o encontrado.")
        elif MESSAGE_ID:
            try:
                mensagem = await channel.fetch_message(MESSAGE_ID)
                await mensagem.edit(embed=painel)
                print("[Server Status] Painel atualizado.")
            except discord.NotFound:
                print("[Server Status] Mensagem n\u00e3o encontrada.")
            except Exception as erro:
                print(f"[Server Status] Erro ao editar mensagem: {erro}")
        else:
            try:
                mensagem = await channel.send(embed=painel)
                print(f"[Server Status] Nova mensagem criada: {mensagem.id}")
            except Exception as erro:
                print(f"[Server Status] Erro ao criar mensagem: {erro}")

        novo_intervalo = (
            INTERVALO_COM_FALHA
            if self.falhas_seguidas >= FALHAS_PARA_BACKOFF
            else INTERVALO_NORMAL
        )
        if self.status_loop.seconds != novo_intervalo:
            self.status_loop.change_interval(seconds=novo_intervalo)

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))
