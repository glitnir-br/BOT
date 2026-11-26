import asyncio
import re
from types import SimpleNamespace

import discord
import emoji
from discord.ext import commands

import config
from utils import storage

DATA_FILE = "guildas.json"


class FormularioGuilda(discord.ui.Modal, title="Criar guilda"):
    nome = discord.ui.TextInput(label="Nome da guilda", max_length=80)
    icone = discord.ui.TextInput(label="Ícone do chat", placeholder="Exemplo: ⚔️", max_length=20)

    async def on_submit(self, interaction):
        nome = str(self.nome).strip()
        icone = str(self.icone).strip()
        if not nome or not icone or re.search(r"[\r\n]", nome + icone):
            await interaction.response.send_message("Informe um nome e um ícone válidos.", ephemeral=True)
            return
        if not emoji.is_emoji(icone):
            await interaction.response.send_message("Informe exatamente um emoji Unicode como ícone, por exemplo ⚔️.", ephemeral=True)
            return
        nome_final = f"{icone} {nome}"
        if len(nome_final) > 100:
            await interaction.response.send_message("O nome completo, incluindo o ícone, deve ter no máximo 100 caracteres.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Criar o cargo e o canal **{discord.utils.escape_markdown(nome_final)}**?",
            view=ConfirmarCriacao(interaction.user.id, nome_final), ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class EditarGuilda(discord.ui.Modal, title="Editar nome e emoji da guilda"):
    nome = discord.ui.TextInput(label="Novo nome da guilda", max_length=80)
    icone = discord.ui.TextInput(label="Novo emoji", placeholder="Exemplo: ⚔️", max_length=20)

    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("Guildas")
        if not cog or not cog.eh_lider(interaction):
            await interaction.response.send_message("Somente o líder pode editar a guilda.", ephemeral=True)
            return
        nome = str(self.nome).strip()
        icone = str(self.icone).strip()
        if not nome or re.search(r"[\r\n]", nome) or not emoji.is_emoji(icone):
            await interaction.response.send_message("Informe um nome válido e exatamente um emoji Unicode.", ephemeral=True)
            return
        nome_final = f"{icone} {nome}"
        if len(nome_final) > 100:
            await interaction.response.send_message("O nome completo, incluindo o emoji, deve ter no máximo 100 caracteres.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with cog.lock:
            if not cog.eh_lider(interaction):
                await interaction.followup.send("Você não é mais o líder desta guilda.", ephemeral=True)
                return
            dados = cog.dados.get(str(interaction.channel_id))
            cargo = interaction.guild.get_role(dados["cargo"]) if dados else None
            canal = interaction.guild.get_channel(interaction.channel_id)
            if not cargo or not canal:
                await interaction.followup.send("Canal ou cargo da guilda não encontrado. Avise a equipe.", ephemeral=True)
                return
            nome_anterior = cargo.name
            try:
                await cargo.edit(name=nome_final, reason=f"Guilda editada pelo líder {interaction.user.id}")
                try:
                    await canal.edit(name=nome_final, reason=f"Guilda editada pelo líder {interaction.user.id}")
                except discord.HTTPException:
                    try:
                        await cargo.edit(name=nome_anterior, reason="Reverter edição incompleta da guilda")
                    except discord.HTTPException:
                        await interaction.followup.send("Não foi possível atualizar o canal nem reverter o cargo. Avise a equipe para corrigir os nomes.", ephemeral=True)
                        return
                    raise
            except discord.HTTPException as erro:
                print(f"[Guildas] Erro ao editar guilda: {erro}")
                await interaction.followup.send("Não foi possível editar a guilda. Verifique as permissões do bot.", ephemeral=True)
                return
        await interaction.followup.send("Nome e emoji da guilda atualizados no cargo e no canal.", ephemeral=True)


class ConfirmarCriacao(discord.ui.View):
    def __init__(self, autor_id, nome):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.nome = nome
        self.usado = False

    @discord.ui.button(label="Criar guilda", style=discord.ButtonStyle.success)
    async def criar(self, interaction, button):
        if interaction.user.id != self.autor_id or self.usado:
            await interaction.response.send_message("Esta confirmação não está disponível.", ephemeral=True)
            return
        self.usado = True
        self.stop()
        await interaction.response.edit_message(content="Criando sua guilda...", view=None)
        cog = interaction.client.get_cog("Guildas")
        if not cog:
            await interaction.followup.send("O sistema de guildas está indisponível.", ephemeral=True)
            return
        await cog.criar(interaction, self.nome)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Esta confirmação pertence a outro usuário.", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(content="Criação cancelada.", view=None)


class PainelGuildas(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Criar chat de guilda", emoji="🛡️", style=discord.ButtonStyle.primary, custom_id="guildas:criar")
    async def criar(self, interaction, button):
        cog = interaction.client.get_cog("Guildas")
        if not cog:
            await interaction.response.send_message("Sistema de guildas indisponível.", ephemeral=True)
            return
        if cog.lider_de_outra(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Você já é líder de uma guilda e não pode criar outra.", ephemeral=True)
            return
        await interaction.response.send_modal(FormularioGuilda())

    @discord.ui.button(label="Minhas guildas", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="guildas:minhas")
    async def minhas(self, interaction, button):
        cog = interaction.client.get_cog("Guildas")
        if not cog:
            await interaction.response.send_message("Sistema de guildas indisponível.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            membro = await interaction.guild.fetch_member(interaction.user.id)
        except discord.HTTPException:
            await interaction.followup.send("Não foi possível consultar suas guildas agora.", ephemeral=True)
            return
        cargos = {cargo.id for cargo in membro.roles}
        linhas = []
        for canal_id, dados in cog.dados.items():
            if dados["guild_id"] != interaction.guild_id or dados["cargo"] not in cargos:
                continue
            funcao = "Líder" if dados.get("lider") == membro.id else "Vice-líder" if dados.get("vice") == membro.id else "Membro"
            linhas.append(f'<@&{dados["cargo"]}> — **{funcao}** · <#{canal_id}>')
        if not linhas:
            await interaction.followup.send("Você ainda não participa de nenhuma guilda registrada.", ephemeral=True)
            return
        texto = "**Suas guildas:**\n"
        for indice, linha in enumerate(linhas):
            if len(texto) + len(linha) + 80 > 2000:
                texto += f"\n... e mais {len(linhas) - indice} guilda(s)."
                break
            texto += linha + "\n"
        await interaction.followup.send(texto, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


class EscolherMembro(discord.ui.UserSelect):
    def __init__(self, acao):
        super().__init__(placeholder="Selecione um membro do Discord", min_values=1, max_values=1)
        self.acao = acao

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Guildas")
        if not cog:
            await interaction.response.send_message("Sistema de guildas indisponível.", ephemeral=True)
            return
        await cog.alterar_membro(interaction, self.values[0], self.acao)


class EscolhaView(discord.ui.View):
    def __init__(self, acao):
        super().__init__(timeout=60)
        self.add_item(EscolherMembro(acao))


class SelecionarRemocao(discord.ui.Select):
    def __init__(self, membros):
        options = [discord.SelectOption(label=m.display_name[:100] or str(m.id), value=str(m.id),
                                        description=f"ID: {m.id}") for m in membros]
        super().__init__(placeholder="Selecione um membro da guilda", options=options)

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Guildas")
        if not cog or not cog.pode_gerenciar_membros(interaction):
            await interaction.response.send_message("Somente o líder ou vice-líder pode remover membros.", ephemeral=True)
            return
        membro = interaction.guild.get_member(int(self.values[0]))
        if not membro:
            try:
                membro = await interaction.guild.fetch_member(int(self.values[0]))
            except discord.HTTPException:
                await interaction.response.send_message("Membro não encontrado no servidor.", ephemeral=True)
                return
        self.view.stop()
        await cog.alterar_membro(interaction, membro, "remover")


class RemocaoView(discord.ui.View):
    def __init__(self, membros, autor_id, pagina=0):
        super().__init__(timeout=60)
        self.membros = membros
        self.autor_id = autor_id
        self.pagina = pagina
        self.add_item(SelecionarRemocao(membros[pagina * 25:(pagina + 1) * 25]))
        self.anterior.disabled = pagina == 0
        self.proxima.disabled = (pagina + 1) * 25 >= len(membros)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message("Esta seleção pertence a quem a abriu.", ephemeral=True)
            return False
        return True

    async def trocar_pagina(self, interaction, pagina):
        cog = interaction.client.get_cog("Guildas")
        if not cog or not cog.pode_gerenciar_membros(interaction):
            await interaction.response.send_message("Somente o líder ou vice-líder pode remover membros.", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(content=f"Selecione um membro da guilda (página {pagina + 1}):", view=RemocaoView(self.membros, self.autor_id, pagina))

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction, button):
        await self.trocar_pagina(interaction, self.pagina - 1)

    @discord.ui.button(label="Próxima", style=discord.ButtonStyle.secondary)
    async def proxima(self, interaction, button):
        await self.trocar_pagina(interaction, self.pagina + 1)


class ConfirmarExclusao(discord.ui.Modal, title="Confirmar exclusão da guilda"):
    nome = discord.ui.TextInput(label="Nome com emoji (exclui canal e cargo)", max_length=100)

    def __init__(self, autor_id, canal_id, nome_guilda):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.canal_id = canal_id
        self.usado = False
        self.nome.placeholder = nome_guilda[:100]

    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("Guildas")
        if interaction.user.id != self.autor_id or interaction.channel_id != self.canal_id or not cog or not cog.eh_lider(interaction):
            await interaction.response.send_message("Somente o líder que iniciou a exclusão pode confirmá-la.", ephemeral=True)
            return
        if self.usado:
            await interaction.response.send_message("Esta solicitação já foi processada.", ephemeral=True)
            return
        dados = cog.dados.get(str(self.canal_id))
        cargo = interaction.guild.get_role(dados["cargo"]) if dados else None
        if not cargo or str(self.nome) != cargo.name:
            await interaction.response.send_message("O nome informado não corresponde ao nome completo da guilda. Nenhuma alteração foi feita.", ephemeral=True)
            return
        self.usado = True
        self.stop()
        await interaction.response.send_message("Nome confirmado. Excluindo o canal e o cargo da guilda...", ephemeral=True)
        await cog.excluir(interaction, self.canal_id)


class MenuGuilda(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Gerenciar guilda", custom_id="guildas:menu", options=[
            discord.SelectOption(label="Adicionar membro", value="adicionar", emoji="➕"),
            discord.SelectOption(label="Remover membro", value="remover", emoji="➖"),
            discord.SelectOption(label="Selecionar vice-líder", value="vice", emoji="🛡️"),
            discord.SelectOption(label="Transferir liderança", value="transferir", emoji="👑"),
            discord.SelectOption(label="Editar nome e emoji", value="editar", emoji="✏️"),
            discord.SelectOption(label="Apagar guilda", value="excluir", emoji="🗑️"),
        ])

    async def callback(self, interaction):
        try:
            if self.values[0] == "excluir":
                await self.view.excluir(interaction)
            elif self.values[0] == "editar":
                cog = interaction.client.get_cog("Guildas")
                if not cog or not cog.eh_lider(interaction):
                    await interaction.response.send_message("Somente o líder pode editar a guilda.", ephemeral=True)
                    return
                await interaction.response.send_modal(EditarGuilda())
            else:
                await self.view.escolher(interaction, self.values[0])
        finally:
            try:
                await interaction.message.edit(view=ControlesGuilda())
            except discord.HTTPException as erro:
                print(f"[Guildas] Não foi possível limpar a seleção do menu: {erro}")


class ControlesGuilda(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MenuGuilda())

    async def escolher(self, interaction, acao):
        cog = interaction.client.get_cog("Guildas")
        permitido = cog and (cog.pode_gerenciar_membros(interaction) if acao in ("adicionar", "remover") else cog.eh_lider(interaction))
        if not permitido:
            await interaction.response.send_message("Você não tem permissão para usar este controle.", ephemeral=True)
            return
        if acao == "remover":
            await interaction.response.defer(ephemeral=True)
            dados = cog.dados[str(interaction.channel_id)]
            cargo = interaction.guild.get_role(dados["cargo"])
            if not cargo:
                await interaction.followup.send("Cargo da guilda não encontrado. Avise a equipe.", ephemeral=True)
                return
            try:
                membros = [m async for m in interaction.guild.fetch_members(limit=None)
                           if cargo in m.roles and m.id != dados["lider"] and not m.bot]
            except discord.HTTPException:
                await interaction.followup.send("Não foi possível consultar os membros da guilda.", ephemeral=True)
                return
            if not membros:
                await interaction.followup.send("Não há membros para remover.", ephemeral=True)
                return
            membros.sort(key=lambda m: (m.display_name.casefold(), m.id))
            await interaction.followup.send("Selecione um membro da guilda (página 1):", view=RemocaoView(membros, interaction.user.id), ephemeral=True)
            return
        await interaction.response.send_message("Selecione o membro:", view=EscolhaView(acao), ephemeral=True)

    async def excluir(self, interaction):
        cog = interaction.client.get_cog("Guildas")
        if not cog or not cog.eh_lider(interaction):
            await interaction.response.send_message("Somente o líder desta guilda pode apagá-la.", ephemeral=True)
            return
        dados = cog.dados[str(interaction.channel_id)]
        cargo = interaction.guild.get_role(dados["cargo"])
        if not cargo:
            await interaction.response.send_message("Cargo da guilda não encontrado. Avise a equipe.", ephemeral=True)
            return
        await interaction.response.send_modal(ConfirmarExclusao(interaction.user.id, interaction.channel_id, cargo.name))


class Guildas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.dados = storage.load_json(DATA_FILE, default={})
        self.lock = asyncio.Lock()

    def salvar(self):
        storage.save_json(DATA_FILE, self.dados)

    @staticmethod
    def embed_guilda(cargo, membros, lider=None, vice=None):
        linhas = [f"<@{membro_id}> — **{'Líder' if membro_id == lider else 'Vice-líder' if membro_id == vice else 'Membro'}**"
                  for membro_id in sorted(membros)]
        cabecalho = f"**Guilda:** {cargo.mention}\n\n**Membros ({len(linhas)}):**\n"
        descricao = cabecalho
        for indice, linha in enumerate(linhas):
            if len(descricao) + len(linha) + 200 > 4096:
                descricao += f"\n... e mais {len(linhas) - indice} membro(s)."
                break
            descricao += linha + "\n"
        descricao += "\nLíder e vice-líder podem adicionar ou remover membros. As demais ações são exclusivas do líder."
        return discord.Embed(title="🛡️ Gestão da guilda", description=descricao, color=discord.Color.blurple())

    async def atualizar_painel(self, canal, dados):
        cargo = canal.guild.get_role(dados["cargo"])
        if not cargo:
            return
        membros = [m.id async for m in canal.guild.fetch_members(limit=None) if cargo in m.roles]
        painel_id = dados.get("painel")
        painel = None
        if painel_id:
            try:
                painel = await canal.fetch_message(painel_id)
            except discord.NotFound:
                pass
        if painel is None:
            async for mensagem in canal.history(limit=100):
                if mensagem.author.id == self.bot.user.id and any(
                    componente.custom_id in ("guildas:adicionar", "guildas:menu")
                    for linha in mensagem.components for componente in linha.children
                ):
                    painel = mensagem
                    break
        embed = self.embed_guilda(cargo, membros, dados.get("lider"), dados.get("vice"))
        if painel:
            await painel.edit(content=cargo.mention, embed=embed, view=ControlesGuilda(), allowed_mentions=discord.AllowedMentions.none())
        else:
            painel = await canal.send(content=cargo.mention, embed=embed, view=ControlesGuilda(), allowed_mentions=discord.AllowedMentions.none())
        dados["painel"] = painel.id
        self.salvar()

    async def cog_load(self):
        self.bot.add_view(PainelGuildas())
        self.bot.add_view(ControlesGuilda())

    @commands.Cog.listener()
    async def on_ready(self):
        # Reconcilia saídas ocorridas enquanto o bot estava desligado.
        for canal_id, dados in list(self.dados.items()):
            guild = self.bot.get_guild(dados["guild_id"])
            canal = guild.get_channel(int(canal_id)) if guild else None
            if canal:
                try:
                    await self.atualizar_painel(canal, dados)
                except (discord.HTTPException, OSError) as erro:
                    print(f"[Guildas] Erro ao atualizar painel: {erro}")
            lider = dados.get("lider")
            if not guild or not lider:
                continue
            try:
                await guild.fetch_member(lider)
            except discord.NotFound:
                await self.on_member_remove(SimpleNamespace(guild=guild, id=lider))
            except discord.HTTPException as erro:
                print(f"[Guildas] Não foi possível verificar o líder {lider}: {erro}")

    def eh_lider(self, interaction):
        registro = self.dados.get(str(interaction.channel_id))
        return bool(registro and registro["guild_id"] == interaction.guild_id and registro.get("lider") == interaction.user.id)

    def pode_gerenciar_membros(self, interaction):
        registro = self.dados.get(str(interaction.channel_id))
        return bool(registro and registro["guild_id"] == interaction.guild_id and interaction.user.id in (registro.get("lider"), registro.get("vice")))

    def lider_de_outra(self, guild_id, usuario_id, exceto=None):
        return any(canal_id != str(exceto) and dados["guild_id"] == guild_id and dados.get("lider") == usuario_id
                   for canal_id, dados in self.dados.items())

    async def excluir(self, interaction, canal_id):
        async with self.lock:
            dados = self.dados.get(str(canal_id))
            if not dados or dados.get("lider") != interaction.user.id or dados["guild_id"] != interaction.guild_id:
                await interaction.followup.send("Você não é mais o líder desta guilda.", ephemeral=True)
                return
            canal = interaction.guild.get_channel(canal_id)
            cargo = interaction.guild.get_role(dados["cargo"])
            try:
                if cargo:
                    await cargo.delete(reason=f"Guilda excluída pelo líder {interaction.user.id}")
                if canal:
                    await canal.delete(reason=f"Guilda excluída pelo líder {interaction.user.id}")
            except discord.HTTPException as erro:
                print(f"[Guildas] Falha ao excluir guilda {canal_id}: {erro}")
                await interaction.followup.send("A exclusão ficou incompleta. Peça à equipe para verificar o canal e o cargo.", ephemeral=True)
                return
            self.dados.pop(str(canal_id), None)
            self.salvar()

    async def criar(self, interaction, nome):
        guild = interaction.guild
        categoria = guild.get_channel(config.CATEGORIA_GUILDAS_ID)
        if not isinstance(categoria, discord.CategoryChannel):
            await interaction.followup.send("Categoria de guildas não configurada. Avise a equipe.", ephemeral=True)
            return
        async with self.lock:
            if self.lider_de_outra(guild.id, interaction.user.id):
                await interaction.followup.send("Você já é líder de uma guilda.", ephemeral=True)
                return
            cargo = canal = None
            try:
                cargo = await guild.create_role(name=nome, reason=f"Guilda solicitada por {interaction.user.id}")
                await interaction.user.add_roles(cargo, reason="Líder da guilda")
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
                    cargo: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=True, read_message_history=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, send_messages=True, read_message_history=True, manage_channels=True),
                }
                canal = await guild.create_voice_channel(name=nome, category=categoria, overwrites=overwrites, reason="Canal de guilda")
                self.dados[str(canal.id)] = {"guild_id": guild.id, "cargo": cargo.id, "lider": interaction.user.id, "vice": None}
                self.salvar()
                painel = await canal.send(content=f"{cargo.mention} {interaction.user.mention}", embed=self.embed_guilda(cargo, [interaction.user.id], interaction.user.id), view=ControlesGuilda(), allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False))
                self.dados[str(canal.id)]["painel"] = painel.id
                self.salvar()
            except (discord.HTTPException, OSError) as erro:
                if canal:
                    self.dados.pop(str(canal.id), None)
                    try:
                        self.salvar()
                        await canal.delete(reason="Falha na criação da guilda")
                    except (discord.HTTPException, OSError):
                        pass
                if cargo:
                    try:
                        await cargo.delete(reason="Falha na criação da guilda")
                    except discord.HTTPException:
                        pass
                print(f"[Guildas] Erro ao criar guilda: {erro}")
                await interaction.followup.send("Não foi possível criar a guilda. Avise a equipe para verificar as permissões.", ephemeral=True)
                return
        await interaction.followup.send(f"Guilda criada: {canal.mention}", ephemeral=True)

    async def alterar_membro(self, interaction, usuario, acao):
        permitido = self.pode_gerenciar_membros(interaction) if acao in ("adicionar", "remover") else self.eh_lider(interaction)
        if not permitido:
            await interaction.response.send_message("Você não tem permissão para usar este controle.", ephemeral=True)
            return
        dados = self.dados[str(interaction.channel_id)]
        cargo = interaction.guild.get_role(dados["cargo"])
        membro = interaction.guild.get_member(usuario.id)
        if not membro:
            try:
                membro = await interaction.guild.fetch_member(usuario.id)
            except discord.HTTPException:
                await interaction.response.send_message("Membro não encontrado no servidor.", ephemeral=True)
                return
        if not cargo or membro.bot or membro.id == dados["lider"]:
            await interaction.response.send_message("Não é possível alterar este membro ou cargo.", ephemeral=True)
            return
        if acao in ("remover", "vice", "transferir") and cargo not in membro.roles:
            await interaction.response.send_message("Este jogador não é membro da guilda.", ephemeral=True)
            return
        if acao == "transferir" and self.lider_de_outra(interaction.guild_id, membro.id, interaction.channel_id):
            await interaction.response.send_message("Este membro já é líder de outra guilda.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            if acao == "adicionar":
                await membro.add_roles(cargo, reason=f"Adicionado pela gestão da guilda: {interaction.user.id}")
                mensagem = "Membro adicionado."
            elif acao == "remover":
                await membro.remove_roles(cargo, reason=f"Removido pela gestão da guilda: {interaction.user.id}")
                if dados.get("vice") == membro.id:
                    dados["vice"] = None
                    self.salvar()
                mensagem = "Membro removido."
            elif acao == "vice":
                dados["vice"] = membro.id
                self.salvar()
                mensagem = "Vice-líder selecionado."
            elif acao == "transferir":
                async with self.lock:
                    if not self.eh_lider(interaction) or self.lider_de_outra(interaction.guild_id, membro.id, interaction.channel_id):
                        await interaction.followup.send("Não foi possível transferir: a liderança mudou ou o membro já lidera outra guilda.", ephemeral=True)
                        return
                    dados["lider"] = membro.id
                    if dados.get("vice") == membro.id:
                        dados["vice"] = None
                    self.salvar()
                mensagem = f"Liderança transferida para {membro.display_name}."
            if acao in ("adicionar", "remover", "vice", "transferir"):
                try:
                    await self.atualizar_painel(interaction.channel, dados)
                except (discord.HTTPException, OSError) as erro:
                    print(f"[Guildas] Erro ao atualizar painel: {erro}")
                    mensagem += " Não foi possível atualizar a lista no painel."
            await interaction.followup.send(mensagem, ephemeral=True)
        except (discord.HTTPException, OSError) as erro:
            print(f"[Guildas] Erro ao atualizar membro: {erro}")
            await interaction.followup.send("Não foi possível concluir a operação. Avise a equipe.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        async with self.lock:
            for canal_id, dados in self.dados.items():
                if dados["guild_id"] != member.guild.id:
                    continue
                if dados.get("lider") == member.id:
                    vice = member.guild.get_member(dados.get("vice")) if dados.get("vice") else None
                    cargo = member.guild.get_role(dados["cargo"])
                    if vice is None and dados.get("vice"):
                        try:
                            vice = await member.guild.fetch_member(dados["vice"])
                        except discord.HTTPException:
                            pass
                    vice_disponivel = (vice and cargo and cargo in vice.roles
                                       and not self.lider_de_outra(member.guild.id, vice.id, canal_id))
                    dados["lider"] = vice.id if vice_disponivel else None
                    dados["vice"] = None
                    self.salvar()
                    canal = member.guild.get_channel(int(canal_id))
                    if canal:
                        try:
                            texto = f"<@{vice.id}> agora é o líder da guilda." if dados["lider"] else "O líder saiu e não há vice-líder elegível. Um administrador precisa definir um novo líder."
                            await canal.send(texto)
                        except discord.HTTPException:
                            pass
                elif dados.get("vice") == member.id:
                    dados["vice"] = None
                    self.salvar()
                canal = member.guild.get_channel(int(canal_id))
                if canal:
                    try:
                        await self.atualizar_painel(canal, dados)
                    except (discord.HTTPException, OSError) as erro:
                        print(f"[Guildas] Erro ao atualizar painel: {erro}")

    @commands.command(name="guilda_lider")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def definir_lider(self, ctx, membro: discord.Member):
        dados = self.dados.get(str(ctx.channel.id))
        if not dados or dados["guild_id"] != ctx.guild.id:
            await ctx.send("Use este comando no chat do canal de voz da guilda.")
            return
        cargo = ctx.guild.get_role(dados["cargo"])
        if not cargo or cargo not in membro.roles or membro.bot:
            await ctx.send("O novo líder precisa ser membro da guilda.")
            return
        if self.lider_de_outra(ctx.guild.id, membro.id, ctx.channel.id):
            await ctx.send("Esse membro já é líder de outra guilda.")
            return
        dados["lider"] = membro.id
        if dados.get("vice") == membro.id:
            dados["vice"] = None
        self.salvar()
        try:
            await self.atualizar_painel(ctx.channel, dados)
        except (discord.HTTPException, OSError) as erro:
            print(f"[Guildas] Erro ao atualizar painel: {erro}")
        await ctx.send(f"{membro.mention} agora é o líder da guilda.")


async def setup(bot):
    await bot.add_cog(Guildas(bot))
