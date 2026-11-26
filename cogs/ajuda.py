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
    "criar_ticket": "Abre um ticket para um membro: `!criar_ticket Categoria @membro [motivo]`.",
    "fechar": "Fecha o ticket em que o comando for usado.",
    "guilda_lider": "Define o líder da guilda: `!guilda_lider @membro` no canal da guilda.",
    "whitelist_test": "Valida uma SteamID sem alterar a whitelist: `!whitelist_test <SteamID64>`.",
    "whitelist_add": "Adiciona uma SteamID ao Server 1: `!whitelist_add <SteamID64>`.",
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
}


class AjudaGlitnir(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        comandos = await self.filter_commands(self.context.bot.commands, sort=True)
        blocos = []
        for comando in comandos:
            descricao = DESCRICOES.get(comando.qualified_name, comando.short_doc or "Consulte os detalhes do comando.")
            blocos.append(f"`{self.context.clean_prefix}{comando.qualified_name}` — {descricao}")
        embeds = []
        atual = ""
        for linha in blocos:
            if len(atual) + len(linha) + 1 > 3500:
                embeds.append(discord.Embed(title="📖 Comandos de Glitnir", description=atual, color=config.COR_GLITNIR))
                atual = ""
            atual += linha + "\n"
        if atual:
            embeds.append(discord.Embed(title="📖 Comandos de Glitnir", description=atual, color=config.COR_GLITNIR))
        for embed in embeds:
            embed.set_footer(text="A lista mostra os comandos que você pode usar aqui. Use !help <comando> para detalhes.")
            await self.get_destination().send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
