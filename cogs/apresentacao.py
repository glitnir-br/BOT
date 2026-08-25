import discord
from discord.ext import commands

import config
from utils import storage

DATA_FILE = "recado_reacoes.json"


class Apresentacao(commands.Cog):
    """Mantém funcionando o cargo por reação 🩸 nas mensagens de recado já publicadas."""

    def __init__(self, bot):
        self.bot = bot
        dados = storage.load_json(DATA_FILE, default={"mensagens": []})
        self.mensagens_recado = set(dados.get("mensagens", []))

    def _salvar(self):
        storage.save_json(DATA_FILE, {"mensagens": list(self.mensagens_recado)})

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "🩸" or payload.message_id not in self.mensagens_recado:
            return
        if not config.APRESENTESE_ID or payload.member is None or payload.member.bot:
            return

        cargo = payload.member.guild.get_role(config.APRESENTESE_ID)
        if cargo:
            try:
                await payload.member.add_roles(cargo)
            except Exception as e:
                print(f"Erro ao dar cargo de recado: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "🩸" or payload.message_id not in self.mensagens_recado:
            return
        if not config.APRESENTESE_ID:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        membro = guild.get_member(payload.user_id)
        if not membro or membro.bot:
            return

        cargo = guild.get_role(config.APRESENTESE_ID)
        if cargo:
            try:
                await membro.remove_roles(cargo)
            except Exception as e:
                print(f"Erro ao remover cargo de recado: {e}")


async def setup(bot):
    await bot.add_cog(Apresentacao(bot))