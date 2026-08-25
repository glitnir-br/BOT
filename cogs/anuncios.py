import discord
from discord.ext import commands

COR_MUAMBINHA = discord.Color.from_rgb(184, 134, 11)  # tom dourado/bronze


def montar_embed_anuncio(canais: list) -> discord.Embed:
    lista_canais = "\n".join(f"📌 {canal.mention}" for canal in canais)

    embed = discord.Embed(
        title="🍺 Ô, ocês tudo aí!",
        description=(
            "Enquanto ocês tavam por aí brigando com troll e morrendo pra javali, "
            "eu tava trabalhando! 😤\n"
            "Arrumei uns canal novo aqui na vila pra deixá tudo mais organizado.\n\n"
            "👀 Passa lá, dá uma olhada e vê se ocê gosta:\n\n"
            f"{lista_canais}\n\n"
            "Se num gostá... pode reclamá.\n"
            "Mas eu provavelmente num vô ouvi. 😂🍻\n\n"
            "Bora conhecê as novidade!"
        ),
        color=COR_MUAMBINHA,
    )
    return embed


class Anuncios(commands.Cog):
    """Comandos pra anunciar novidades pro servidor"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="anunciar")
    @commands.has_permissions(administrator=True)
    async def anunciar(self, ctx: commands.Context, *, ids_texto: str = None):
        """Anuncia canais a partir dos IDs. Ex: !anunciar 123456789012345678, 234567890123456789"""
        if not ids_texto:
            await ctx.send(
                "Manda os IDs dos canais! Ex: `!anunciar 123456789012345678, 234567890123456789`",
                delete_after=10,
            )
            return

        partes = [p.strip() for p in ids_texto.replace(",", " ").split()]
        canais = []
        invalidos = []

        for parte in partes:
            if not parte.isdigit():
                invalidos.append(parte)
                continue
            canal = ctx.guild.get_channel(int(parte))
            if canal:
                canais.append(canal)
            else:
                invalidos.append(parte)

        if not canais:
            await ctx.send("Nenhum ID válido encontrado. Confere se copiou certinho.", delete_after=10)
            return

        await ctx.send(
            content="@everyone",
            embed=montar_embed_anuncio(canais),
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )

        if invalidos:
            await ctx.send(
                f"⚠️ Não encontrei esses IDs, ignorei eles: {', '.join(invalidos)}", delete_after=15
            )

        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!anunciar): {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Anuncios(bot))