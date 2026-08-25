import os

import discord
from discord.ext import commands

import config

# Caminho da imagem de fundo das boas-vindas — coloque um arquivo em assets/boas_vindas.png
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
IMAGEM_BOAS_VINDAS = os.path.join(ASSETS_DIR, "boas_vindas.png")

COR_GLITNIR = discord.Color.from_str("#17e0d6")


def montar_embed_boas_vindas(member: discord.Member):
    total_membros = member.guild.member_count

    embed = discord.Embed(
        title="⚔️ Mais um Viking chegou em Glitnir!",
        description=(
            f"Salve, {member.mention}! Seja muito bem-vindo(a) às terras de **Glitnir**.\n\n"
            "Aqui você vai encontrar aventuras, boas histórias e uma comunidade "
            "pronta pra te ajudar a sobreviver (e a rir das suas mortes pra troll 😄).\n\n"
            "📜 Dá uma olhadinha nas regras: <#1389580571214348328>\n"
            "📋 E não esquece de fazer sua whitelist: <#1530078865555325068>\n\n"
            "Qualquer dúvida, é só abrir um ticket de suporte!"
        ),
        color=COR_GLITNIR,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Você é o(a) Viking número {total_membros} do reino!")

    arquivo = None
    if os.path.exists(IMAGEM_BOAS_VINDAS):
        arquivo = discord.File(IMAGEM_BOAS_VINDAS, filename="boas_vindas.png")
        embed.set_image(url="attachment://boas_vindas.png")

    return embed, arquivo


class BoasVindas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not config.BEM_VINDO_ID:
            return

        canal = self.bot.get_channel(config.BEM_VINDO_ID)
        if not canal:
            return

        embed, arquivo = montar_embed_boas_vindas(member)
        try:
            if arquivo:
                await canal.send(embed=embed, file=arquivo)
            else:
                await canal.send(embed=embed)
        except Exception as e:
            print(f"Erro ao enviar mensagem de boas-vindas: {e}")

    @commands.command(name="testar_boasvindas")
    @commands.has_permissions(administrator=True)
    async def testar_boasvindas(self, ctx: commands.Context):
        """Simula a mensagem de boas-vindas usando você mesmo, sem precisar sair/entrar do servidor."""
        canal = self.bot.get_channel(config.BEM_VINDO_ID) if config.BEM_VINDO_ID else ctx.channel
        if not canal:
            await ctx.send("Canal de boas-vindas não encontrado (verifique BEM_VINDO_ID).", delete_after=10)
            return

        embed, arquivo = montar_embed_boas_vindas(ctx.author)
        if arquivo:
            await canal.send(embed=embed, file=arquivo)
        else:
            await canal.send(embed=embed)

        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!testar_boasvindas): {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(BoasVindas(bot))