import asyncio
import os

import aiohttp
import discord
from discord import ui
from discord.ext import commands

import config
from utils.logger import send_log
from utils.image_cache import obter_url_cacheada

# Caminho da imagem do painel de suporte — coloque um arquivo em assets/ticket.png
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
IMAGEM_TICKET = os.path.join(ASSETS_DIR, "ticket.png")

# Imagens extras enviadas automaticamente no ticket de Doações
IMAGEM_VALORES = os.path.join(ASSETS_DIR, "doacao_valores.png")
IMAGEM_PIX = os.path.join(ASSETS_DIR, "doacao_pix.png")

# Imagem de instruções pra deixar o perfil Steam público (Whitelist)
IMAGEM_STEAM_PUBLICO = os.path.join(ASSETS_DIR, "whitelist_steam.png")


async def montar_embeds_extra_doacao(bot):
    """Monta até 2 embeds (valores + pix), reaproveitando o link já hospedado (sem reenviar o arquivo)."""
    embeds = []

    if os.path.exists(IMAGEM_VALORES):
        url = await obter_url_cacheada(bot, IMAGEM_VALORES, "doacao_valores.png", config.CANAL_LOG_ID)
        if url:
            embed = discord.Embed(title="💰 Valores das Moedas", color=config.COR_GLITNIR)
            embed.set_image(url=url)
            embeds.append(embed)

    if os.path.exists(IMAGEM_PIX):
        url = await obter_url_cacheada(bot, IMAGEM_PIX, "doacao_pix.png", config.CANAL_LOG_ID)
        if url:
            embed = discord.Embed(title="🔑 Chave PIX", color=config.COR_GLITNIR)
            embed.set_image(url=url)
            embeds.append(embed)

    return embeds

# Opções de valor pro ticket de Doações — aparecem como menu de seleção, não texto livre
VALORES_DOACAO = [
    "R$ 15,00 - 4 GC",
    "R$ 35,00 - 10 GC",
    "R$ 50,00 - 18 GC",
    "R$ 100,00 - 40 GC",
    "R$ 250,00 - 120 GC",
]

# Perguntas do formulário de cada categoria: (label, estilo, placeholder, tamanho_max)
PERGUNTAS = {
    "Dúvidas": [
        {"label": "Qual sua dúvida?", "style": discord.TextStyle.paragraph, "placeholder": "Descreva sua dúvida em detalhes", "max_length": 500},
    ],
    "Suporte": [
        {"label": "Qual o Nickname no jogo?", "max_length": 50},
        {"label": "Descreva o problema encontrado", "style": discord.TextStyle.paragraph, "max_length": 500},
    ],
    "Doações": [
        {"label": "Qual o Nickname no jogo?", "max_length": 50},
        {"label": "Qual sua ID Steam?", "max_length": 50},
    ],
    "Whitelist": [
        {"label": "Nickname usado no jogo:", "max_length": 20},
        {
            "label": "Sua SteamID:",
            "placeholder": "Ex: 76561198000000000",
            "min_length": 17,
            "max_length": 17,
        },
        {"label": "Você já jogou em outra season?", "max_length": 100},
        {"label": "Algum amigo joga no servidor? Se sim, quem?", "style": discord.TextStyle.paragraph, "max_length": 200},
        {"label": "Deixou sua ID Steam pública?", "max_length": 20},
    ],
    "Chat de Guilda": [
        {"label": "Quais os membros da sua guilda?", "style": discord.TextStyle.paragraph, "placeholder": "Liste os membros (nicknames)", "max_length": 500},
        {"label": "Qual o nome da Guilda e Emoji para ela?", "max_length": 100},
    ],
    "Território de Guilda": [
        {"label": "Nome da Guilda", "max_length": 100},
        {"label": "Nome do Líder", "max_length": 50},
        {"label": "Steam ID de todos os membros", "style": discord.TextStyle.paragraph, "placeholder": "Uma Steam ID por linha", "max_length": 500},
        {"label": "Formato do território", "placeholder": "Digite: Redondo ou Quadrado", "max_length": 20},
    ],
    "Envio de Dados": [
        {"label": "Nome", "max_length": 100},
        {"label": "ID Steam", "max_length": 50},
        {"label": "Comprovante (link ou observação)", "placeholder": "Envie o comprovante assim que abrir o ticket", "max_length": 300, "obrigatorio": False},
    ],
}

EMOJIS = {
    "Dúvidas": "💡",
    "Suporte": "🎫",
    "Doações": "💰",
    "Whitelist": "📋",
    "Chat de Guilda": "💬",
    "Território de Guilda": "🗺️",
    "Envio de Dados": "🎫",
}

# Cor fixa por categoria, usada nos logs (abertura e arquivamento) e pode ser reaproveitada em outros embeds
CORES_CATEGORIA = {
    "Whitelist": discord.Color.green(),
    "Suporte": discord.Color.red(),
    "Dúvidas": discord.Color.gold(),
    "Doações": discord.Color.from_rgb(255, 140, 0),  # laranja, cor de moeda
    "Chat de Guilda": discord.Color.blue(),
    "Território de Guilda": discord.Color.dark_teal(),
    "Envio de Dados": discord.Color.blurple(),
}

