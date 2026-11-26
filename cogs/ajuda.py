import discord
from discord.ext import commands

import config

DESCRICOES = {
    "help": "Mostra esta ajuda ou os detalhes de um comando.",
    "ping": "Verifica a resposta do bot.",
    "ticket_painel": "Publica o painel de tickets.",
    "whitelist_painel": "Publica o painel de solicitações de whitelist.",
    "guilda_painel": "Publica o painel de guildas.",
    "doacao_painel": "Publica o painel de doações.",
    "vip_painel": "Publica o painel VIP.",
    "envio_dados_painel": "Publica o painel de envio de dados.",
    "criar_ticket": "Abre ticket para um membro: `!criar_ticket \"Envio de Dados\" @membro [motivo]`. Use aspas em categorias com espaços.",
    "fechar": "Fecha o ticket em que o comando for usado.",
    "guilda_lider": "Define o líder da guilda: `!guilda_lider @membro` no canal da guilda.",
    "whitelist_test": "Valida o formato da SteamID e mostra a configuração local, sem testar a conexão: `!whitelist_test <SteamID64>`.",
    "whitelist_add": "Adiciona diretamente ao Server 1, sem consultar banimentos: `!whitelist_add <SteamID64>`.",
    "remover_cargo_whitelist": "Remove o cargo de whitelist dos membros após confirmação.",
    "guia_modpack": "Publica o guia do modpack no canal configurado.",
    "painel_modpack": "Publica o painel de atualização do código do modpack.",
    "painel_mensagens": "Publica o painel de envio imediato de mensagens.",
    "regras": "Publica o códice de regras neste canal.",
    "text": "Publica um texto ou imagem em um card: `!text [mensagem]`.",
    "editar": "Edita um card enviado pelo bot: `!editar <ID da mensagem> <texto>`.",
    "cargo_painel": "Cria um painel de cargos: `!cargo_painel \"Título\" \"Descrição\" @cargo`.",
    "anunciar": "Anuncia canais pelos IDs: `!anunciar <ID> [outros IDs]`.",
    "testar_boasvindas": "Testa a mensagem de boas-vindas.",
    "painel_apresentacao": "Publica a mensagem de reação para receber o cargo inicial.",
}

CATEGORIAS_AJUDA = {
    "📋 Painéis": (
        "ticket_painel", "whitelist_painel", "guilda_painel", "doacao_painel",
        "vip_painel", "envio_dados_painel", "painel_mensagens", "painel_modpack", "cargo_painel", "painel_apresentacao",
    ),
    "🛡️ Gestão": ("criar_ticket", "fechar", "guilda_lider", "remover_cargo_whitelist", "whitelist_add"),
    "📢 Publicações": ("guia_modpack", "regras", "text", "editar", "anunciar"),
}


class AjudaGlitnir(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        comandos = await self.filter_commands(self.context.bot.commands, sort=True)
        disponiveis = {comando.qualified_name: comando for comando in comandos}
        secoes = []
        for titulo, nomes in CATEGORIAS_AJUDA.items():
            linhas = [f"`{self.context.clean_prefix}{nome}` — {DESCRICOES[nome]}"
                      for nome in nomes if nome in disponiveis]
            if linhas:
                secoes.append((titulo, "\n".join(linhas)))
        if not secoes:
            await self.get_destination().send("Não há comandos administrativos disponíveis para você neste canal.")
            return
        embed = discord.Embed(title="📖 Comandos de Glitnir", color=config.COR_GLITNIR)
        for titulo, texto in secoes:
            embed.add_field(name=titulo, value=texto, inline=False)
        embed.set_footer(text="Comandos de administração disponíveis aqui. Use !help <comando> para detalhes.")
        await self.get_destination().send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
