import discord
from discord.ext import commands

from utils.logger import send_log

# Palavras/expressões comuns em golpes de "cassino cripto" e spam de investimento.
# Tudo em minúsculo, comparado como substring dentro da mensagem (também minúscula).
PALAVRAS_SUSPEITAS = [
    # Português
    "cassino", "casino cripto", "crypto casino", "rakeback",
    "bônus grátis", "bonus gratis", "código promocional", "codigo promocional",
    "activate code", "saque aprovado", "withdrawal successful",
    "invista e ganhe", "duplicar seu", "duplique seu", "airdrop grátis", "airdrop gratis",
    "aposta liberada", "sorteio automático de cripto", "ganhe cripto grátis",
    "ganhe criptomoeda", "aposta segura", "lucro garantido",
    # Inglês — golpes de "cassino cripto" com conta famosa/hackeada
    "cryptocurrency casino", "crypto casino", "promo code", "special promo code",
    "claim your reward", "claim your bonus", "claim now", "giving away",
    "free bonus", "register and get", "withdrawal success", "play or withdraw",
    "only the fastest", "will be deleted in an hour", "double your crypto",
    "double your investment", "connect your wallet", "verify your wallet",
    "limited time offer", "exclusive bonus", "guaranteed profit",
]

# Se a mensagem tiver esse número de anexos (imagens) OU mais, junto de link externo,
# também é tratada como suspeita — típico desse golpe (prints de "saque" e "lucro").
MINIMO_ANEXOS_SUSPEITOS = 2


def _mensagem_suspeita(message: discord.Message) -> bool:
    conteudo = message.content.lower()

    if any(palavra in conteudo for palavra in PALAVRAS_SUSPEITAS):
        return True

    tem_link = "http://" in conteudo or "https://" in conteudo
    if tem_link and len(message.attachments) >= MINIMO_ANEXOS_SUSPEITOS:
        return True

    return False


class AntiSpam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Não modera quem tem permissão de administrador (staff)
        if message.author.guild_permissions.administrator:
            return

        if not _mensagem_suspeita(message):
            return

        try:
            await message.delete()
        except Exception as e:
            print(f"Erro ao apagar mensagem suspeita: {e}")
            return

        await send_log(
            self.bot,
            "Anti-Spam: Removida",
            f"Mensagem suspeita de golpe/spam de {message.author.mention} foi apagada no canal {message.channel.mention}",
            user=message.author,
            cor=discord.Color.red(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiSpam(bot))