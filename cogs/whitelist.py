import asyncio
import os
import re

import aiohttp
import discord
from discord.ext import commands

import config

ARQUIVO_PADRAO = "/.config/unity3d/IronGate/Valheim/permittedlist.txt"
ARQUIVO_BANIDOS_PADRAO = "/.config/unity3d/IronGate/Valheim/bannedlist.txt"
STEAM_ID64 = re.compile(r"^\d{17}$")


class ConfirmarRemocao(discord.ui.View):
    def __init__(self, autor_id):
        super().__init__(timeout=60)
        self.autor_id = autor_id
        self.confirmado = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.autor_id or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Apenas o administrador que iniciou o comando pode confirmar ou cancelar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmar remoção", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction, button):
        self.confirmado = True
        self.stop()
        await interaction.response.edit_message(content="Remoção confirmada. Processando...", view=None)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction, button):
        self.stop()
        await interaction.response.edit_message(content="Remoção cancelada. Nenhum cargo foi removido.", view=None)


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
            "arquivo_banidos": os.getenv("PTERODACTYL_BANLIST_PATH", ARQUIVO_BANIDOS_PADRAO),
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

    @commands.command(name="remover_cargo_whitelist")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.max_concurrency(1, per=commands.BucketType.guild)
    async def remover_cargo_whitelist(self, ctx):
        """Retira o cargo de whitelist de todos os membros do servidor."""
        cargo = ctx.guild.get_role(config.CARGO_WHITELIST_ID)
        if not cargo:
            await ctx.send("Cargo de whitelist não encontrado. Verifique CARGO_WHITELIST_ID no .env.")
            return
        if cargo.is_default() or cargo.managed or not ctx.guild.me.guild_permissions.manage_roles or cargo >= ctx.guild.me.top_role:
            await ctx.send("Não posso remover esse cargo. Verifique a permissão Gerenciar Cargos e a hierarquia do bot.")
            return

        await ctx.send("Buscando membros com o cargo de whitelist. Isso pode levar algum tempo.")
        try:
            membros = [membro async for membro in ctx.guild.fetch_members(limit=None) if cargo in membro.roles]
        except discord.HTTPException:
            await ctx.send("Não foi possível obter a lista completa de membros. Nenhum cargo foi removido.")
            return

        if not membros:
            await ctx.send("Nenhum membro possui o cargo de whitelist.")
            return
        confirmacao = ConfirmarRemocao(ctx.author.id)
        mensagem = await ctx.send(
            f"Remover o cargo **{discord.utils.escape_markdown(cargo.name)}** de **{len(membros)}** membro(s)? "
            "Esta ação não altera as whitelists dos servidores. Confirme em até 60 segundos.",
            view=confirmacao,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        expirou = await confirmacao.wait()
        if expirou:
            await mensagem.edit(content="Confirmação expirada. Nenhum cargo foi removido.", view=None)
            return
        if not confirmacao.confirmado:
            return

        removidos = 0
        falhas = 0
        for membro in membros:
            try:
                await membro.remove_roles(cargo, reason=f"Remoção de whitelist solicitada por {ctx.author} ({ctx.author.id})")
                removidos += 1
            except discord.HTTPException as erro:
                falhas += 1
                print(f"[Whitelist] Falha ao remover cargo do membro {membro.id}: {erro}")
        await ctx.send(f"Remoção concluída: **{removidos}** cargo(s) removido(s); **{falhas}** falha(s).")

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

    async def verificar_banimentos(self, steam_id: str) -> list[str]:
        """Retorna os servidores cuja lista de banidos contém a SteamID."""
        servidores = self.configuracoes_servidores()
        configurados = {
            chave: dados for chave, dados in servidores.items()
            if self.configuracao_valida(dados[1])
        }
        if len(configurados) != len(servidores):
            raise RuntimeError("Os dois servidores Pterodactyl precisam estar configurados.")

        resultados = await asyncio.gather(*(
            self.steam_id_esta_banida(steam_id, dados[1])
            for dados in configurados.values()
        ))
        return [
            servidores[chave][0]
            for (chave, _), encontrado in zip(configurados.items(), resultados)
            if encontrado
        ]

    async def steam_id_esta_na_whitelist(self, steam_id: str, config: dict) -> bool:
        linhas = await self._ler_arquivo(config, config["arquivo"])
        return steam_id in linhas

    async def steam_id_esta_banida(self, steam_id: str, config: dict) -> bool:
        linhas = await self._ler_arquivo(config, config["arquivo_banidos"])
        return steam_id in linhas

    async def _ler_arquivo(self, config: dict, arquivo: str) -> list[str]:
        base = f'{config["panel"]}/api/client/servers/{config["server_id"]}/files'
        headers = {
            "Authorization": f'Bearer {config["api_key"]}',
            "Accept": "Application/vnd.pterodactyl.v1+json",
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{base}/contents", headers=headers, params={"file": arquivo}
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
    @remover_cargo_whitelist.error
    async def comando_erro(self, ctx, erro):
        if isinstance(erro, commands.MissingPermissions):
            await ctx.send("Apenas administradores podem usar este comando.")
            return
        if isinstance(erro, commands.MissingRequiredArgument):
            await ctx.send("Uso: `!whitelist_test <SteamID64>` ou `!whitelist_add <SteamID64>`")
            return
        if isinstance(erro, commands.NoPrivateMessage):
            await ctx.send("Este comando só pode ser usado em um servidor.")
            return
        if isinstance(erro, commands.MaxConcurrencyReached):
            await ctx.send("Já existe uma remoção de cargos em andamento.")
            return
        raise erro


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
