import discord
from discord.ext import commands


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        embed = discord.Embed(
            description=f"🏓 **Pong!** Latência: `{round(self.bot.latency * 1000)}ms`",
            color=discord.Color.green(),
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(Ping(bot))