# PingBot

Bot modular pro servidor Glitnir (Valheim) com:
- `!ping` → responde `pong`
- Aviso automático toda sexta 19h (horário de Brasília) de boss liberado
- `!boss` → dispara o aviso manualmente
- Sistema de salas de voz automáticas (join to create)

## Estrutura

```
pingbot/
├── main.py              # entry point — monta o bot e carrega os cogs
├── config.py            # variáveis de ambiente e constantes
├── cogs/
│   ├── ping.py          # comando !ping
│   ├── boss_reminder.py # aviso semanal + comando !boss
│   └── voice_rooms.py   # salas de voz automáticas
├── .env.example
└── requirements.txt
```

## Setup

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

2. Copie `.env.example` para `.env` e preencha os valores:
   ```
   cp .env.example .env
   ```

3. No Developer Portal (aba **Bot**), ative:
   - **MESSAGE CONTENT INTENT**
   - **SERVER MEMBERS INTENT**

4. No servidor, garanta que o bot tem as permissões: Enviar Mensagens, Gerenciar Canais, Mover Membros.

5. Rode o bot:
   ```
   python main.py
   ```

## Adicionando novas funcionalidades

Cada funcionalidade nova vira um arquivo em `cogs/`, seguindo o padrão:

```python
from discord.ext import commands

class MinhaFeature(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(MinhaFeature(bot))
```

E adiciona o caminho `"cogs.meu_arquivo"` na lista `EXTENSIONS` do `main.py`.

## Importante

- **Nunca** comite o `.env` no git (já está no `.gitignore`).
- Se o token vazar em algum momento (chat, print, etc.), resete-o no Developer Portal.