# Categorias que aparecem no menu principal (!ticket_painel). Whitelist e Guildas têm painel próprio.
CATEGORIAS_MENU_PRINCIPAL = ["Dúvidas", "Suporte"]


def embed_painel_suporte():
    embed = discord.Embed(
        title="❱ CONSELHO DE GLITNIR",
        description=(
            "Precisa de **ajuda**? Utilize o **menu abaixo** para falar com nossa equipe!\n\n"
            "**❱ Categorias**\n"
            "> ✦ `💡` **Dúvidas:** Acerca do funcionamento da comunidade.\n"
            "> ✦ `🎫` **Suporte:** Problemas técnicos ou no jogo.\n\n"
            "*Ao selecionar, um pequeno formulário vai abrir e, depois, um canal privado será criado só pra você e a equipe.*"
        ),
        color=config.COR_GLITNIR,
    )

    arquivo = None
    if os.path.exists(IMAGEM_TICKET):
        arquivo = discord.File(IMAGEM_TICKET, filename="ticket.png")
        embed.set_image(url="attachment://ticket.png")

    return embed, arquivo


def embed_boas_vindas_ticket(categoria: str, autor: discord.Member, respostas: list) -> discord.Embed:
    embed = discord.Embed(
        title=f"❱ Atendimento: {categoria}",
        description=(
            f"Olá {autor.mention}!\n"
            "Nossa equipe vai analisar as informações abaixo e te responder em breve."
        ),
        color=config.COR_GLITNIR,
    )
    for label, valor in respostas:
        nome_campo = label if categoria == "Envio de Dados" else f"• {label}"
        embed.add_field(name=nome_campo, value=valor or "—", inline=False)

    if categoria in ("Chat de Guilda", "Território de Guilda"):
        embed.add_field(
            name="⚠️ Requisitos pra aprovação",
            value=(
                "A guilda precisa ter **no mínimo 5 membros**, e este chamado precisa "
                "ter sido aberto pelo **Líder** da guilda."
            ),
            inline=False,
        )

    if categoria == "Envio de Dados":
        embed.add_field(
            name="📎 Comprovante",
            value="Nos envie o comprovante por gentileza!",
            inline=False,
        )
        embed.add_field(
            name="⚠️ Importante",
            value=(
                "Certifique-se de que o ID Steam esteja correto para facilitar a "
                "identificação e o atendimento. Aguarde a equipe após o envio dos dados. ✅"
            ),
            inline=False,
        )

    embed.add_field(
        name="⏳ Prazo de atendimento",
        value=(
            "Nossa equipe costuma responder em até **24 horas**. "
            "Agradecemos a paciência e a confiança em fazer parte da Glitnir! 🔥"
        ),
        inline=False,
    )
    return embed


def _dividir_em_blocos(linhas: list, limite: int = 1900) -> list:
    """Junta linhas em blocos de até `limite` caracteres, pra caber em mensagens do Discord.
    Uma linha sozinha maior que o limite é quebrada em pedaços, pra nunca estourar um bloco."""
    linhas_normalizadas = []
    for linha in linhas:
        if len(linha) <= limite:
            linhas_normalizadas.append(linha)
        else:
            for i in range(0, len(linha), limite):
                linhas_normalizadas.append(linha[i:i + limite])

    blocos = []
    atual = ""
    for linha in linhas_normalizadas:
        candidato = f"{atual}\n\n{linha}" if atual else linha
        if len(candidato) > limite:
            if atual:
                blocos.append(atual)
            atual = linha
        else:
            atual = candidato
    if atual:
        blocos.append(atual)
    return blocos


