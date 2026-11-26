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


class ConfirmarRemocaoCodigo(discord.ui.View):
    def __init__(self, autor_id, codigo):
        super().__init__(timeout=60)
        self.autor_id = autor_id
        self.codigo = codigo
        self.processado = False

    async def interaction_check(self, interaction):
        if not interaction.guild or interaction.user.id != self.autor_id or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Somente o administrador que iniciou a remoção pode confirmá-la.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmar remoção", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction, button):
        if self.processado:
            await interaction.response.send_message("Esta solicitação já foi processada.", ephemeral=True)
            return
        self.processado = True
        self.stop()
        await interaction.response.edit_message(content="Removendo o código...", view=None)
        cog = interaction.client.get_cog("Modpack")
        if not cog:
            await interaction.followup.send("O sistema de modpack está indisponível.", ephemeral=True)
            return
        await cog.remover_codigo(interaction, self.codigo)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        self.stop()
        await interaction.response.edit_message(content="Remoção cancelada.", view=None)


class PainelModpack(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Atualizar código", emoji="✏️", style=discord.ButtonStyle.primary, custom_id="modpack:atualizar")
    async def atualizar(self, interaction, button):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Somente administradores podem atualizar o código.", ephemeral=True)
            return
        await interaction.response.send_modal(CodigoModal())

    @discord.ui.button(label="Remover código", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="modpack:remover")
    async def remover(self, interaction, button):
        if not interaction.guild or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Somente administradores podem remover o código.", ephemeral=True)
            return
        cog = interaction.client.get_cog("Modpack")
        dados = cog.dados.get(str(interaction.guild_id), {}) if cog else {}
        codigo = dados.get("codigo")
        if not cog:
            await interaction.response.send_message("O sistema de modpack está indisponível.", ephemeral=True)
        elif not codigo:
            await interaction.response.send_message("Não há código de modpack configurado.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Remover o código do guia? Ele ficará como não configurado.",
                view=ConfirmarRemocaoCodigo(interaction.user.id, codigo), ephemeral=True,
            )


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
        canal = ctx.guild.get_channel(config.CANAL_GUIA_MODPACK_ID)
        if not canal or not hasattr(canal, "send"):
            await ctx.send("Canal do guia não configurado ou inacessível. Verifique CANAL_GUIA_MODPACK_ID.")
            return
        async with self.lock:
            dados = self.dados.setdefault(str(ctx.guild.id), {})
            mensagem = await canal.send(embed=embed_guia(dados.get("codigo", "")), allowed_mentions=discord.AllowedMentions.none())
            dados.update({"canal": canal.id, "mensagem": mensagem.id})
            storage.save_json(DATA_FILE, self.dados)
        await ctx.send(f"Guia publicado em {canal.mention}. Este será o guia atualizado pelo painel.", delete_after=15)

    @commands.command(name="painel_modpack")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def painel(self, ctx):
        canal_avisos = ctx.guild.get_channel(config.CANAL_AVISOS_INTERNOS_ID)
        referencia_avisos = canal_avisos.mention if canal_avisos else "canal de avisos internos"
        canal_guia = ctx.guild.get_channel(config.CANAL_GUIA_MODPACK_ID)
        referencia_guia = canal_guia.mention if canal_guia else "canal do guia de instalação"
        embed = discord.Embed(
            title="🛠️ Gerenciamento do modpack",
            description=(
                "Quando houver uma nova versão do modpack, clique em **Atualizar código** e informe o novo código do perfil do Gale.\n\n"
                f"O bot atualizará o guia em {referencia_guia} e enviará um aviso com **@everyone** em {referencia_avisos}.\n\n"
                "Para limpar o código do guia, use **Remover código** e confirme a operação."
            ),
            color=config.COR_GLITNIR,
        )
        await ctx.send(
            embed=embed,
            view=PainelModpack(),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def atualizar(self, interaction, codigo):
        async with self.lock:
            dados = self.dados.get(str(interaction.guild_id), {})
            canal = interaction.guild.get_channel(config.CANAL_GUIA_MODPACK_ID)
            avisos = interaction.guild.get_channel(config.CANAL_AVISOS_INTERNOS_ID)
            if not canal or dados.get("canal") != config.CANAL_GUIA_MODPACK_ID or not dados.get("mensagem"):
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

    async def remover_codigo(self, interaction, codigo_esperado):
        async with self.lock:
            dados = self.dados.get(str(interaction.guild_id), {})
            if dados.get("codigo") != codigo_esperado:
                await interaction.followup.send("O código foi alterado desde a confirmação. Abra uma nova solicitação.", ephemeral=True)
                return
            canal = interaction.guild.get_channel(config.CANAL_GUIA_MODPACK_ID)
            if not canal or dados.get("canal") != config.CANAL_GUIA_MODPACK_ID or not dados.get("mensagem"):
                await interaction.followup.send("Guia não encontrado. Publique-o novamente com `!guia_modpack`.", ephemeral=True)
                return
            try:
                mensagem = await canal.fetch_message(dados["mensagem"])
                await mensagem.edit(embed=embed_guia(""), allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException as erro:
                print(f"[Modpack] Falha ao limpar guia: {erro}")
                await interaction.followup.send("Não foi possível atualizar o guia. Verifique o canal e as permissões do bot.", ephemeral=True)
                return
            dados["codigo"] = ""
            try:
                storage.save_json(DATA_FILE, self.dados)
            except OSError as erro:
                dados["codigo"] = codigo_esperado
                print(f"[Modpack] Falha ao salvar remoção: {erro}")
                await interaction.followup.send("O guia foi alterado, mas a remoção não foi salva. Avise a equipe.", ephemeral=True)
                return
            await interaction.followup.send("Código removido e guia atualizado.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Modpack(bot))
