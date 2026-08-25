from datetime import datetime, timezone

import discord

import config

# Cor e ícone escolhidos automaticamente conforme palavras-chave no título do log
REGRAS_VISUAL = [
    (("aberto",), "🟢", discord.Color.green()),
    (("arquivado", "fechado", "encerrad"), "🗄️", discord.Color.orange()),
    (("erro", "falha"), "🔴", discord.Color.red()),
    (("online", "iniciado"), "⚡", discord.Color.blue()),
    (("transfer", "anfitrião", "dono"), "👑", discord.Color.gold()),
    (("permiss", "trancou", "trancad", "destrancou"), "🔒", discord.Color.dark_grey()),
]


def _estilo_para(titulo: str):
    titulo_lower = titulo.lower()
    for palavras, emoji, cor in REGRAS_VISUAL:
        if any(p in titulo_lower for p in palavras):
            return emoji, cor
    return "📋", config.COR_GLITNIR


async def send_log(bot, title: str, description: str, user=None, cor=None, channel_id=None):
    """Envia um log em formato de embed. Se `channel_id` não for passado, usa CANAL_LOG_ID."""
    destino = channel_id or config.CANAL_LOG_ID
    if not destino:
        return

    channel = bot.get_channel(destino)
    if not channel:
        try:
            channel = await bot.fetch_channel(destino)
        except Exception:
            return

    emoji, cor_automatica = _estilo_para(title)
    cor_final = cor if cor is not None else cor_automatica

    embed = discord.Embed(
        title=f"{emoji} {title}",
        description=description,
        color=cor_final,
        timestamp=datetime.now(timezone.utc),
    )

    if user:
        embed.set_author(name=str(user.display_name), icon_url=user.display_avatar.url)
    else:
        embed.set_author(name="Sistema")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao enviar log: {e}")