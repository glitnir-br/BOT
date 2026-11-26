import asyncio

from pathlib import Path

import discord
from discord.ext import commands

import config
from utils import storage

DATA_FILE = "modpack.json"
IMAGENS_GUIA = Path(__file__).resolve().parent.parent / "assets" / "guia_gale"
ETAPAS_VISUAIS = (
    ("1. Menu de importação", "No Gale, selecione Importar → perfil via código.", "menu-importar.png"),
    ("2. Informe o código", "Cole o código atualizado do guia. Esta imagem mostra um código de exemplo.", "codigo-exemplo.png"),
    ("3. Inicie com mods", "Após importar e selecionar o perfil, clique em Iniciar com mods.", "iniciar.png"),
)


def embeds_guia(codigo):
    exibicao = codigo or "Ainda não configurado pela equipe"
    secoes = [
        ("🛠️ Guia de instalação — Modpack Glitnir", "Siga os passos abaixo para instalar o perfil de Glitnir e iniciar o Valheim com os mods do servidor.\n\n**1️⃣ Baixe e instale o Gale**\nAcesse a [Hexium](https://hexium.gg/mod-manager) ou a [Thunderstore](https://thunderstore.io/c/valheim/p/Kesomannen/GaleModManager/) e baixe o Gale. No Windows, extraia o arquivo se vier em `.zip` e execute o instalador `.msi`.\n\n**2️⃣ Selecione o Valheim**\nAbra o Gale e escolha **Valheim**. Se necessário, indique a pasta onde o jogo está instalado.", None),
        ("3️⃣ Importe o perfil", "No menu superior do Gale, clique em **Importar → perfil via código**.", "menu-importar.png"),
        ("Cole o código do modpack", f"Na janela **Importar perfil**, cole o código abaixo, clique em **Importar** e aguarde os downloads terminarem:\n```\n{exibicao}\n```\n\nA imagem mostra um código fictício; use o código acima.", "codigo-exemplo.png"),
        ("4️⃣ Inicie o jogo com mods", "Abra o perfil importado e clique em **Iniciar com mods**. Sempre inicie o jogo por esse perfil no Gale para jogar em Glitnir.", "iniciar.png"),
        ("5️⃣ Entre no servidor", "Use seu personagem exclusivo de Glitnir e conecte-se ao servidor informado pela equipe.\n\n**🔄 Atualizações**\nQuando a equipe publicar um novo código, importe-o no Gale e aguarde a instalação antes de entrar.\n\n**❓ Problemas comuns**\n• Mods não carregaram? Confira o perfil e use **Iniciar com mods**.\n• Erro na importação? Confira se copiou o código completo.\n• Não consegue entrar? Confira os avisos e o código mais recente.\n\nSe precisar de ajuda, abra um ticket e envie uma imagem do erro.", None),
    ]
    embeds = []
    for titulo, descricao, nome in secoes:
        embed = discord.Embed(title=titulo, description=descricao, color=config.COR_GLITNIR)
        if nome:
            embed.set_image(url=f"attachment://{nome}")
        embeds.append(embed)
    return embeds


def arquivos_guia():
    return [discord.File(IMAGENS_GUIA / nome, filename=nome) for _, _, nome in ETAPAS_VISUAIS]


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
            mensagem = await canal.send(embeds=embeds_guia(dados.get("codigo", "")), files=arquivos_guia(), allowed_mentions=discord.AllowedMentions.none())
            dados.update({"canal": canal.id, "mensagem": mensagem.id})
            storage.save_json(DATA_FILE, self.dados)
        await ctx.send(f"Guia publicado em {canal.mention}. Este será o guia atualizado pelo painel.", delete_after=15)

    def embed_painel(self, guild):
        canal_avisos = guild.get_channel(config.CANAL_AVISOS_INTERNOS_ID)
        referencia_avisos = canal_avisos.mention if canal_avisos else "canal de avisos internos"
        canal_guia = guild.get_channel(config.CANAL_GUIA_MODPACK_ID)
        referencia_guia = canal_guia.mention if canal_guia else "canal do guia de instalação"
        codigo = self.dados.get(str(guild.id), {}).get("codigo") or "Ainda não configurado"
        return discord.Embed(
            title="🛠️ Gerenciamento do modpack",
            description=(
                f"**Código atual:**\n```\n{codigo}\n```\n"
                "Quando houver uma nova versão do modpack, clique em **Atualizar código** e informe o novo código do perfil do Gale.\n\n"
                f"O bot atualizará o guia em {referencia_guia} e enviará um aviso com **@everyone** em {referencia_avisos}.\n\n"
                "Para limpar o código do guia, use **Remover código** e confirme a operação."
            ),
            color=config.COR_GLITNIR,
        )

    @commands.command(name="painel_modpack")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def painel(self, ctx):
        mensagem = await ctx.send(
            embed=self.embed_painel(ctx.guild),
            view=PainelModpack(),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        dados = self.dados.setdefault(str(ctx.guild.id), {})
        dados.update(painel_canal=ctx.channel.id, painel_mensagem=mensagem.id)
        storage.save_json(DATA_FILE, self.dados)

    async def atualizar_painel(self, guild, dados):
        canal = guild.get_channel(dados.get("painel_canal"))
        if not canal or not dados.get("painel_mensagem"):
            return False
        try:
            mensagem = await canal.fetch_message(dados["painel_mensagem"])
            await mensagem.edit(embed=self.embed_painel(guild), view=PainelModpack(), allowed_mentions=discord.AllowedMentions.none())
            return True
        except discord.HTTPException as erro:
            print(f"[Modpack] Falha ao atualizar painel: {erro}")
            return False

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
                await mensagem.edit(embeds=embeds_guia(codigo), attachments=arquivos_guia(), allowed_mentions=discord.AllowedMentions.none())
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
            painel_atualizado = await self.atualizar_painel(interaction.guild, dados)
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
            texto = "Código atualizado no guia e aviso publicado."
            if not painel_atualizado:
                texto += " Publique novamente o painel com `!painel_modpack` para mostrar o código atual."
            await interaction.followup.send(texto, ephemeral=True)

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
                await mensagem.edit(embeds=embeds_guia(""), attachments=arquivos_guia(), allowed_mentions=discord.AllowedMentions.none())
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
            painel_atualizado = await self.atualizar_painel(interaction.guild, dados)
            texto = "Código removido e guia atualizado."
            if not painel_atualizado:
                texto += " Publique novamente o painel com `!painel_modpack` para atualizar o card."
            await interaction.followup.send(texto, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Modpack(bot))
