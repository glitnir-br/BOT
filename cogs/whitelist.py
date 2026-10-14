import asyncio
import os
import re

import aiohttp
from discord.ext import commands


ARQUIVO_PADRAO = "/.config/unity3d/IronGate/Valheim/permittedlist.txt"
STEAM_ID64 = re.compile(r"^\d{17}$")


class Whitelist(commands.Cog):
    """Gerencia a whitelist do Valheim pelo Client API do Pterodactyl."""

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()

    @staticmethod
    def configuracao(servidor: str = "server_1"):
        """Retorna a configuracao do servidor escolhido.

        ``PTERODACTYL_SERVER_ID`` continua servindo como alias do Server 1 para
        instalacoes ja existentes. Para usar os dois servidores, configure
        PTERODACTYL_SERVER_1_ID e PTERODACTYL_SERVER_2_ID no .env.
        """
        ids = {
            "server_1": os.getenv("PTERODACTYL_SERVER_1_ID", "") or os.getenv("PTERODACTYL_SERVER_ID", ""),
            "server_2": os.getenv("PTERODACTYL_SERVER_2_ID", ""),
        }
        return {
            "panel": os.getenv("PTERODACTYL_URL", "").rstrip("/"),
            "api_key": os.getenv("PTERODACTYL_API_KEY", ""),
            "server_id": ids.get(servidor, ""),
            "arquivo": os.getenv("PTERODACTYL_WHITELIST_PATH", ARQUIVO_PADRAO),
        }

    @classmethod
    def configuracoes_servidores(cls):
        return {
            "server_1": ("Server 1", cls.configuracao("server_1")),
            "server_2": ("Server 2", cls.configuracao("server_2")),
        }

    @staticmethod
    def steam_id_valido(steam_id):
        return bool(STEAM_ID64.fullmatch(steam_id))

    @commands.command(name="whitelist_test")
    @commands.has_permissions(administrator=True)
    async def whitelist_test(self, ctx, steam_id: str):
        """Simula a inclusão sem fazer qualquer chamada à API."""
        if not self.steam_id_valido(steam_id):
            await ctx.send("SteamID inválida. Use uma SteamID64 com 17 dígitos.")
            return

        config = self.configuracao()
        servidor = config["server_id"] or "não configurado"
        await ctx.send(
            "🧪 **Teste de whitelist concluído**\n"
            f"SteamID validada: `{steam_id}`\n"
            f"Servidor Pterodactyl: `{servidor}`\n"
            f"Arquivo: `{config['arquivo']}`\n"
            "Nenhuma chamada à API foi feita e nenhum arquivo foi alterado."
        )

    @commands.command(name="whitelist_add")
    @commands.has_permissions(administrator=True)
    async def whitelist_add(self, ctx, steam_id: str):
        """Inclui uma SteamID64 no permittedlist.txt pelo Pterodactyl."""
        if not self.steam_id_valido(steam_id):
            await ctx.send("SteamID inválida. Use uma SteamID64 com 17 dígitos.")
            return

        config = self.configuracao()
        obrigatorios = ("panel", "api_key", "server_id")
        if any(not config[chave] for chave in obrigatorios):
            await ctx.send(
                "A integração Pterodactyl não está configurada. "
                "Defina PTERODACTYL_URL, PTERODACTYL_API_KEY e "
                "PTERODACTYL_SERVER_ID no .env."
            )
            return

        await ctx.typing()
        try:
            resultado = await self.adicionar_whitelist(steam_id, config)
        except aiohttp.ClientResponseError as erro:
            print(f"[Whitelist] Pterodactyl retornou HTTP {erro.status}.")
            await ctx.send("Não foi possível atualizar a whitelist no Pterodactyl.")
            return
        except (aiohttp.ClientError, asyncio.TimeoutError) as erro:
            print(f"[Whitelist] Erro de conexão: {erro}")
            await ctx.send("Não foi possível conectar ao Pterodactyl.")
            return

        await ctx.send(self.mensagem_resultado(resultado))

    @staticmethod
    def mensagem_resultado(resultado: str) -> str:
        return {
            "adicionado": "Jogador adicionado à whitelist.",
            "ja_existia": "Jogador já está na whitelist.",
        }.get(resultado, "Não foi possível atualizar a whitelist.")

    @staticmethod
    def configuracao_valida(config: dict) -> bool:
        return all(config[chave] for chave in ("panel", "api_key", "server_id"))

    async def verificar_servidores(self, steam_id: str) -> list[str]:
        """Retorna os nomes dos servidores cuja whitelist já contém a SteamID.

        Uma falha de leitura é propagada: quem preencheu o formulário não deve
        receber um resultado enganoso caso o painel esteja indisponível.
        """
        servidores = self.configuracoes_servidores()
        configurados = {
            chave: dados for chave, dados in servidores.items()
            if self.configuracao_valida(dados[1])
        }
        if len(configurados) != len(servidores):
            raise RuntimeError("Os dois servidores Pterodactyl precisam estar configurados.")

        resultados = await asyncio.gather(*(
            self.steam_id_esta_na_whitelist(steam_id, dados[1])
            for dados in configurados.values()
        ))
        return [
            servidores[chave][0]
            for (chave, _), encontrado in zip(configurados.items(), resultados)
            if encontrado
        ]

    async def steam_id_esta_na_whitelist(self, steam_id: str, config: dict) -> bool:
        linhas = await self._ler_whitelist(config)
        return steam_id in linhas

    async def _ler_whitelist(self, config: dict) -> list[str]:
        base = f'{config["panel"]}/api/client/servers/{config["server_id"]}/files'
        headers = {
            "Authorization": f'Bearer {config["api_key"]}',
            "Accept": "Application/vnd.pterodactyl.v1+json",
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{base}/contents", headers=headers, params={"file": config["arquivo"]}
            ) as resposta:
                resposta.raise_for_status()
                return (await resposta.text()).splitlines()

    async def adicionar_whitelist(self, steam_id, config):
        base = f'{config["panel"]}/api/client/servers/{config["server_id"]}/files'
        headers = {
            "Authorization": f'Bearer {config["api_key"]}',
            "Accept": "Application/vnd.pterodactyl.v1+json",
        }
        timeout = aiohttp.ClientTimeout(total=15)

        async with self._lock:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{base}/contents", headers=headers, params={"file": config["arquivo"]}
                ) as resposta:
                    resposta.raise_for_status()
                    linhas = (await resposta.text()).splitlines()

                if steam_id in linhas:
                    return "ja_existia"

                conteudo = "\n".join([*linhas, steam_id]) + "\n"
                headers["Content-Type"] = "text/plain"
                async with session.post(
                    f"{base}/write",
                    headers=headers,
                    params={"file": config["arquivo"]},
                    data=conteudo.encode("utf-8"),
                ) as resposta:
                    resposta.raise_for_status()

        print(f"[Whitelist] SteamID adicionada: {steam_id[-4:].rjust(17, '*')}")
        return "adicionado"

    @whitelist_test.error
    @whitelist_add.error
    async def comando_erro(self, ctx, erro):
        if isinstance(erro, commands.MissingPermissions):
            await ctx.send("Apenas administradores podem usar este comando.")
            return
        if isinstance(erro, commands.MissingRequiredArgument):
            await ctx.send("Uso: `!whitelist_test <SteamID64>` ou `!whitelist_add <SteamID64>`")
            return
        raise erro


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