async def process_ticket_closure(bot, canal: discord.TextChannel, user_who_closed: discord.abc.User):
    """Arquiva o histórico do chamado num tópico de log (sem download) e apaga o canal original."""
    log_channel = bot.get_channel(config.LOG_FECHADOS_ID) if config.LOG_FECHADOS_ID else None

    linhas = []
    campos_formulario = []
    primeira_mensagem = True

    async for msg in canal.history(limit=500, oldest_first=True):
        hora = msg.created_at.strftime("%d/%m %H:%M")

        # A primeira mensagem do canal é sempre o embed de boas-vindas com as respostas do formulário
        if primeira_mensagem:
            primeira_mensagem = False
            if msg.embeds:
                campos_formulario = [
                    (campo.name, campo.value)
                    for campo in msg.embeds[0].fields
                    if campo.name != "⏳ Prazo de atendimento"
                ]
            continue  # não repete o embed de boas-vindas na transcrição

        if msg.content:
            linhas.append(f"**{msg.author.display_name}** • `{hora}`\n{msg.content}")
        for anexo in msg.attachments:
            linhas.append(f"**{msg.author.display_name}** • `{hora}`\n📎 {anexo.url}")

    if log_channel:
        categoria_ticket = canal.topic.split(":")[0].strip() if canal.topic else ""
        cor = CORES_CATEGORIA.get(categoria_ticket, discord.Color.orange())

        # Descobre quem abriu o ticket a partir do topic do canal ("categoria:user_id")
        dono_ticket = None
        if canal.topic and ":" in canal.topic:
            try:
                dono_id = int(canal.topic.split(":")[1])
                dono_ticket = canal.guild.get_member(dono_id) or await bot.fetch_user(dono_id)
            except (ValueError, discord.NotFound):
                dono_ticket = None

        embed = discord.Embed(
            title="🗄️ Ticket Arquivado",
            description=f"O chamado **#{canal.name}** foi encerrado.",
            color=cor,
            timestamp=discord.utils.utcnow(),
        )
        if dono_ticket:
            embed.add_field(name="Aberto por", value=dono_ticket.mention, inline=True)
            embed.set_author(name=str(dono_ticket.display_name), icon_url=dono_ticket.display_avatar.url)
        embed.add_field(name="Encerrado por", value=user_who_closed.mention, inline=True)

        if categoria_ticket == "Whitelist":
            aprovado = bool(canal.topic and canal.topic.endswith(":aprovado"))
            embed.add_field(
                name="Whitelist",
                value="✅ Aprovada" if aprovado else "❌ Não aprovada",
                inline=True,
            )

        # Respostas do formulário sempre aparecem aqui, aprovado ou não
        for nome_campo, valor_campo in campos_formulario:
            embed.add_field(name=f"📋 {nome_campo}", value=valor_campo or "—", inline=False)

        embed.set_footer(text="Abra o tópico abaixo pra ver a conversa completa")

        try:
            mensagem_log = await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Erro ao enviar o embed de arquivamento do ticket: {e}")
            mensagem_log = None

        topico_log = None
        if mensagem_log:
            try:
                topico_log = await mensagem_log.create_thread(
                    name=f"📄 {canal.name}"[:100],
                    auto_archive_duration=10080,  # 1 semana
                )
            except Exception as e:
                print(f"Erro ao criar o tópico de log do ticket, tentando de novo em 3s: {e}")
                await asyncio.sleep(3)
                try:
                    topico_log = await mensagem_log.create_thread(
                        name=f"📄 {canal.name}"[:100],
                        auto_archive_duration=10080,
                    )
                except Exception as e2:
                    print(f"Tópico de log falhou de novo, usando o canal como alternativa: {e2}")
                    topico_log = None

        # Se não conseguiu criar o tópico (rate limit, etc.), manda a transcrição
        # direto no canal de log mesmo, pra não perder o conteúdo.
        destino_transcricao = topico_log or log_channel

        if not topico_log and mensagem_log:
            embed.set_footer(text="Conversa completa logo abaixo (sem tópico dessa vez)")
            try:
                await mensagem_log.edit(embed=embed)
            except Exception:
                pass

        if destino_transcricao:
            if linhas:
                for indice, bloco in enumerate(_dividir_em_blocos(linhas), start=1):
                    try:
                        await destino_transcricao.send(bloco)
                    except Exception as e:
                        print(f"Erro ao enviar bloco {indice} da transcrição: {e}")
                        try:
                            await destino_transcricao.send(
                                f"⚠️ Um trecho da conversa (bloco {indice}) não pôde ser enviado."
                            )
                        except Exception:
                            pass
            else:
                try:
                    await destino_transcricao.send("*Nenhuma mensagem foi registrada neste chamado.*")
                except Exception as e:
                    print(f"Erro ao enviar aviso de transcrição vazia: {e}")

    try:
        await canal.delete()
    except Exception as e:
        print(f"Erro ao apagar o canal de ticket: {e}")


def eh_staff(member: discord.Member) -> bool:
    """Administrador sempre conta como staff; além disso, qualquer cargo em CARGOS_ADM_ID também conta."""
    if member.guild_permissions.administrator:
        return True
    if config.CARGOS_ADM_ID:
        ids_do_membro = {cargo.id for cargo in member.roles}
        if any(rid in ids_do_membro for rid in config.CARGOS_ADM_ID):
            return True
    return False


async def obter_respostas_ticket(canal: discord.TextChannel) -> dict:
    """Busca o embed de boas-vindas do ticket (primeira mensagem do canal) e retorna
    um dicionário {label sem o marcador "• ": valor}, pra facilitar buscar uma resposta pelo label exato."""
    async for msg in canal.history(limit=5, oldest_first=True):
        if msg.embeds:
            return {campo.name.lstrip("•").strip(): campo.value for campo in msg.embeds[0].fields}
    return {}


