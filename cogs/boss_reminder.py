import os
from datetime import datetime

import discord
from discord.ext import commands, tasks

import config
from utils import storage

DATA_FILE = "boss_reminder.json"

# Caminho da imagem do aviso — coloque um arquivo em assets/boss.png (ou mude o nome aqui)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
IMAGEM_BOSS = os.path.join(ASSETS_DIR, "boss.png")

COR_VALHEIM = discord.Color.from_rgb(94, 129, 87)  # verde musgo, clima Valheim


def montar_embed_boss() -> tuple[discord.Embed, discord.File | None]:
    embed = discord.Embed(
        title="🚨⚔️ O NOVO BOSS FOI LIBERADO! ⚔️🚨",
        description=(
            "Ôia só, cês tão moscando aí? 👀\n\n"
            "As pedra antiga tremeu, as runa acendeu e uma criatura braba saiu das "
            "profundezas. Eu num chegava nem perto dela... mas ocês parecem gostar "
            "de um perigo, né? 🌲💀\n\n"
            "Então junta o clã, afia essas arma enferrujada, enche o bucho de "
            "hidromel e vai pra peleja!\n\n"
            "🏹 O novo Boss já tá esperando ocês!\n"
            "⚔️ Mostra que ocê é guerreiro de verdade e enfrenta esse desafio.\n"
            "🏆 Se voltar vivo, leva glória, riqueza e umas recompensa boa demais da conta.\n\n"
            "Mas ó... num vai sozinho achando que é herói não, viu? Essa criatura "
            "num tem dó de ninguém. Se vacilar... vira adubo pras árvore daqui. 🌳😂\n\n"
            "Agora para de prosear e corre pro servidor! Eu vô ficá daqui só ouvindo "
            "os grito de quem entrou sem preparo.\n\n"
            "Que Odin ilumine ocês... e que os corvo num tenha serviço hoje! 🍻\n\n"
            "🔥 Boa sorte, guerreiros! 🔥"
        ),
        color=COR_VALHEIM,
    )
    embed.set_footer(text="🪓 Servidor Glitnir • Toda sexta-feira, 19h")

    arquivo = None
    if os.path.exists(IMAGEM_BOSS):
        arquivo = discord.File(IMAGEM_BOSS, filename="boss.png")
        embed.set_image(url="attachment://boss.png")

    return embed, arquivo


class BossReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        dados = storage.load_json(DATA_FILE, default={"last_sent_date": None})
        self._last_sent_date_str = dados.get("last_sent_date")  # ex: "2026-07-24"
        self.aviso_boss_semanal.start()

    def cog_unload(self):
        self.aviso_boss_semanal.cancel()

    def _salvar(self, data_str):
        storage.save_json(DATA_FILE, {"last_sent_date": data_str})

    @commands.command(name="boss")
    async def boss_manual(self, ctx):
        """Dispara o aviso de boss manualmente, a qualquer momento."""
        embed, arquivo = montar_embed_boss()
        if arquivo:
            await ctx.send(embed=embed, file=arquivo)
        else:
            await ctx.send(embed=embed)

    @tasks.loop(minutes=1)
    async def aviso_boss_semanal(self):
        agora = datetime.now(config.TZ_BRASILIA)

        # weekday(): segunda=0 ... sexta=4 ... domingo=6
        eh_sexta_19h = agora.weekday() == 4 and agora.hour == 19 and agora.minute == 0
        hoje_str = agora.date().isoformat()

        if eh_sexta_19h and self._last_sent_date_str != hoje_str:
            canal = self.bot.get_channel(config.CHAT_GERAL_ID)
            if canal:
                embed, arquivo = montar_embed_boss()
                if arquivo:
                    await canal.send(embed=embed, file=arquivo)
                else:
                    await canal.send(embed=embed)
                self._last_sent_date_str = hoje_str
                self._salvar(hoje_str)
                print(f"Aviso de boss enviado em {agora}")
            else:
                print("CHAT_GERAL_ID inválido ou bot sem acesso ao canal.")

    @aviso_boss_semanal.before_loop
    async def before_aviso_boss_semanal(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(BossReminder(bot))