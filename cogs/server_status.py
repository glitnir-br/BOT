import a2s
import requests
import time
import json
import os

from datetime import datetime, timezone
from dotenv import load_dotenv


# =========================
# CARREGA .ENV
# =========================

load_dotenv()


# =========================
# CONFIGURAÇÕES
# =========================

SERVER_IP = "177.54.147.114"

# IMPORTANTE:
# Se 24666 for a porta usada para entrar no Valheim,
# normalmente a porta de QUERY será 24667.
QUERY_PORT = 24667

WEBHOOK_URL = os.getenv("STATUS_WEBHOOK_URL")

# Atualização a cada 60 segundos
INTERVALO = 60

# Arquivo usado para lembrar qual mensagem deve ser editada
MESSAGE_FILE = "status_message.json"


# =========================
# CONSULTA DO VALHEIM
# =========================

def consultar_servidor():

    endereco = (
        SERVER_IP,
        QUERY_PORT
    )

    try:

        info = a2s.info(
            endereco,
            timeout=5
        )

        return {
            "online": True,
            "nome": info.server_name,
            "jogadores": info.player_count,
            "max_jogadores": info.max_players,
            "ping": round(info.ping * 1000)
        }

    except Exception as erro:

        print("")
        print("❌ Não foi possível consultar o servidor.")
        print(f"IP: {SERVER_IP}")
        print(f"Query Port: {QUERY_PORT}")
        print(f"Erro: {erro}")
        print("")

        return {
            "online": False
        }


# =========================
# MESSAGE ID
# =========================

def carregar_message_id():

    if not os.path.exists(MESSAGE_FILE):
        return None

    try:

        with open(
            MESSAGE_FILE,
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(arquivo)

            return dados.get("message_id")

    except Exception as erro:

        print(
            f"⚠️ Erro ao carregar ID da mensagem: {erro}"
        )

        return None


def salvar_message_id(message_id):

    try:

        with open(
            MESSAGE_FILE,
            "w",
            encoding="utf-8"
        ) as arquivo:

            json.dump(
                {
                    "message_id": message_id
                },
                arquivo,
                indent=4
            )

    except Exception as erro:

        print(
            f"⚠️ Erro ao salvar ID da mensagem: {erro}"
        )


# =========================
# EMBED
# =========================

def criar_embed(status):

    agora = datetime.now(
        timezone.utc
    ).isoformat()

    # =========================
    # ONLINE
    # =========================

    if status["online"]:

        jogadores = status["jogadores"]
        max_jogadores = status["max_jogadores"]
        ping = status["ping"]

        return {

            "title": "⚔️ GLITNIR",

            "description": (
                "🟢 **Servidor Online**"
            ),

            "color": 5763719,

            "fields": [

                {
                    "name": "👥 Jogadores",
                    "value": (
                        f"**{jogadores} / "
                        f"{max_jogadores}**"
                    ),
                    "inline": True
                },

                {
                    "name": "📡 Ping",
                    "value": (
                        f"**{ping} ms**"
                    ),
                    "inline": True
                }

            ],

            "footer": {
                "text": (
                    "Glitnir • Status automático"
                )
            },

            "timestamp": agora
        }

    # =========================
    # OFFLINE
    # =========================

    return {

        "title": "⚔️ GLITNIR",

        "description": (
            "🔴 **Servidor Offline**"
        ),

        "color": 15548997,

        "footer": {
            "text": (
                "Glitnir • Status automático"
            )
        },

        "timestamp": agora
    }


# =========================
# CRIAR MENSAGEM
# =========================

def criar_mensagem(embed):

    try:

        resposta = requests.post(

            f"{WEBHOOK_URL}?wait=true",

            json={
                "embeds": [embed]
            },

            timeout=10
        )

        if resposta.status_code not in [
            200,
            201
        ]:

            print(
                "❌ Erro ao criar mensagem:"
            )

            print(
                resposta.status_code,
                resposta.text
            )

            return None

        dados = resposta.json()

        message_id = dados["id"]

        salvar_message_id(
            message_id
        )

        print(
            f"✅ Mensagem criada: {message_id}"
        )

        return message_id

    except Exception as erro:

        print(
            f"❌ Erro ao enviar mensagem: {erro}"
        )

        return None


# =========================
# EDITAR MENSAGEM
# =========================

def editar_mensagem(
    message_id,
    embed
):

    try:

        url = (
            f"{WEBHOOK_URL}"
            f"/messages/"
            f"{message_id}"
        )

        resposta = requests.patch(

            url,

            json={
                "embeds": [embed]
            },

            timeout=10
        )

        # Mensagem atualizada normalmente
        if resposta.status_code in [
            200,
            204
        ]:

            print(
                "🔄 Status atualizado."
            )

            return True

        # Mensagem não existe mais
        if resposta.status_code == 404:

            print(
                "⚠️ Mensagem antiga não existe mais."
            )

            return False

        print(
            "❌ Não foi possível editar a mensagem."
        )

        print(
            resposta.status_code,
            resposta.text
        )

        return False

    except Exception as erro:

        print(
            f"❌ Erro ao editar mensagem: {erro}"
        )

        return False


# =========================
# DISCORD
# =========================

def atualizar_discord(status):

    embed = criar_embed(
        status
    )

    message_id = carregar_message_id()

    # Já temos uma mensagem
    if message_id:

        sucesso = editar_mensagem(
            message_id,
            embed
        )

        if sucesso:
            return

        print(
            "🔄 Criando uma nova mensagem..."
        )

    # Não existe mensagem ou foi apagada
    criar_mensagem(
        embed
    )


# =========================
# VERIFICA CONFIGURAÇÃO
# =========================

def verificar_configuracao():

    if not WEBHOOK_URL:

        print("")
        print(
            "❌ STATUS_WEBHOOK_URL não encontrado no .env"
        )
        print("")

        return False

    return True


# =========================
# MAIN
# =========================

def main():

    if not verificar_configuracao():
        return

    print("")
    print("============================")
    print("⚔️ GLITNIR SERVER STATUS")
    print("============================")
    print(f"IP: {SERVER_IP}")
    print(f"Query Port: {QUERY_PORT}")
    print(
        f"Atualização: {INTERVALO}s"
    )
    print("============================")
    print("")

    while True:

        try:

            status = consultar_servidor()

            if status["online"]:

                print(
                    "🟢 ONLINE | "
                    f'{status["jogadores"]}/'
                    f'{status["max_jogadores"]} '
                    "jogadores | "
                    f'{status["ping"]}ms'
                )

            else:

                print(
                    "🔴 OFFLINE"
                )

            atualizar_discord(
                status
            )

        except Exception as erro:

            print(
                f"❌ Erro inesperado: {erro}"
            )

        time.sleep(
            INTERVALO
        )


# =========================
# INICIAR
# =========================

if __name__ == "__main__":
    main()