async def enviar_whitelist_base44(nickname: str, steamid: str) -> tuple:
    """Envia o Nickname e a SteamID aprovados pro Base44, pra cadastrar o player na tabela de players.
    O Base44 responde com um JSON {"ok": bool, "error": str}, então além do status HTTP a gente
    confere o campo "ok" — pode vir HTTP 200 com "ok": false se ele recusar por dentro.
    Retorna (sucesso: bool, mensagem_de_erro: str — vazia se sucesso)."""
    if not config.WHITELIST_TOKEN:
        return False, "WHITELIST_TOKEN não configurado no .env"

    payload = {"nick": nickname, "steamid": steamid}
    headers = {
        "Content-Type": "application/json",
        "x-whitelist-token": config.WHITELIST_TOKEN,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                config.BASE44_WHITELIST_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resposta:
                texto_bruto = await resposta.text()
                try:
                    dados = await resposta.json(content_type=None)
                except Exception:
                    dados = None

                if resposta.status in (200, 201) and isinstance(dados, dict) and dados.get("ok"):
                    return True, ""

                erro = dados.get("error") if isinstance(dados, dict) else None
                return False, str(erro) if erro else f"HTTP {resposta.status}: {texto_bruto[:200]}"
    except Exception as e:
        return False, str(e)


class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="support:close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Só administradores podem encerrar um chamado.", ephemeral=True
            )
            return
        await interaction.response.send_message("Encerrando chamado e arquivando logs...")
        await process_ticket_closure(interaction.client, interaction.channel, interaction.user)


