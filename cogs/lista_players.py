import asyncio
from contextlib import closing
import json
import sqlite3
from pathlib import Path

import discord
from discord.ext import commands

import config
from utils.storage import DATA_DIR

DB_PATH = Path(DATA_DIR) / "players_whitelist.sqlite3"


def conectar():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS players (guild_id TEXT NOT NULL, discord_id TEXT NOT NULL, steam_id TEXT NOT NULL, nickname TEXT NOT NULL, servidor TEXT NOT NULL, PRIMARY KEY (guild_id, discord_id, servidor))")
    db.execute("CREATE TABLE IF NOT EXISTS paineis (guild_id TEXT PRIMARY KEY, canal_id TEXT NOT NULL, mensagens TEXT NOT NULL)")
    db.commit()
    return db


class ListaPlayers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()
        with closing(conectar()) as db, db:
            pass

    def registrar(self, guild_id, discord_id, steam_id, nickname, servidor):
        with closing(conectar()) as db, db:
            db.execute("INSERT INTO players (guild_id, discord_id, steam_id, nickname, servidor) VALUES (?, ?, ?, ?, ?) ON CONFLICT(guild_id, discord_id, servidor) DO UPDATE SET steam_id=excluded.steam_id, nickname=excluded.nickname", (str(guild_id), str(discord_id), steam_id, nickname, servidor))

    def montar_embeds(self, guild_id):
        with closing(conectar()) as db, db:
            registros = db.execute("SELECT discord_id, steam_id, nickname, servidor FROM players WHERE guild_id=? ORDER BY nickname COLLATE NOCASE, discord_id", (str(guild_id),)).fetchall()
        embeds = []
        for chave, nome in (("server_1", "Server 1"), ("server_2", "Server 2")):
            linhas = []
            for discord_id, steam_id, nickname, servidor in registros:
                if servidor == chave:
                    nick = discord.utils.escape_markdown(nickname) if nickname else "Não informado"
                    linhas.append(f"👤 <@{discord_id}> · **{nick}**\nSteamID: `{steam_id}`")
            grupos, atual = [], ""
            for linha in linhas:
                if len(atual) + len(linha) + 2 > 3800:
                    grupos.append(atual)
                    atual = ""
                atual += linha + "\n\n"
            if atual or not grupos:
                grupos.append(atual or "Nenhum jogador registrado.")
            for indice, texto in enumerate(grupos, 1):
                titulo = f"📋 Jogadores — {nome}"
                if len(grupos) > 1:
                    titulo += f" ({indice}/{len(grupos)})"
                embeds.append(discord.Embed(title=titulo, description=texto, color=config.COR_GLITNIR))
        return embeds

    async def publicar(self, guild, canal):
        with closing(conectar()) as db, db:
            registro = db.execute("SELECT canal_id, mensagens FROM paineis WHERE guild_id=?", (str(guild.id),)).fetchone()
        ids = json.loads(registro[1]) if registro and registro[0] == str(canal.id) else []
        embeds = self.montar_embeds(guild.id)
        novos = []
        for index, embed in enumerate(embeds):
            mensagem = None
            if index < len(ids):
                try:
                    mensagem = await canal.fetch_message(int(ids[index]))
                except discord.NotFound:
                    pass
            if mensagem:
                if mensagem.author.id != self.bot.user.id:
                    raise ValueError("A mensagem registrada não pertence ao bot")
                await mensagem.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            else:
                mensagem = await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            novos.append(mensagem.id)
            # Persiste cada mensagem para permitir recuperação se uma publicação falhar.
            with closing(conectar()) as db, db:
                db.execute("INSERT INTO paineis (guild_id, canal_id, mensagens) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET canal_id=excluded.canal_id, mensagens=excluded.mensagens", (str(guild.id), str(canal.id), json.dumps(novos + ids[index + 1:])))
        for mensagem_id in ids[len(embeds):]:
            try:
                mensagem = await canal.fetch_message(int(mensagem_id))
                if mensagem.author.id == self.bot.user.id:
                    await mensagem.delete()
            except discord.NotFound:
                pass
        with closing(conectar()) as db, db:
            db.execute("INSERT INTO paineis (guild_id, canal_id, mensagens) VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET canal_id=excluded.canal_id, mensagens=excluded.mensagens", (str(guild.id), str(canal.id), json.dumps(novos)))

    async def atualizar_registrado(self, guild):
        async with self.lock:
            with closing(conectar()) as db, db:
                registro = db.execute("SELECT canal_id FROM paineis WHERE guild_id=?", (str(guild.id),)).fetchone()
            if not registro:
                return False
            if not config.CANAL_LISTA_PLAYERS_ID or int(registro[0]) != config.CANAL_LISTA_PLAYERS_ID:
                return False
            canal = guild.get_channel(config.CANAL_LISTA_PLAYERS_ID)
            if not canal:
                raise ValueError("Canal da lista não encontrado")
            await self.publicar(guild, canal)
            return True

    @commands.command(name="lista_players")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def lista_players(self, ctx):
        """Publica ou atualiza a lista de jogadores no canal configurado."""
        canal = ctx.guild.get_channel(config.CANAL_LISTA_PLAYERS_ID)
        if not canal or not hasattr(canal, "send"):
            await ctx.send("Canal da lista não encontrado. Verifique CANAL_LISTA_PLAYERS_ID.")
            return
        async with self.lock:
            try:
                await self.publicar(ctx.guild, canal)
            except (discord.HTTPException, sqlite3.Error, OSError, ValueError) as erro:
                print(f"[Lista de players] Erro: {erro}")
                await ctx.send("Não foi possível publicar a lista. Verifique permissões, armazenamento e logs.")
                return
        await ctx.send(f"Lista atualizada em {canal.mention}. Esse canal receberá as próximas atualizações.", delete_after=15)


async def setup(bot):
    await bot.add_cog(ListaPlayers(bot))
