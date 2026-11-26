import discord
from discord import ui
from discord.ext import commands

import config


def administrador(interaction):
    return bool(interaction.guild and interaction.user.guild_permissions.administrator)


def canais_permitidos(guild):
    configurados = (
        ("Avisos internos", config.CANAL_AVISOS_INTERNOS_ID),
        ("Chat geral", config.CHAT_GERAL_ID),
        ("Anúncios", config.CANAL_ANUNCIOS_ID),
        ("Anúncios do Sjar", config.CANAL_ANUNCIOS_SJAR_ID),
        ("Chat Admin", config.CANAL_CHAT_ADMIN_ID),
    )
    return [(nome, canal) for nome, canal_id in configurados
            if canal_id and (canal := guild.get_channel(canal_id)) and hasattr(canal, "send")]


class MensagemModal(ui.Modal, title="Enviar mensagem"):
    texto = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, max_length=4000)

    def __init__(self, canal_id, autor_id):
        super().__init__()
        self.canal_id = canal_id
        self.autor_id = autor_id
        self.imagem = ui.FileUpload(required=False, max_values=1)
        self.add_item(ui.Label(text="Imagem (opcional)", component=self.imagem))

    async def on_submit(self, interaction):
        if not administrador(interaction) or interaction.user.id != self.autor_id:
            await interaction.response.send_message("Somente o administrador que iniciou o envio pode continuar.", ephemeral=True)
            return
        texto = self.texto.value.strip()
        if not texto:
            await interaction.response.send_message("A mensagem não pode ficar vazia.", ephemeral=True)
            return
        canal = next((canal for _, canal in canais_permitidos(interaction.guild) if canal.id == self.canal_id), None)
        if not canal or not hasattr(canal, "send"):
            await interaction.response.send_message("O canal escolhido não está disponível.", ephemeral=True)
            return
        permissoes = canal.permissions_for(interaction.guild.me)
        if not permissoes.view_channel or not permissoes.send_messages or not permissoes.embed_links or not permissoes.mention_everyone:
            await interaction.response.send_message("O bot precisa poder ver o canal, enviar mensagens, inserir links e mencionar @everyone.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return
        anexo = self.imagem.values[0] if self.imagem.values else None
        if anexo and (not anexo.content_type or not anexo.content_type.startswith("image/")):
            await interaction.response.send_message("O arquivo enviado precisa ser uma imagem.", ephemeral=True)
            return
        if anexo and not permissoes.attach_files:
            await interaction.response.send_message("O bot precisa de permissão para anexar arquivos nesse canal.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            embed = discord.Embed(description=texto, color=config.COR_GLITNIR)
            kwargs = {}
            if anexo:
                arquivo = await anexo.to_file()
                embed.set_image(url=f"attachment://{arquivo.filename}")
                kwargs["file"] = arquivo
            await canal.send(content="@everyone", embed=embed,
                             allowed_mentions=discord.AllowedMentions(everyone=True, users=False, roles=False), **kwargs)
        except discord.HTTPException as erro:
            print(f"[Mensagens] Falha ao enviar mensagem: {erro}")
            await interaction.followup.send("Não foi possível enviar a mensagem. Verifique as permissões do bot.", ephemeral=True)
            return
        await interaction.followup.send(f"Mensagem enviada em {canal.mention}.", ephemeral=True)


class EscolherCanal(ui.Select):
    def __init__(self, canais):
        super().__init__(placeholder="Escolha o canal de publicação", options=[
            discord.SelectOption(label=nome, value=str(canal.id)) for nome, canal in canais
        ])

    async def callback(self, interaction):
        if not administrador(interaction) or interaction.user.id != self.view.autor_id:
            await interaction.response.send_message("Somente o administrador que iniciou o envio pode continuar.", ephemeral=True)
            return
        canal_id = int(self.values[0])
        if not any(canal.id == canal_id for _, canal in canais_permitidos(interaction.guild)):
            await interaction.response.send_message("Este canal não está mais disponível para envio.", ephemeral=True)
            return
        await interaction.response.send_modal(MensagemModal(canal_id, self.view.autor_id))


class EscolhaCanalView(ui.View):
    def __init__(self, autor_id, canais):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.add_item(EscolherCanal(canais))


class PainelMensagens(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Enviar mensagem", emoji="📨", style=discord.ButtonStyle.primary, custom_id="mensagens:enviar")
    async def enviar(self, interaction, button):
        if not administrador(interaction):
            await interaction.response.send_message("Apenas administradores podem enviar mensagens.", ephemeral=True)
            return
        canais = canais_permitidos(interaction.guild)
        if not canais:
            await interaction.response.send_message("Nenhum canal de envio está configurado ou acessível.", ephemeral=True)
            return
        await interaction.response.send_message("Escolha o canal para publicar a mensagem:", view=EscolhaCanalView(interaction.user.id, canais), ephemeral=True)


class PainelAntigo(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Novo agendamento", style=discord.ButtonStyle.success, custom_id="agendados:novo")
    async def antigo(self, interaction, button):
        if not administrador(interaction):
            await interaction.response.send_message("Apenas administradores podem usar o painel.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=embed_painel(), view=PainelMensagens())


def embed_painel():
    return discord.Embed(title="📨 Enviador de mensagens", description=(
        "Clique em **Enviar mensagem**, escolha o canal e escreva o texto. "
        "Você também pode anexar uma imagem. A mensagem será publicada imediatamente "
        "em um card, com **@everyone** fora dele."
    ), color=config.COR_GLITNIR)


class Agendados(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PainelMensagens())
        self.bot.add_view(PainelAntigo())

    @commands.command(name="painel_mensagens")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def painel(self, ctx):
        canal = ctx.guild.get_channel(config.CANAL_BOT_MANAGER_ID)
        if not canal or not hasattr(canal, "send"):
            await ctx.send("Canal bot-manager não encontrado. Verifique CANAL_BOT_MANAGER_ID.")
            return
        await canal.send(embed=embed_painel(), view=PainelMensagens(), allowed_mentions=discord.AllowedMentions.none())
        await ctx.send(f"Painel publicado em {canal.mention}.", delete_after=10)


async def setup(bot):
    await bot.add_cog(Agendados(bot))