class WhitelistTicketView(TicketControlView):
    @ui.button(label="Aprovar Whitelist", emoji="✅", style=discord.ButtonStyle.success, custom_id="support:aprovar_whitelist")
    async def aprovar(self, interaction: discord.Interaction, button: ui.Button):
        if not eh_staff(interaction.user):
            await interaction.response.send_message(
                "Só a equipe pode aprovar uma whitelist.", ephemeral=True
            )
            return

        if not config.CARGO_WHITELIST_ID:
            await interaction.response.send_message(
                "Cargo de whitelist não configurado (verifique CARGO_WHITELIST_ID no .env).", ephemeral=True
            )
            return

        role = interaction.guild.get_role(config.CARGO_WHITELIST_ID)
        if not role:
            await interaction.response.send_message("Cargo de whitelist não encontrado no servidor.", ephemeral=True)
            return

        topic = interaction.channel.topic or ""
        try:
            user_id = int(topic.split(":")[1])
        except (IndexError, ValueError):
            await interaction.response.send_message("Não consegui identificar o dono deste ticket.", ephemeral=True)
            return

        membro = interaction.guild.get_member(user_id)
        if not membro:
            await interaction.response.send_message("Membro não encontrado no servidor (pode ter saído).", ephemeral=True)
            return

        await membro.add_roles(role)

        # Marca esse canal como aprovado, pra aparecer certinho quando o ticket for arquivado depois
        try:
            await interaction.channel.edit(topic=f"{topic}:aprovado")
        except Exception as e:
            print(f"Erro ao marcar ticket de whitelist como aprovado: {e}")

        # --- Integração Base44: envia Nickname + SteamID pra tabela de players ---
        respostas = await obter_respostas_ticket(interaction.channel)
        nickname = (respostas.get("Nickname usado no jogo:") or "").strip()
        steamid = (respostas.get("Sua SteamID:") or "").strip()

        if nickname and steamid:
            base44_ok, base44_erro = await enviar_whitelist_base44(nickname, steamid)
        else:
            base44_ok, base44_erro = False, "Não encontrei o Nickname/SteamID no formulário deste ticket"

        if base44_ok:
            await send_log(
                interaction.client, "Whitelist: Base44",
                f"Enviou {nickname} ({steamid}) pro Base44 (aprovado por {interaction.user.mention})",
                user=membro, cor=discord.Color.green()
            )
        else:
            await send_log(
                interaction.client, "Whitelist: Base44 (falhou)",
                f"Não conseguiu enviar {membro.mention} pro Base44 — {base44_erro}",
                user=interaction.user, cor=discord.Color.red()
            )

        embed_boas_vindas = discord.Embed(
            title="👋 Bem-vindo(a) ao Glitnir!",
            description=(
                "Seja muito bem-vindo(a)! Antes de entrar no servidor, siga estes passos:\n\n"
                "📜 **Leia as Regras:**\n"
                "https://discord.com/channels/848339987174785054/1389580571214348328\n\n"
                "🛠️ **Veja o Guia de Instalação:**\n"
                "Aprenda como instalar os mods e entrar no servidor.\n"
                "https://discord.com/channels/848339987174785054/1479613965414830181\n\n"
                "🎫 **Precisa de ajuda?**\n"
                "Abra um Ticket de Suporte e nossa equipe irá ajudá-lo.\n"
                "https://discord.com/channels/848339987174785054/1530270146726465576\n\n"
                "Desejamos uma ótima aventura em Glitnir! ⚔️"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(content=membro.mention, embed=embed_boas_vindas)
        await send_log(
            interaction.client, "Whitelist: Aprovado", f"Aprovou a whitelist de {membro.mention}",
            user=interaction.user, cor=discord.Color.green()
        )


def obter_categoria_discord(guild: discord.Guild, categoria: str):
    """Retorna a categoria do Discord configurada pra esse tipo de ticket, caindo na SUPPORT_CATEGORY_ID se não houver uma específica."""
    categoria_id = config.CATEGORIAS_POR_TIPO.get(categoria) or config.SUPPORT_CATEGORY_ID
    if not categoria_id:
        return None
    canal = guild.get_channel(categoria_id)
    if isinstance(canal, discord.CategoryChannel):
        return canal
    return None


async def _apagar_depois(mensagem, segundos: float):
    """Apaga uma mensagem (inclusive efêmera) depois de alguns segundos."""
    await asyncio.sleep(segundos)
    try:
        await mensagem.delete()
    except Exception:
        pass


def _slug_canal(texto: str) -> str:
    """Deixa um texto no formato aceito pelo Discord pra nome de canal (minúsculo, hífens, mantendo acentos)."""
    texto = texto.lower().strip()
    texto = texto.replace(" ", "-")
    permitido = "abcdefghijklmnopqrstuvwxyzáàâãéèêẽíìîõóòôúùûçñ0123456789-_()"
    return "".join(c for c in texto if c in permitido) or "ticket"


async def abrir_ticket(interaction: discord.Interaction, categoria: str, respostas: list):
    """Cria o canal privado do ticket, dentro da categoria configurada, já com as respostas do formulário."""
    categoria_discord = obter_categoria_discord(interaction.guild, categoria)

    if not categoria_discord:
        await interaction.followup.send(
            "Categoria de ticket não configurada pra esse tipo (verifique o .env).", ephemeral=True
        )
        return

    marcador = f"{categoria}:{interaction.user.id}"
    for canal_existente in categoria_discord.channels:
        if isinstance(canal_existente, discord.TextChannel) and canal_existente.topic and canal_existente.topic.startswith(marcador):
            await interaction.followup.send(
                f"Você já possui um chamado de **{categoria}** aberto! "
                f"Finalize o anterior antes de abrir um novo: {canal_existente.mention}",
                ephemeral=True,
            )
            return

    nome_canal = _slug_canal(f"{categoria} ({interaction.user.display_name})")[:90]

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True),
    }
    if config.CARGOS_ADM_ID:
        for staff_role_id in config.CARGOS_ADM_ID:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    try:
        canal_ticket = await interaction.guild.create_text_channel(
            name=nome_canal,
            category=categoria_discord,
            overwrites=overwrites,
            topic=marcador,
        )

        view_do_ticket = WhitelistTicketView() if categoria == "Whitelist" else TicketControlView()
        await canal_ticket.send(
            embed=embed_boas_vindas_ticket(categoria, interaction.user, respostas),
            view=view_do_ticket,
        )

        confirmacao = await interaction.followup.send(
            f"✅ Chamado de **{categoria}** aberto em: {canal_ticket.mention}", ephemeral=True, wait=True
        )
        asyncio.create_task(_apagar_depois(confirmacao, 3))

        await send_log(
            interaction.client, "Suporte: Aberto", f"Abriu um chamado de {categoria}",
            user=interaction.user, cor=CORES_CATEGORIA.get(categoria), channel_id=config.LOG_ABERTOS_ID
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao abrir chamado: {e}", ephemeral=True)


class CategoriaModal(ui.Modal):
    def __init__(self, categoria: str, respostas_extras: list = None, mensagem_para_apagar: discord.Message = None):
        super().__init__(title=f"Ticket: {categoria}")
        self.categoria = categoria
        self.respostas_extras = respostas_extras or []
        self.mensagem_para_apagar = mensagem_para_apagar
        self.perguntas = PERGUNTAS[categoria]
        self.campos = []
        for pergunta in self.perguntas:
            campo = ui.TextInput(
                label=pergunta.get("label"),
                style=pergunta.get("style", discord.TextStyle.short),
                placeholder=pergunta.get("placeholder", ""),
                max_length=pergunta.get("max_length", 200),
                min_length=pergunta.get("min_length"),
                required=pergunta.get("obrigatorio", True),
            )
            if pergunta.get("description"):
                self.add_item(ui.Label(text=pergunta["label"], description=pergunta["description"], component=campo))
            else:
                self.add_item(campo)
            self.campos.append(campo)

    async def on_submit(self, interaction: discord.Interaction):
        respostas = [(self.perguntas[i]["label"], self.campos[i].value) for i in range(len(self.campos))]
        await interaction.response.defer(ephemeral=True)

        if self.mensagem_para_apagar:
            try:
                await self.mensagem_para_apagar.delete()
            except Exception as e:
                print(f"Erro ao apagar mensagem anterior do ticket: {e}")

        respostas += self.respostas_extras
        await abrir_ticket(interaction, self.categoria, respostas)


async def embeds_regras_whitelist(bot):
    """Monta os embeds com as instruções obrigatórias antes de preencher o ticket de Whitelist."""
    embed_steam = discord.Embed(
        title="🔓 Deixe seu perfil Steam público",
        color=discord.Color.red(),
    )

    url_steam = None
    if os.path.exists(IMAGEM_STEAM_PUBLICO):
        url_steam = await obter_url_cacheada(bot, IMAGEM_STEAM_PUBLICO, "whitelist_steam.png", config.CANAL_LOG_ID)

    if url_steam:
        embed_steam.set_image(url=url_steam)
    else:
        embed_steam.description = (
            "Jogos ficam ocultos por padrão no Steam. Pra liberar, mude suas "
            "configurações de privacidade do perfil:\n\n"
            "**1.** No seu Perfil Steam, clique em **Editar Perfil**\n"
            "**2.** Clique na aba **Minhas configurações de privacidade**\n"
            "**3.** Defina **Detalhes do jogo** como **Público**\n"
            "**4.** Desmarque **Sempre mantenha meu tempo total de jogo privado**\n\n"
            "*Pode levar alguns minutos até o cache atualizar depois da mudança.*"
        )

    embed_nome = discord.Embed(
        title="📝 Regras de Nome e Identidade",
        description=(
            "Os nomes têm poder. Evite nomes ofensivos, vulgares ou de mau gosto.\n\n"
            "**O nome no jogo deve ser o mesmo utilizado no Discord.**\n"
            "*Exemplo: Morgnar ou Morgnar / Victor Padilha*\n\n"
            "**O nome no jogo não pode ter espaços, números ou caracteres especiais.**\n\n"
            "Nomes considerados inapropriados podem resultar em recusa de acesso, "
            "solicitação de alteração obrigatória ou banimento, sem aviso prévio."
        ),
        color=config.COR_GLITNIR,
    )

    return [embed_steam, embed_nome]


class ContinuarWhitelistView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.mensagem_para_apagar = None

    @ui.button(label="Já li, quero continuar", style=discord.ButtonStyle.success, custom_id="support:whitelist_continuar")
    async def continuar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CategoriaModal("Whitelist"))
        if self.mensagem_para_apagar:
            try:
                await self.mensagem_para_apagar.delete()
            except Exception as e:
                print(f"Erro ao apagar mensagem de regras da whitelist: {e}")


