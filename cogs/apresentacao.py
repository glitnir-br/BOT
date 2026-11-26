import discord
from discord.ext import commands

import config
from utils import storage

DATA_FILE = "painel_apresentacao.json"
EMOJI = "🩸"


class Apresentacao(commands.Cog):
    """Concede o cargo inicial por reação no canal comece-aqui."""

    def __init__(self, bot):
        self.bot = bot
        self.paineis = storage.load_json(DATA_FILE, default={})

    @commands.command(name="painel_apresentacao")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def painel(self, ctx):
        """Publica a mensagem de reação para receber o cargo inicial."""
        canal = ctx.guild.get_channel(config.CANAL_COMECE_AQUI_ID)
        cargo = ctx.guild.get_role(config.APRESENTESE_ID)
        if not canal or not hasattr(canal, "send") or not cargo:
            await ctx.send("Configure CANAL_COMECE_AQUI_ID e APRESENTESE_ID com um canal e cargo válidos.")
            return
        permissao = canal.permissions_for(ctx.guild.me)
        if not (permissao.view_channel and permissao.send_messages and permissao.read_message_history and permissao.add_reactions and permissao.manage_messages and ctx.guild.me.guild_permissions.manage_roles):
            await ctx.send("O bot precisa acessar o canal, enviar e fixar mensagens, adicionar reações e gerenciar cargos.")
            return
        if cargo.is_default() or cargo.managed or cargo >= ctx.guild.me.top_role:
            await ctx.send("O cargo inicial precisa estar abaixo do cargo do bot e ser gerenciável.")
            return
        registro = self.paineis.get(str(ctx.guild.id), {})
        mensagem = None
        if registro.get("canal") == canal.id and registro.get("mensagem"):
            try:
                mensagem = await canal.fetch_message(registro["mensagem"])
            except discord.NotFound:
                pass
            except discord.HTTPException as erro:
                print(f"[Apresentação] Erro ao consultar painel: {erro}")
                await ctx.send("Não foi possível verificar a mensagem existente.")
                return
        if mensagem and mensagem.author.id != self.bot.user.id:
            await ctx.send("A mensagem registrada não pertence ao bot. Verifique a configuração.")
            return
        try:
            embed = discord.Embed(title="🩸 Comece sua jornada", description="Reaja com 🩸 nesta mensagem para receber seu cargo e começar sua jornada em Glitnir!", color=config.COR_GLITNIR)
            if mensagem:
                await mensagem.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            else:
                mensagem = await canal.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                self.paineis[str(ctx.guild.id)] = {"canal": canal.id, "mensagem": mensagem.id}
                storage.save_json(DATA_FILE, self.paineis)
            await mensagem.add_reaction(EMOJI)
            if not mensagem.pinned:
                await mensagem.pin(reason=f"Painel de apresentação publicado por {ctx.author}")
        except (discord.HTTPException, OSError) as erro:
            print(f"[Apresentação] Erro ao publicar painel: {erro}")
            await ctx.send("Não foi possível concluir a publicação. Verifique as permissões e os logs.")
            return
        await ctx.send(f"Painel de apresentação publicado e fixado em {canal.mention}.")

    async def alterar_cargo(self, payload, adicionar):
        if not payload.guild_id or str(payload.emoji) != EMOJI:
            return
        painel = self.paineis.get(str(payload.guild_id), {})
        if payload.message_id != painel.get("mensagem") or payload.channel_id != painel.get("canal"):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild or not config.APRESENTESE_ID:
            return
        member = payload.member if adicionar else guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.HTTPException as erro:
                print(f"[Apresentação] Não foi possível consultar membro: {erro}")
                return
        if member.bot:
            return
        cargo = guild.get_role(config.APRESENTESE_ID)
        if not cargo:
            print("[Apresentação] Cargo APRESENTESE_ID não encontrado.")
            return
        try:
            if adicionar:
                await member.add_roles(cargo, reason="Reação no painel de apresentação")
            else:
                await member.remove_roles(cargo, reason="Reação removida do painel de apresentação")
        except discord.HTTPException as erro:
            print(f"[Apresentação] Falha ao alterar cargo do membro {member.id}: {erro}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.alterar_cargo(payload, True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.alterar_cargo(payload, False)


async def setup(bot):
    await bot.add_cog(Apresentacao(bot))
