import os
from datetime import datetime

import discord
from discord.ext import commands, tasks

import config
from utils import storage

DATA_FILE = "quiz_reminder.json"

# Caminho da imagem do aviso — coloque um arquivo em assets/quiz.png
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
IMAGEM_QUIZ = os.path.join(ASSETS_DIR, "quiz.png")

COR_QUIZ = discord.Color.from_rgb(255, 87, 34)  # laranja/vermelho, clima de "quiz em chamas"


def montar_embed_quiz():
    embed = discord.Embed(
        title="🔥 Quiz Glitnir 🔥",
        description=(
            "Chegou a hora de testar seus conhecimentos! 🧠⚔️\n"
            "Leia as regras abaixo com atenção para participar corretamente.\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "## 📖 Como funciona?\n"
            "❓ As perguntas aparecerão no **chat branco**.\n"
            "💬 **As respostas devem ser enviadas somente no chat branco**, **não** no chat global.\n"
            "✍️ As respostas devem ser escritas:\n"
            "- Apenas com **letras minúsculas**;\n"
            "- **Sem espaços**;\n"
            "- **Sem acentos**.\n\n"
            "**Exemplo:**\n"
            "- ❌ Machado de Ferro\n"
            "- ❌ machado de ferro\n"
            "- ❌ machádodeferro\n"
            "- ✅ machadodeferro\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "## 🏆 Como funciona a vitória?\n"
            "Pode haver **mais de um vencedor**, dependendo do tempo em que o teleporte de "
            "gatilho permanecer ativo.\n"
            "Se você respondeu corretamente, mas **não recebeu a recompensa**, significa que "
            "outro jogador respondeu mais rápido.\n"
            "⚡ Velocidade também faz parte do desafio!\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🍻 Boa sorte a todos e que vença o viking mais sábio do Glitnir!"
        ),
        color=COR_QUIZ,
    )

    arquivo = None
    if os.path.exists(IMAGEM_QUIZ):
        arquivo = discord.File(IMAGEM_QUIZ, filename="quiz.png")
        embed.set_image(url="attachment://quiz.png")

    return embed, arquivo


class QuizReminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        dados = storage.load_json(DATA_FILE, default={"last_sent_date": None})
        self._last_sent_date_str = dados.get("last_sent_date")  # ex: "2026-07-24"
        self.aviso_quiz_semanal.start()

    def cog_unload(self):
        self.aviso_quiz_semanal.cancel()

    def _salvar(self, data_str):
        storage.save_json(DATA_FILE, {"last_sent_date": data_str})

    @commands.command(name="quiz")
    @commands.has_permissions(administrator=True)
    async def quiz_manual(self, ctx: commands.Context):
        """Dispara o anúncio do Quiz Glitnir manualmente, a qualquer momento."""
        embed, arquivo = montar_embed_quiz()
        if arquivo:
            await ctx.send(embed=embed, file=arquivo)
        else:
            await ctx.send(embed=embed)
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!quiz): {e}")

    @tasks.loop(minutes=1)
    async def aviso_quiz_semanal(self):
        agora = datetime.now(config.TZ_BRASILIA)

        # weekday(): segunda=0 ... quinta=3 ... domingo=6
        eh_quinta_20h = agora.weekday() == 3 and agora.hour == 20 and agora.minute == 0
        hoje_str = agora.date().isoformat()

        if eh_quinta_20h and self._last_sent_date_str != hoje_str:
            canal = self.bot.get_channel(config.QUIZ_CHANNEL_ID)
            if canal:
                embed, arquivo = montar_embed_quiz()
                if arquivo:
                    await canal.send(embed=embed, file=arquivo)
                else:
                    await canal.send(embed=embed)
                self._last_sent_date_str = hoje_str
                self._salvar(hoje_str)
                print(f"Anúncio de Quiz enviado em {agora}")
            else:
                print("QUIZ_CHANNEL_ID inválido ou bot sem acesso ao canal.")

    @aviso_quiz_semanal.before_loop
    async def before_aviso_quiz_semanal(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(QuizReminder(bot))