def embed_painel_whitelist() -> discord.Embed:
    embed = discord.Embed(
        title="📋 WHITELIST DE GLITNIR",
        description=(
            "# Junte-se à Glitnir!\n"
            "Este é o primeiro passo pra fazer parte da nossa comunidade Viking. "
            "Sua solicitação será analisada pela nossa equipe com todo cuidado.\n\n"
            "### ⚔️ Como funciona?\n"
            "Clique no botão **Solicitar Whitelist** logo abaixo. Antes do formulário, "
            "vamos te mostrar duas coisas importantes:\n"
            "> ✦ Como deixar seu perfil Steam **público**\n"
            "> ✦ As **regras de nome e identidade** do servidor\n\n"
            "*Leia tudo com atenção — isso evita atrasos na aprovação do seu acesso!*"
        ),
        color=config.COR_GLITNIR,
    )
    embed.set_footer(text="Servidor Glitnir • Que Odin guie sua jornada!")
    return embed


class WhitelistPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Solicitar Whitelist", emoji="📋", style=discord.ButtonStyle.success, custom_id="support:whitelist_solicitar")
    async def solicitar(self, interaction: discord.Interaction, button: ui.Button):
        embeds = await embeds_regras_whitelist(interaction.client)
        view = ContinuarWhitelistView()
        await interaction.response.send_message(
            content="Leia as instruções abaixo com atenção antes de continuar:",
            embeds=embeds,
            view=view,
            ephemeral=True,
        )
        view.mensagem_para_apagar = await interaction.original_response()


