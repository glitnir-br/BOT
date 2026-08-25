import os
import random

import discord
from discord.ext import commands, tasks

import config
from utils import storage

DATA_FILE = "voice_rooms.json"

COR_INFO = discord.Color.blurple()
COR_SUCESSO = discord.Color.green()
COR_ERRO = discord.Color.red()

# Caminho da imagem do embed de boas-vindas — coloque um arquivo em assets/sala.png
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
IMAGEM_SALA = os.path.join(ASSETS_DIR, "sala.png")


def embed_simples(descricao: str, cor: discord.Color) -> discord.Embed:
    return discord.Embed(description=descricao, color=cor)


def montar_embed_boas_vindas(member: discord.Member):
    embed = discord.Embed(
        title="⚔️ Bem-vindo à Fogueira de Glitnir!",
        description=(
            "**Saudações, Viking!**\n"
            "Este é o seu refúgio temporário para organizar expedições e compartilhar "
            "histórias. Utilize este espaço conforme as **Diretrizes desta Comunidade**!\n\n"
            "**⚔️ Gerenciamento da Fogueira**\n"
            "✦ ✏️ - **Renomear**: Altera o nome deste canal de voz.\n"
            "✦ 🔒 - **Trancar/Destrancar**: Alterna entre fechar ou abrir a entrada de novos Vikings.\n"
            "✦ 👥 - **Limite**: Define o número máximo de participantes no canal de voz.\n"
            "✦ 👑 - **Anfitrião**: Transfere as opções de gestão da call para outro Viking.\n\n"
            "Caso o anfitrião se retire, eu irei transferir as opções de gestão "
            "aleatoriamente a outro Viking. O canal será desfeito assim que o "
            "último Viking deixar a fogueira.\n\n"
            "Trate seus companheiros(as) com dignidade. Navegue com bom senso."
        ),
        color=COR_INFO,
    )

    arquivo = None
    if os.path.exists(IMAGEM_SALA):
        arquivo = discord.File(IMAGEM_SALA, filename="sala.png")
        embed.set_image(url="attachment://sala.png")

    return embed, arquivo


def embed_novo_dono(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title="👑 Novo anfitrião da fogueira",
        description=f"{member.mention} agora é o anfitrião desta sala e pode usar os botões de gestão.",
        color=COR_INFO,
    )
    return embed


class RenomearModal(discord.ui.Modal, title="Renomear sala"):
    novo_nome = discord.ui.TextInput(label="Novo nome da sala", max_length=100)

    def __init__(self, cog: "VoiceRooms"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.channel
        if self.cog.salas.get(canal.id) != interaction.user.id:
            await interaction.response.send_message(
                embed=embed_simples("Só o anfitrião da sala pode fazer isso.", COR_ERRO), ephemeral=True
            )
            return
        await canal.edit(name=str(self.novo_nome))
        await interaction.response.send_message(
            embed=embed_simples(f"Sala renomeada pra **{self.novo_nome}**.", COR_SUCESSO), ephemeral=True
        )


class LimiteModal(discord.ui.Modal, title="Definir limite de participantes"):
    quantidade = discord.ui.TextInput(label="Quantidade (0 = sem limite)", max_length=2, placeholder="ex: 5")

    def __init__(self, cog: "VoiceRooms"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.channel
        if self.cog.salas.get(canal.id) != interaction.user.id:
            await interaction.response.send_message(
                embed=embed_simples("Só o anfitrião da sala pode fazer isso.", COR_ERRO), ephemeral=True
            )
            return
        try:
            valor = int(str(self.quantidade))
        except ValueError:
            await interaction.response.send_message(
                embed=embed_simples("Digite um número válido.", COR_ERRO), ephemeral=True
            )
            return
        if valor < 0 or valor > 99:
            await interaction.response.send_message(
                embed=embed_simples("Escolhe um número entre 0 (sem limite) e 99.", COR_ERRO), ephemeral=True
            )
            return
        await canal.edit(user_limit=valor)
        texto = "Limite de participantes removido." if valor == 0 else f"Limite ajustado pra **{valor}** participantes."
        await interaction.response.send_message(embed=embed_simples(texto, COR_SUCESSO), ephemeral=True)


class TransferirSelect(discord.ui.Select):
    def __init__(self, cog: "VoiceRooms", canal: discord.VoiceChannel):
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in canal.members
            if not m.bot
        ]
        super().__init__(placeholder="Escolha o novo anfitrião...", options=options, min_values=1, max_values=1)
        self.cog = cog
        self.canal = canal

    async def callback(self, interaction: discord.Interaction):
        novo_dono_id = int(self.values[0])
        novo_dono = interaction.guild.get_member(novo_dono_id)

        self.cog.salas[self.canal.id] = novo_dono_id
        self.cog._salvar()

        await interaction.response.edit_message(
            content=f"Você transferiu a liderança pra **{novo_dono.display_name}**.", view=None
        )
        await self.canal.send(embed=embed_novo_dono(novo_dono))


class TransferirView(discord.ui.View):
    def __init__(self, cog: "VoiceRooms", canal: discord.VoiceChannel):
        super().__init__(timeout=60)
        self.add_item(TransferirSelect(cog, canal))


class RoomControlView(discord.ui.View):
    def __init__(self, cog: "VoiceRooms"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _checar_dono(self, interaction: discord.Interaction) -> bool:
        if self.cog.salas.get(interaction.channel.id) != interaction.user.id:
            await interaction.response.send_message(
                embed=embed_simples("Só o anfitrião da sala pode usar esse botão.", COR_ERRO), ephemeral=True
            )
            return False
        return True

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.danger, custom_id="salas:trancar")
    async def trancar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._checar_dono(interaction):
            return
        canal = interaction.channel
        overwrite_atual = canal.overwrites_for(interaction.guild.default_role)
        trancada = overwrite_atual.connect is False

        overwrites = canal.overwrites
        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(connect=trancada)
        await canal.edit(overwrites=overwrites)

        msg = "🔓 Sala destrancada." if trancada else "🔒 Sala trancada."
        await interaction.response.send_message(embed=embed_simples(msg, COR_SUCESSO), ephemeral=True)

    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.primary, custom_id="salas:renomear")
    async def renomear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._checar_dono(interaction):
            return
        await interaction.response.send_modal(RenomearModal(self.cog))

    @discord.ui.button(emoji="👥", style=discord.ButtonStyle.secondary, custom_id="salas:limite")
    async def limite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._checar_dono(interaction):
            return
        await interaction.response.send_modal(LimiteModal(self.cog))

    @discord.ui.button(emoji="👑", style=discord.ButtonStyle.success, custom_id="salas:anfitriao")
    async def anfitriao_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._checar_dono(interaction):
            return
        canal = interaction.channel
        outros = [m for m in canal.members if m.id != interaction.user.id and not m.bot]
        if not outros:
            await interaction.response.send_message(
                embed=embed_simples("Não tem mais ninguém na call pra transferir a liderança.", COR_ERRO),
                ephemeral=True,
            )
            return
        view = TransferirView(self.cog, canal)
        await interaction.response.send_message(
            "Escolha quem vai ser o novo anfitrião:", view=view, ephemeral=True
        )


