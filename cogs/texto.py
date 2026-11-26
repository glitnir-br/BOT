from discord.ext import commands
import discord
from pathlib import Path

import config


class ConfirmarLimpeza(discord.ui.View):
    def __init__(self, autor_id):
        super().__init__(timeout=60)
        self.autor_id = autor_id
        self.processando = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Somente o administrador que iniciou a limpeza pode confirmá-la.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Apagar mensagens", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction, button):
        if self.processando:
            await interaction.response.send_message("A limpeza já está em andamento.", ephemeral=True)
            return
        self.processando = True
        await interaction.response.edit_message(content="Limpeza em andamento. Isso pode levar algum tempo.", view=None)
        try:
            removidas = await interaction.channel.purge(
                limit=None, check=lambda mensagem: mensagem.id != interaction.message.id,
                reason=f"Limpeza solicitada por {interaction.user} ({interaction.user.id})",
            )
        except discord.HTTPException as erro:
            print(f"[Limpeza] Falha no canal {interaction.channel_id}: {erro}")
            await interaction.followup.send("A limpeza foi interrompida. Algumas mensagens podem já ter sido apagadas.", ephemeral=True)
        else:
            await interaction.followup.send(f"Limpeza concluída: {len(removidas)} mensagem(ns) apagada(s).", ephemeral=True)
        finally:
            try:
                await interaction.message.delete()
            except discord.HTTPException:
                pass
            self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        if self.processando:
            await interaction.response.send_message("A limpeza já está em andamento.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Limpeza cancelada. Nenhuma mensagem foi apagada.", view=None)
        self.stop()


class Texto(commands.Cog):
    """Comando genérico pra postar qualquer texto como embed"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="limpar_chat")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.max_concurrency(1, per=commands.BucketType.channel)
    async def limpar_chat(self, ctx):
        permissoes = ctx.channel.permissions_for(ctx.guild.me)
        if not permissoes.manage_messages or not permissoes.read_message_history:
            await ctx.send("Preciso das permissões Gerenciar Mensagens e Ler Histórico de Mensagens neste canal.")
            return
        view = ConfirmarLimpeza(ctx.author.id)
        aviso = await ctx.send(
            f"⚠️ **Apagar todas as mensagens deste canal ({ctx.channel.mention})?** "
            "Isso inclui mensagens fixadas e não pode ser desfeito. Confirme em até 60 segundos.",
            view=view,
        )
        if await view.wait():
            try:
                await aviso.edit(content="Confirmação expirada. Nenhuma mensagem foi apagada.", view=None)
            except discord.HTTPException:
                pass

    @limpar_chat.error
    async def limpar_chat_erro(self, ctx, erro):
        if isinstance(erro, commands.MissingPermissions):
            await ctx.send("Somente administradores podem limpar o chat.")
        elif isinstance(erro, commands.NoPrivateMessage):
            await ctx.send("Este comando só pode ser usado em um servidor.")
        elif isinstance(erro, commands.MaxConcurrencyReached):
            await ctx.send("Já existe uma limpeza em andamento neste canal.")
        else:
            raise erro

    @commands.command(name="regras")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def regras(self, ctx: commands.Context):
        """Publica o códice no canal em que o comando for executado."""
        arquivo = Path(__file__).resolve().parent.parent / "regras" / "codice.md"
        try:
            texto = arquivo.read_text(encoding="utf-8-sig")
            secoes = [secao.strip() for secao in texto.split("\n# ")]
            secoes[0] = secoes[0].removeprefix("# ")
            embeds = []
            for secao in secoes:
                titulo, descricao = secao.split("\n", 1)
                if not titulo.strip() or len(titulo) > 256 or len(descricao.strip()) > 4096:
                    raise ValueError("Seção com título ou texto fora dos limites do Discord")
                embeds.append(discord.Embed(title=titulo, description=descricao.strip(), color=config.COR_GLITNIR))
        except (OSError, ValueError, IndexError) as erro:
            print(f"[Regras] Não foi possível preparar o códice: {erro}")
            await ctx.send("Não foi possível publicar as regras. Verifique o arquivo do códice.")
            return
        for embed in embeds:
            await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="text")
    @commands.has_permissions(administrator=True)
    async def text(self, ctx: commands.Context, *, conteudo: str = None):
        """Posta o texto (e imagem anexada, se tiver) como embed. Ex: !text Qualquer coisa aqui"""
        imagem_anexada = None
        for anexo in ctx.message.attachments:
            if anexo.content_type and anexo.content_type.startswith("image/"):
                imagem_anexada = anexo
                break

        if not conteudo and not imagem_anexada:
            await ctx.send(
                "Escreve ou cola o texto (ou anexa uma imagem) depois do comando! "
                "Ex: `!text Sua mensagem aqui`",
                delete_after=10,
            )
            return

        if conteudo:
            embed = discord.Embed(description=conteudo, color=config.COR_GLITNIR)
        else:
            embed = discord.Embed(color=config.COR_GLITNIR)

        arquivo = None
        if imagem_anexada:
            arquivo = await imagem_anexada.to_file()
            embed.set_image(url=f"attachment://{arquivo.filename}")

        if arquivo:
            await ctx.send(embed=embed, file=arquivo)
        else:
            await ctx.send(embed=embed)

        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!text): {e}")

    @commands.command(name="editar")
    @commands.has_permissions(administrator=True)
    async def editar(self, ctx: commands.Context, message_id: int, *, novo_texto: str):
        """Edita o texto de um embed que o bot já mandou. Ex: !editar 123456789 Novo texto aqui"""
        try:
            mensagem = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            await ctx.send("Não encontrei essa mensagem nesse canal (confere se o ID e o canal estão certos).", delete_after=10)
            return
        except discord.HTTPException as e:
            await ctx.send(f"Erro ao buscar a mensagem: {e}", delete_after=10)
            return

        if mensagem.author.id != self.bot.user.id:
            await ctx.send("Só consigo editar mensagens que eu mesmo mandei.", delete_after=10)
            return

        if not mensagem.embeds:
            await ctx.send("Essa mensagem não tem um embed pra editar.", delete_after=10)
            return

        embed = mensagem.embeds[0]
        embed.description = novo_texto
        await mensagem.edit(embed=embed)

        await ctx.send("✅ Mensagem atualizada!", delete_after=5)
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!editar): {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Texto(bot))
