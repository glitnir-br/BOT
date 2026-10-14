"""Teste isolado, somente leitura, da integração de whitelist Pterodactyl."""

import os
import re
import sys

import aiohttp
import asyncio
from dotenv import load_dotenv


STEAM_ID_DE_TESTE = "76561198000000000"
ARQUIVO_PADRAO = "/.config/unity3d/IronGate/Valheim/permittedlist.txt"
STEAM_ID64 = re.compile(r"^\d{17}$")


async def main():
    load_dotenv()
    panel = os.getenv("PTERODACTYL_URL", "").rstrip("/")
    api_key = os.getenv("PTERODACTYL_API_KEY", "")
    server_id = os.getenv("PTERODACTYL_SERVER_ID", "")
    arquivo = os.getenv("PTERODACTYL_WHITELIST_PATH", ARQUIVO_PADRAO)
    steam_id = os.getenv("PTERODACTYL_TEST_STEAM_ID", "").strip()
    gravar = os.getenv("PTERODACTYL_TEST_WRITE", "").strip().lower() == "true"

    if not all((panel, api_key, server_id)):
        print(
            "Configuracao ausente: PTERODACTYL_URL, PTERODACTYL_API_KEY e "
            "PTERODACTYL_SERVER_ID sao obrigatorias."
        )
        return 1

    url = f"{panel}/api/client/servers/{server_id}/files/contents"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "Application/vnd.pterodactyl.v1+json",
    }

    print("Consultando o arquivo de whitelist (somente leitura)...")
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url, headers=headers, params={"file": arquivo}
            ) as resposta:
                conteudo = await resposta.text()
                resposta.raise_for_status()
    except aiohttp.ClientResponseError as erro:
        print(f"Falha: Pterodactyl respondeu HTTP {erro.status}.")
        return 1
    except (aiohttp.ClientError, asyncio.TimeoutError) as erro:
        print(f"Falha de conexao: {erro}")
        return 1

    linhas = conteudo.splitlines()
    steam_ids_existentes = {linha.strip() for linha in linhas if linha.strip()}
    print("Conexao com Pterodactyl confirmada.")
    print(f"Arquivo acessado: {arquivo}")
    print(f"Entradas na whitelist: {len(steam_ids_existentes)}")

    if not steam_id:
        steam_id = STEAM_ID_DE_TESTE
        print("Usando a SteamID ficticia padrao para consulta.")

    if not STEAM_ID64.fullmatch(steam_id):
        print("PTERODACTYL_TEST_STEAM_ID deve conter uma SteamID64 de 17 digitos.")
        return 1

    if steam_id in steam_ids_existentes:
        print("SteamID encontrada na whitelist.")
        print("Nenhum arquivo foi alterado.")
    elif not gravar:
        print("SteamID nao encontrada na whitelist.")
        print("Teste somente leitura: nenhum arquivo foi alterado.")
    else:
        # Preserva todo o conteudo original e somente acrescenta a nova ID.
        separador = "" if not conteudo or conteudo.endswith("\n") else "\n"
        novo_conteudo = f"{conteudo}{separador}{steam_id}\n"
        headers["Content-Type"] = "text/plain"
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{panel}/api/client/servers/{server_id}/files/write",
                    headers=headers,
                    params={"file": arquivo},
                    data=novo_conteudo.encode("utf-8"),
                ) as resposta:
                    resposta.raise_for_status()
        except aiohttp.ClientResponseError as erro:
            print(f"Falha ao gravar: Pterodactyl respondeu HTTP {erro.status}.")
            return 1
        except (aiohttp.ClientError, asyncio.TimeoutError) as erro:
            print(f"Falha de conexao ao gravar: {erro}")
            return 1
        print("SteamID adicionada a whitelist com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