class VoiceRooms(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        dados = storage.load_json(DATA_FILE, default={"salas": {}})
        # salas: { channel_id (int): owner_id (int) }
        self.salas = {int(k): v for k, v in dados.get("salas", {}).items()}

    def _salvar(self):
        storage.save_json(DATA_FILE, {"salas": {str(k): v for k, v in self.salas.items()}})

    @commands.Cog.listener()
    async def on_ready(self):
        # Registra a view como persistente (funciona nos botões mesmo após restart do bot)
        self.bot.add_view(RoomControlView(self))

        # Limpa salas órfãs (já vazias ou apagadas manualmente enquanto o bot estava offline)
        for sala_id in list(self.salas.keys()):
            canal = self.bot.get_channel(sala_id)
            if canal is None:
                self.salas.pop(sala_id, None)
                continue
            if len(canal.members) == 0:
                await canal.delete()
                self.salas.pop(sala_id, None)
        self._salvar()

        if not self.limpeza_periodica.is_running():
            self.limpeza_periodica.start()

    def cog_unload(self):
        self.limpeza_periodica.cancel()

    @tasks.loop(minutes=2)
    async def limpeza_periodica(self):
        """
        Rede de segurança: mesmo que o bot perca o controle das salas (ex: reset
        do voice_rooms.json após uma atualização na hospedagem), essa checagem
        periódica apaga qualquer sala vazia dentro da categoria do canal gatilho,
        exceto o próprio canal gatilho.
        """
        canal_gatilho = self.bot.get_channel(config.CHAT_VOZ_ID)
        if not canal_gatilho or not canal_gatilho.category:
            return

        for canal in canal_gatilho.category.voice_channels:
            if canal.id == canal_gatilho.id:
                continue
            if not canal.name.startswith("Sala de "):
                continue  # só mexe em salas criadas pelo bot, nunca em canais fixos da categoria
            if len(canal.members) == 0:
                try:
                    await canal.delete()
                except Exception as e:
                    print(f"Erro na limpeza periódica de salas: {e}")
                self.salas.pop(canal.id, None)

        self._salvar()

    @limpeza_periodica.before_loop
    async def before_limpeza_periodica(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Entrou no canal-gatilho -> cria uma sala nova e move o membro pra ela
        if after.channel and after.channel.id == config.CHAT_VOZ_ID:
            categoria = after.channel.category
            nova_sala = await member.guild.create_voice_channel(
                name=f"Sala de {member.display_name}",
                category=categoria,
                position=after.channel.position + 1,
            )
            await member.move_to(nova_sala)  # move primeiro, o resto pode esperar

            self.salas[nova_sala.id] = member.id
            self._salvar()

            embed, arquivo = montar_embed_boas_vindas(member)
            if arquivo:
                await nova_sala.send(embed=embed, file=arquivo, view=RoomControlView(self))
            else:
                await nova_sala.send(embed=embed, view=RoomControlView(self))

        # Saiu de uma sala temporária
        if before.channel and before.channel.id in self.salas:
            sala_id = before.channel.id
            membros_restantes = before.channel.members

            if len(membros_restantes) == 0:
                # Sala vazia -> apaga
                await before.channel.delete()
                self.salas.pop(sala_id, None)
                self._salvar()
            elif self.salas.get(sala_id) == member.id:
                # O anfitrião saiu mas ainda tem gente -> passa a sala pra alguém aleatório
                novo_dono = random.choice(membros_restantes)
                self.salas[sala_id] = novo_dono.id
                self._salvar()
                await before.channel.send(embed=embed_novo_dono(novo_dono))


async def setup(bot):
    await bot.add_cog(VoiceRooms(bot))