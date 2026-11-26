import asyncio

import discord
from discord.ext import commands

import config
from utils import storage

DATA_FILE = "modpack.json"


def embed_guia(codigo):
    exibicao = codigo or "Ainda não configurado pela equipe"
    return discord.Embed(
        title="🛠️ Guia de instalação — Modpack Glitnir",
        description=(
            "Prepare seu Valheim para entrar em Glitnir.\n\n"
            "**1️⃣ Instale o Gale**\n"
            "Baixe o Gale Mod Manager pela [Hexium](https://hexium.gg/mod-manager) "
            "ou pela [Thunderstore](https://thunderstore.io/c/valheim/p/Kesomannen/GaleModManager/).\n\n"
            "**2️⃣ Selecione o Valheim**\n"
            "Abra o Gale, selecione Valheim e, se solicitado, indique a pasta do jogo.\n\n"
            "**3️⃣ Importe o modpack**\n"
            "Na tela de perfis, escolha a opção de importar por código e informe:\n"
            f"```\n{exibicao}\n```"
            "Aguarde a instalação terminar.\n\n"
            "**4️⃣ Inicie com mods**\n"
            "Selecione o perfil de Glitnir e inicie o jogo com mods pelo Gale.\n\n"
            "**5️⃣ Entre no servidor**\n"
            "Use seu personagem exclusivo de Glitnir e conecte-se ao servidor informado pela equipe.\n\n"
            "**Atualizações e ajuda**\n"
            "Acompanhe os avisos da equipe. Se precisar de ajuda, abra um ticket e envie uma imagem do erro."
        ),
        color=config.COR_GLITNIR,
    )


class CodigoModal(discord.ui.Modal, title="Atualizar código do modpack"):
    codigo = discord.ui.TextInput(label="Novo código do perfil", max_length=200)

    async def on_submit(self, interaction):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Somente administradores podem atualizar o código.", ephemeral=True)
            return
        codigo = str(self.codigo).strip()
        if not codigo or any(c in codigo for c in "`\r\n"):
            await interaction.response.send_message("Informe um código em uma linha, sem crases.", ephemeral=True)
            return
        cog = interaction.client.get_cog("Modpack")
        if not cog:
            await interaction.response.send_message("O sistema de modpack está indisponível.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await cog.atualizar(interaction, codigo)


class PainelModpack(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Atualizar código", emoji="✏️", style=discord.ButtonStyle.primary, custom_id="modpack:atualizar")
    async def atualizar(self, interaction, button):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Somente administradores podem atualizar o código.", ephemeral=True)
            return
        await interaction.response.send_modal(CodigoModal())


class Modpack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dados = storage.load_json(DATA_FILE, default={})
        self.lock = asyncio.Lock()

    async def cog_load(self):
        self.bot.add_view(PainelModpack())

    @commands.command(name="guia_modpack")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def guia(self, ctx):
        async with self.lock:
            dados = self.dados.setdefault(str(ctx.guild.id), {})
            mensagem = await ctx.send(embed=embed_guia(dados.get("codigo", "")), allowed_mentions=discord.AllowedMentions.none())
            dados.update({"canal": ctx.channel.id, "mensagem": mensagem.id})
            storage.save_json(DATA_FILE, self.dados)
        await ctx.send("Guia publicado. Este será o guia atualizado pelo painel.", delete_after=15)

    @commands.command(name="painel_modpack")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def painel(self, ctx):
        await ctx.send(
            "🛠️ **Gerenciamento do modpack**\n\n"
            "Quando houver uma nova versão do modpack, clique em **Atualizar código** e informe o novo código do perfil do Gale.\n\n"
            "O bot atualizará o código no último guia publicado e enviará automaticamente um aviso com **@everyone** no canal de avisos internos.\n\n"
            "Antes de usar o painel, publique o guia com `!guia_modpack` e configure `CANAL_AVISOS_INTERNOS_ID` no ambiente. "
            "Apenas administradores podem atualizar o código.",
            view=PainelModpack(),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def atualizar(self, interaction, codigo):
        async with self.lock:
            dados = self.dados.get(str(interaction.guild_id), {})
            canal = interaction.guild.get_channel(dados.get("canal"))
            avisos = interaction.guild.get_channel(config.CANAL_AVISOS_INTERNOS_ID)
            if not canal or not dados.get("mensagem"):
                await interaction.followup.send("Publique primeiro o guia usando `!guia_modpack`.", ephemeral=True)
                return
            if not avisos or not hasattr(avisos, "send"):
                await interaction.followup.send("Configure CANAL_AVISOS_INTERNOS_ID com um canal acessível deste servidor.", ephemeral=True)
                return
            try:
                mensagem = await canal.fetch_message(dados["mensagem"])
                await mensagem.edit(embed=embed_guia(codigo), allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException as erro:
                print(f"[Modpack] Falha ao atualizar guia: {erro}")
                await interaction.followup.send("Não foi possível atualizar o guia. Verifique o canal e as permissões do bot.", ephemeral=True)
                return
            dados["codigo"] = codigo
            try:
                storage.save_json(DATA_FILE, self.dados)
            except OSError as erro:
                print(f"[Modpack] Falha ao salvar código: {erro}")
                await interaction.followup.send("O guia foi atualizado, mas não foi possível salvar o código. Avise a equipe.", ephemeral=True)
                return
            try:
                await avisos.send(
                    content="@everyone",
                    embed=discord.Embed(
                        title="📢 O modpack de Glitnir foi atualizado!",
                        description=(f"Novo código de perfil:\n```\n{codigo}\n```\n"
                                     f"[Consulte o guia atualizado]({mensagem.jump_url})"),
                        color=config.COR_GLITNIR,
                    ),
                    allowed_mentions=discord.AllowedMentions(everyone=True, users=False, roles=False),
                )
            except discord.HTTPException as erro:
                print(f"[Modpack] Falha ao enviar aviso: {erro}")
                await interaction.followup.send("O guia e o código foram atualizados, mas não consegui enviar o aviso. Verifique as permissões do canal de avisos.", ephemeral=True)
                return
            await interaction.followup.send("Código atualizado no guia e aviso publicado.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Modpack(bot))