class ValorDoacaoSelect(ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=valor) for valor in VALORES_DOACAO]
        super().__init__(placeholder="Escolha o valor da doação...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        valor_escolhido = self.values[0]
        respostas_extras = [("Qual o valor doado?", valor_escolhido)]
        await interaction.response.send_modal(
            CategoriaModal("Doações", respostas_extras, mensagem_para_apagar=self.view.mensagem_para_apagar)
        )


class ValorDoacaoView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.mensagem_para_apagar = None
        self.add_item(ValorDoacaoSelect())


def embed_painel_doacao() -> discord.Embed:
    embed = discord.Embed(
        title="💰 DOAÇÕES DE GLITNIR",
        description=(
            "Quer apoiar o servidor? Clique no botão abaixo pra fazer sua doação!\n\n"
            "*Você vai ver os valores disponíveis e a chave PIX antes de preencher o "
            "formulário com seus dados.*"
        ),
        color=CORES_CATEGORIA.get("Doações", config.COR_GLITNIR),
    )
    return embed


class DoacaoPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Fazer Doação", emoji="💰", style=discord.ButtonStyle.success, custom_id="support:doacao_solicitar")
    async def solicitar(self, interaction: discord.Interaction, button: ui.Button):
        embeds_extra = await montar_embeds_extra_doacao(interaction.client)
        view = ValorDoacaoView()
        await interaction.response.send_message(
            content="Confira os valores abaixo e escolha o valor da sua doação:",
            embeds=embeds_extra,
            view=view,
            ephemeral=True,
        )
        view.mensagem_para_apagar = await interaction.original_response()


def embed_painel_envio_dados() -> discord.Embed:
    embed = discord.Embed(
        title="🎫 TICKET — ENVIO DE DADOS",
        description=(
            "Olá! 👋\n"
            "Este ticket será utilizado para o envio de informações e comprovantes, "
            "para que possamos conversar sobre seu caso.\n\n"
            "⚠️ **Importante:**\n"
            "Aguarde a equipe após a abertura do ticket e siga as orientações fornecidas "
            "durante o atendimento. ✅\n\n"
            "*Clique no botão abaixo pra começar.*"
        ),
        color=CORES_CATEGORIA.get("Envio de Dados", config.COR_GLITNIR),
    )
    return embed


class EnvioDadosPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Enviar Dados", emoji="🎫", style=discord.ButtonStyle.success, custom_id="support:envio_dados_solicitar")
    async def solicitar(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CategoriaModal("Envio de Dados"))


def embed_painel_guilda() -> discord.Embed:
    embed = discord.Embed(
        title="🛡️ GUILDAS DE GLITNIR",
        description=(
            "Escolha abaixo o que você precisa:\n\n"
            "> 💬 **Chat de Guilda** — solicite a criação de um chat privado pra sua guilda\n"
            "> 🗺️ **Território de Guilda** — solicite a demarcação de um território\n\n"
            "### ⚠️ Requisitos obrigatórios\n"
            "> ✦ Sua guilda precisa ter **no mínimo 5 membros**\n"
            "> ✦ O ticket **precisa ser aberto pelo Líder** da guilda\n\n"
            "*Chamados que não atendam esses requisitos serão recusados.*\n\n"
            "*Ao selecionar, um formulário vai abrir e um canal privado será criado só "
            "pra você e a equipe da Staff.*"
        ),
        color=config.COR_GLITNIR,
    )
    return embed


class GuildaDropdown(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Chat de Guilda", emoji=EMOJIS["Chat de Guilda"]),
            discord.SelectOption(label="Território de Guilda", emoji=EMOJIS["Território de Guilda"]),
        ]
        super().__init__(
            placeholder="Escolha uma opção...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="guilda:dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        categoria = self.values[0]

        # Reseta o menu, senão ele fica "preso" mostrando a última escolha
        try:
            await interaction.message.edit(view=GuildaPanelView())
        except Exception as e:
            print(f"Erro ao resetar o menu de guilda: {e}")

        await interaction.response.send_modal(CategoriaModal(categoria))


class GuildaPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GuildaDropdown())


class SupportDropdown(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=categoria, emoji=EMOJIS[categoria])
            for categoria in CATEGORIAS_MENU_PRINCIPAL
        ]
        super().__init__(
            placeholder="Selecione uma categoria de atendimento...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="support:dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        categoria = self.values[0]

        # Reseta o menu pro estado inicial, senão ele fica "preso" mostrando a última escolha
        # e a pessoa não consegue clicar na mesma categoria de novo.
        try:
            await interaction.message.edit(view=SupportPanelView())
        except Exception as e:
            print(f"Erro ao resetar o menu de suporte: {e}")

        await interaction.response.send_modal(CategoriaModal(categoria))


class SupportPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SupportDropdown())


class SupportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(SupportPanelView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(WhitelistPanelView())
        self.bot.add_view(WhitelistTicketView())
        self.bot.add_view(GuildaPanelView())
        self.bot.add_view(DoacaoPanelView())
        self.bot.add_view(EnvioDadosPanelView())

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Avisa dentro de qualquer ticket aberto do membro, caso ele saia do servidor."""
        guild = member.guild
        categorias_ids = set(config.CATEGORIAS_POR_TIPO.values())
        categorias_ids.add(config.SUPPORT_CATEGORY_ID)
        categorias_ids.discard(0)

        marcador = f":{member.id}"

        for categoria_id in categorias_ids:
            categoria = guild.get_channel(categoria_id)
            if not isinstance(categoria, discord.CategoryChannel):
                continue

            for canal in categoria.channels:
                if isinstance(canal, discord.TextChannel) and canal.topic and canal.topic.endswith(marcador):
                    embed = discord.Embed(
                        description=(
                            f"⚠️ **{member}** saiu do servidor Discord enquanto este chamado "
                            "ainda estava aberto."
                        ),
                        color=discord.Color.orange(),
                    )
                    try:
                        await canal.send(embed=embed)
                    except Exception as e:
                        print(f"Erro ao avisar saída no ticket {canal.name}: {e}")

    @commands.command(name="ticket_painel")
    @commands.has_permissions(administrator=True)
    async def ticket_painel(self, ctx: commands.Context):
        """Publica o painel de suporte com o menu de categorias."""
        embed, arquivo = embed_painel_suporte()
        if arquivo:
            await ctx.send(embed=embed, file=arquivo, view=SupportPanelView())
        else:
            await ctx.send(embed=embed, view=SupportPanelView())
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!ticket_painel): {e}")

    @commands.command(name="whitelist_painel")
    @commands.has_permissions(administrator=True)
    async def whitelist_painel(self, ctx: commands.Context):
        """Publica o painel dedicado de solicitação de whitelist."""
        await ctx.send(embed=embed_painel_whitelist(), view=WhitelistPanelView())
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!whitelist_painel): {e}")

    @commands.command(name="guilda_painel")
    @commands.has_permissions(administrator=True)
    async def guilda_painel(self, ctx: commands.Context):
        """Publica o painel dedicado de Chat de Guilda / Território de Guilda."""
        await ctx.send(embed=embed_painel_guilda(), view=GuildaPanelView())
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!guilda_painel): {e}")

    @commands.command(name="doacao_painel")
    @commands.has_permissions(administrator=True)
    async def doacao_painel(self, ctx: commands.Context):
        """Publica o painel dedicado de Doações."""
        await ctx.send(embed=embed_painel_doacao(), view=DoacaoPanelView())
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!doacao_painel): {e}")

    @commands.command(name="envio_dados_painel")
    @commands.has_permissions(administrator=True)
    async def envio_dados_painel(self, ctx: commands.Context):
        """Publica o painel dedicado de Envio de Dados."""
        await ctx.send(embed=embed_painel_envio_dados(), view=EnvioDadosPanelView())
        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!envio_dados_painel): {e}")

    @commands.command(name="criar_ticket")
    @commands.has_permissions(administrator=True)
    async def criar_ticket_manual(
        self, ctx: commands.Context, categoria: str, membro: discord.Member, *, motivo: str = None
    ):
        """Cria um ticket manualmente pra um membro específico, sem passar pelo painel.
        Ex: !criar_ticket Suporte @Fulano Motivo do chamado (opcional)"""
        if categoria not in PERGUNTAS:
            categorias_validas = ", ".join(PERGUNTAS.keys())
            await ctx.send(
                f"Categoria inválida. Use uma dessas (com o nome exato): {categorias_validas}",
                delete_after=15,
            )
            return

        categoria_discord = obter_categoria_discord(ctx.guild, categoria)
        if not categoria_discord:
            await ctx.send(
                "Categoria de ticket não configurada pra esse tipo (verifique o .env).", delete_after=10
            )
            return

        marcador = f"{categoria}:{membro.id}"
        for canal_existente in categoria_discord.channels:
            if isinstance(canal_existente, discord.TextChannel) and canal_existente.topic and canal_existente.topic.startswith(marcador):
                await ctx.send(
                    f"{membro.mention} já tem um chamado de **{categoria}** aberto: {canal_existente.mention}",
                    delete_after=10,
                )
                return

        nome_canal = _slug_canal(f"{categoria} ({membro.display_name})")[:90]

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            membro: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            ctx.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, manage_channels=True
            ),
        }
        if config.CARGOS_ADM_ID:
            for staff_role_id in config.CARGOS_ADM_ID:
                staff_role = ctx.guild.get_role(staff_role_id)
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )

        try:
            canal_ticket = await ctx.guild.create_text_channel(
                name=nome_canal,
                category=categoria_discord,
                overwrites=overwrites,
                topic=marcador,
            )

            respostas = []
            if motivo:
                respostas.append(("Motivo (aberto pela equipe)", motivo))

            view_do_ticket = WhitelistTicketView() if categoria == "Whitelist" else TicketControlView()
            await canal_ticket.send(
                embed=embed_boas_vindas_ticket(categoria, membro, respostas),
                view=view_do_ticket,
            )

            await ctx.send(
                f"✅ Ticket de **{categoria}** criado pra {membro.mention}: {canal_ticket.mention}",
                delete_after=10,
            )

            await send_log(
                self.bot, "Suporte: Aberto (manual)",
                f"Abriu manualmente um chamado de {categoria} pra {membro.mention}",
                user=ctx.author, cor=CORES_CATEGORIA.get(categoria), channel_id=config.LOG_ABERTOS_ID,
            )
        except Exception as e:
            await ctx.send(f"❌ Erro ao criar ticket: {e}", delete_after=15)
            return

        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!criar_ticket): {e}")

    @commands.command(name="fechar")
    @commands.has_permissions(administrator=True)
    async def fechar(self, ctx: commands.Context):
        """Encerra manualmente o chamado de suporte no canal atual."""
        categorias_validas = set(config.CATEGORIAS_POR_TIPO.values())
        categorias_validas.add(config.SUPPORT_CATEGORY_ID)
        categorias_validas.discard(0)

        eh_canal_de_ticket = (
            isinstance(ctx.channel, discord.TextChannel)
            and ctx.channel.category_id in categorias_validas
            and ctx.channel.topic
            and ":" in ctx.channel.topic
        )
        if eh_canal_de_ticket:
            await ctx.send("Encerrando chamado e arquivando logs...")
            await process_ticket_closure(self.bot, ctx.channel, ctx.author)


async def setup(bot):
    await bot.add_cog(SupportCog(bot))
