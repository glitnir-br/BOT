import os

import discord

from utils import storage

DATA_FILE = "image_cache.json"


async def obter_url_cacheada(bot, caminho_arquivo: str, filename: str, canal_id: int):
    """
    Retorna uma URL de imagem já hospedada no Discord, subindo o arquivo só na
    primeira vez. Da segunda vez em diante, busca a mesma mensagem de novo pra
    gerar um link fresco (os links de anexo do Discord expiram depois de um
    tempo) — sem precisar reenviar o arquivo, só mais rápido que subir de novo.
    """
    if not os.path.exists(caminho_arquivo):
        return None

    tamanho_atual = os.path.getsize(caminho_arquivo)
    cache = storage.load_json(DATA_FILE, default={})
    entrada = cache.get(caminho_arquivo)

    # Se já tem no cache e o arquivo não mudou de tamanho, tenta reaproveitar a mensagem
    if entrada and entrada.get("tamanho") == tamanho_atual:
        canal_cache = bot.get_channel(entrada.get("canal_id", 0))
        if canal_cache:
            try:
                mensagem = await canal_cache.fetch_message(entrada["mensagem_id"])
                if mensagem.attachments:
                    return mensagem.attachments[0].url
            except Exception as e:
                print(f"Cache de imagem inválido pra {caminho_arquivo}, vou reenviar: {e}")
                # segue pro fluxo de reenvio abaixo

    if not canal_id:
        return None

    canal = bot.get_channel(canal_id)
    if not canal:
        return None

    try:
        arquivo = discord.File(caminho_arquivo, filename=filename)
        mensagem = await canal.send(file=arquivo)
    except Exception as e:
        print(f"Erro ao cachear imagem {caminho_arquivo}: {e}")
        return None

    if not mensagem.attachments:
        return None

    url = mensagem.attachments[0].url
    cache[caminho_arquivo] = {
        "canal_id": canal.id,
        "mensagem_id": mensagem.id,
        "tamanho": tamanho_atual,
    }
    storage.save_json(DATA_FILE, cache)
    return url