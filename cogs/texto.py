from discord.ext import commands
import discord

import config


class Texto(commands.Cog):
    """Comando genérico pra postar qualquer texto como embed"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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