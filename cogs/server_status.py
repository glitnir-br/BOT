import asyncio
import a2s
import discord

from discord.ext import commands, tasks


SERVER_IP = "177.54.147.114"
QUERY_PORT = 24667

# ID do canal onde ficará a mensagem de status
CHANNEL_ID = 1543025024645210303

# ID da mensagem já existente
# Se deixar 0, o bot cria uma nova e mostra o ID no terminal
MESSAGE_ID = 1543039966890823694

WORLD_BIOME = "Mistlands"

class ServerStatus(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()

    # =========================
    # CONSULTA VALHEIM
    # =========================

    async def consultar_servidor(self):

        try:

            info = await asyncio.to_thread(
                a2s.info,
                (SERVER_IP, QUERY_PORT),
                timeout=5
            )

            return {
                "online": True,
                "nome": info.server_name,
                "jogadores": info.player_count,
                "max_jogadores": info.max_players,
            }

        except Exception as erro:

            print(
                f"[Server Status] Erro ao consultar servidor: {erro}"
            )

            return {
                "online": False
            }

    # =========================
    # EMBED
    # =========================

    def criar_embed(self, status):

        if status["online"]:

            embed = discord.Embed(
                title="⚔️ GLITNIR",
                description="🟢 **Servidor Online**",
                color=discord.Color.green()
            )

            embed.add_field(
                name="👥 Jogadores",
                value=(
                    f'**{status["jogadores"]} / '
                    f'{status["max_jogadores"]}**'
                ),
                inline=True
            )

            embed.add_field(
                name="🗺️ Bioma atual",
                value=f"**{WORLD_BIOME}**",
                inline=True
            )

        else:

            embed = discord.Embed(
                title="⚔️ GLITNIR",
                description="🔴 **Servidor Offline**",
                color=discord.Color.red()
            )

        embed.set_footer(
            text="Glitnir • Status automático"
        )

        embed.timestamp = discord.utils.utcnow()

        return embed

    # =========================
    # LOOP
    # =========================

    @tasks.loop(seconds=60)
    async def status_loop(self):

        status = await self.consultar_servidor()

        embed = self.criar_embed(status)

        channel = self.bot.get_channel(CHANNEL_ID)

        if not channel:

            print(
                f"[Server Status] Canal {CHANNEL_ID} não encontrado."
            )
            return

        # Se já temos uma mensagem fixa
        if MESSAGE_ID:

            try:

                mensagem = await channel.fetch_message(
                    MESSAGE_ID
                )

                await mensagem.edit(
                    embed=embed
                )

                print(
                    "[Server Status] Mensagem atualizada."
                )

                return

            except discord.NotFound:

                print(
                    "[Server Status] Mensagem não encontrada."
                )

            except Exception as erro:

                print(
                    f"[Server Status] Erro ao editar mensagem: {erro}"
                )

                return

        # Cria a mensagem caso ainda não exista
        try:

            mensagem = await channel.send(
                embed=embed
            )

            print("")
            print(
                "[Server Status] NOVA MENSAGEM CRIADA"
            )
            print(
                f"[Server Status] MESSAGE_ID = {mensagem.id}"
            )
            print("")

        except Exception as erro:

            print(
                f"[Server Status] Erro ao criar mensagem: {erro}"
            )

    @status_loop.before_loop
    async def before_status_loop(self):

        await self.bot.wait_until_ready()


async def setup(bot):

    await bot.add_cog(
        ServerStatus(bot)
    )