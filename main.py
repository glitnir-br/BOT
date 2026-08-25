import asyncio

import discord
from discord.ext import commands

import config

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

EXTENSIONS = [
    "cogs.ping",
    "cogs.voice_rooms",
    "cogs.support",
    "cogs.apresentacao",
    "cogs.anuncios",
    "cogs.texto",
    "cogs.boas_vindas",
    "cogs.cargos",
    "cogs.anti_spam",
    "cogs.agendados",
]


@bot.event
async def on_ready():
    print(f"Bot online como {bot.user} (ID: {bot.user.id})")
    if config.DISCORD_ID:
        guild = bot.get_guild(config.DISCORD_ID)
        print(f"Conectado no servidor: {guild.name if guild else 'não encontrado'}")


async def main():
    async with bot:
        for extension in EXTENSIONS:
            await bot.load_extension(extension)
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    if not config.TOKEN:
        raise SystemExit("DISCORD_TOKEN não encontrado. Configure o arquivo .env")
    asyncio.run(main())