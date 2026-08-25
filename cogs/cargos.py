import discord
from discord import ui
from discord.ext import commands

import config


class CargoSelect(ui.Select):
    def __init__(self, cargos: list = None):
        if cargos:
            options = [
                discord.SelectOption(label=cargo.name, value=str(cargo.id))
                for cargo in cargos
            ]
        else:
            # Placeholder só pra permitir registrar a view persistente no on_ready.
            # Em uso real, a mensagem já enviada tem as opções de verdade.
            options = [discord.SelectOption(label="—", value="0")]

        super().__init__(
            placeholder="Escolha seus cargos...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="cargos:selecionar",
        )

    async def callback(self, interaction: discord.Interaction):
        selecionados = {int(v) for v in self.values}

        # Recupera todas as opções reais do menu direto da mensagem (funciona mesmo após restart do bot)
        todas_ids = set()
        for linha in interaction.message.components:
            for componente in linha.children:
                if getattr(componente, "custom_id", None) == "cargos:selecionar":
                    todas_ids = {int(opcao.value) for opcao in componente.options}

        atuais_ids = {cargo.id for cargo in interaction.user.roles}

        ids_pra_adicionar = selecionados - atuais_ids
        ids_pra_remover = (todas_ids - selecionados) & atuais_ids

        adicionados, removidos = [], []

        for cargo_id in ids_pra_adicionar:
            cargo = interaction.guild.get_role(cargo_id)
            if cargo:
                await interaction.user.add_roles(cargo)
                adicionados.append(cargo.name)

        for cargo_id in ids_pra_remover:
            cargo = interaction.guild.get_role(cargo_id)
            if cargo:
                await interaction.user.remove_roles(cargo)
                removidos.append(cargo.name)

        partes = []
        if adicionados:
            partes.append(f"✅ Adicionado: **{', '.join(adicionados)}**")
        if removidos:
            partes.append(f"❌ Removido: **{', '.join(removidos)}**")
        if not partes:
            partes.append("Nenhuma mudança.")

        await interaction.response.send_message("\n".join(partes), ephemeral=True)


class CargoPainelView(ui.View):
    def __init__(self, cargos: list = None):
        super().__init__(timeout=None)
        self.add_item(CargoSelect(cargos))


class Cargos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(CargoPainelView())

    @commands.command(name="cargo_painel")
    @commands.has_permissions(administrator=True)
    async def cargo_painel(self, ctx: commands.Context, titulo: str, descricao: str, cargos: commands.Greedy[discord.Role] = None):
        """Publica um menu de auto-atribuição de cargos. Ex: !cargo_painel "Título" "Descrição" @Cargo1 @Cargo2"""
        if not cargos:
            await ctx.send(
                'Menciona pelo menos um cargo! Ex: `!cargo_painel "Título" "Descrição" @Cargo1 @Cargo2`',
                delete_after=12,
            )
            return

        if len(cargos) > 25:
            await ctx.send("Máximo de 25 cargos por painel (limite do Discord).", delete_after=10)
            return

        embed = discord.Embed(title=titulo, description=descricao, color=config.COR_GLITNIR)
        await ctx.send(embed=embed, view=CargoPainelView(cargos))

        try:
            await ctx.message.delete()
        except Exception as e:
            print(f"Não consegui apagar a mensagem de comando (!cargo_painel): {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Cargos(bot))