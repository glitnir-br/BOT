import a2s
import requests
import time
from datetime import datetime

# =========================
# CONFIGURAÇÕES
# =========================

SERVER_IP = "177.54.147.114"

# Se o servidor usa a porta padrão 2456,
# normalmente a query será 2457.
QUERY_PORT = 24666

WEBHOOK_URL = "https://discord.com/api/webhooks/1543025206900162743/BtumFilpjzt7jyVCQ0nadpaLfsdEFz8ZRC-dEQnve1iwSf6M05U7L5NDYy3CLh7YaMne"

# Atualização em segundos
INTERVALO = 60


# =========================
# CONSULTA DO VALHEIM
# =========================

def consultar_servidor():
    endereco = (SERVER_IP, QUERY_PORT)

    try:
        info = a2s.info(endereco, timeout=5)

        return {
            "online": True,
            "nome": info.server_name,
            "jogadores": info.player_count,
            "max_jogadores": info.max_players,
            "ping": round(info.ping * 1000)
        }

    except Exception as erro:
        print(f"Erro ao consultar servidor: {erro}")

        return {
            "online": False
        }


# =========================
# ENVIA PARA O DISCORD
# =========================

def enviar_discord(status):

    if status["online"]:

        embed = {
            "title": "⚔️ GLITNIR",
            "description": "🟢 **Servidor Online**",
            "color": 5763719,

            "fields": [
                {
                    "name": "👥 Jogadores",
                    "value": f'**{status["jogadores"]} / {status["max_jogadores"]}**',
                    "inline": True
                },
                {
                    "name": "📡 Ping",
                    "value": f'**{status["ping"]} ms**',
                    "inline": True
                }
            ],

            "footer": {
                "text": "Glitnir • Status automático"
            },

            "timestamp": datetime.utcnow().isoformat()
        }

    else:

        embed = {
            "title": "⚔️ GLITNIR",
            "description": "🔴 **Servidor Offline**",
            "color": 15548997,

            "footer": {
                "text": "Glitnir • Status automático"
            },

            "timestamp": datetime.utcnow().isoformat()
        }

    requests.post(
        WEBHOOK_URL,
        json={
            "embeds": [embed]
        }
    )


# =========================
# LOOP
# =========================

while True:

    status = consultar_servidor()

    print(status)

    enviar_discord(status)

    time.sleep(INTERVALO)