import discord
from discord.ext import commands

import config


class Apresentacao(commands.Cog):
    """Atribui o cargo de apresentação aos novos membros."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or not config.APRESENTESE_ID:
            return
        cargo = member.guild.get_role(config.APRESENTESE_ID)
        if not cargo:
            print("[Apresentação] Cargo APRESENTESE_ID não encontrado.")
            return
        try:
            await member.add_roles(cargo, reason="Cargo atribuído ao entrar no servidor")
        except discord.HTTPException as erro:
            print(f"[Apresentação] Erro ao atribuir cargo ao novo membro {member.id}: {erro}")


async def setup(bot):
    await bot.add_cog(Apresentacao(bot))
