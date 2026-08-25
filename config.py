import os
from zoneinfo import ZoneInfo

import discord
from dotenv import load_dotenv

load_dotenv()

def _int_env(nome: str) -> int:
    """Lê uma variável de ambiente como int, tratando ausente ou vazia como 0."""
    valor = os.getenv(nome, "0").strip()
    return int(valor) if valor else 0


def _int_list_env(nome: str) -> list:
    """Lê uma variável de ambiente com IDs separados por vírgula, retornando uma lista de int."""
    valor = os.getenv(nome, "").strip()
    if not valor:
        return []
    return [int(item.strip()) for item in valor.split(",") if item.strip()]


TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_ID = _int_env("DISCORD_ID")
CHAT_GERAL_ID = _int_env("CHAT_GERAL_ID")
CHAT_VOZ_ID = _int_env("CHAT_VOZ_ID")
BEM_VINDO_ID = _int_env("BEM_VINDO_ID")
APRESENTESE_ID = _int_env("APRESENTESE_ID")
SUPPORT_CATEGORY_ID = _int_env("SUPPORT_CATEGORY_ID")  # categoria fallback se o tipo de ticket não tiver uma própria
CARGOS_ADM_ID = _int_list_env("CARGOS_ADM_ID")  # um ou mais cargos que enxergam todo ticket criado
CARGO_WHITELIST_ID = _int_env("CARGO_WHITELIST_ID")  # cargo concedido ao aprovar um ticket de whitelist
CANAL_LOG_ID = _int_env("CANAL_LOG_ID")  # log geral (usado como fallback pros dois abaixo, e por outros logs do bot)
LOG_ABERTOS_ID = _int_env("LOG_ABERTOS_ID") or CANAL_LOG_ID
LOG_FECHADOS_ID = _int_env("LOG_FECHADOS_ID") or CANAL_LOG_ID

# Categoria do Discord onde cada tipo de ticket cria seu canal.
# Se um tipo não tiver variável preenchida no .env, cai no SUPPORT_CATEGORY_ID acima.
CATEGORIAS_POR_TIPO = {
    "Dúvidas": _int_env("CATEGORIA_DUVIDAS_ID"),
    "Suporte": _int_env("CATEGORIA_SUPORTE_ID"),
    "Doações": _int_env("CATEGORIA_DOACOES_ID"),
    "Whitelist": _int_env("CATEGORIA_WHITELIST_ID"),
    "Chat de Guilda": _int_env("CATEGORIA_CHAT_GUILDA_ID"),
    "Território de Guilda": _int_env("CATEGORIA_TERRITORIO_GUILDA_ID"),
    "Envio de Dados": _int_env("CATEGORIA_ENVIO_DADOS_ID"),
}

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")

COR_GLITNIR = discord.Color.from_str("#17e0d6")