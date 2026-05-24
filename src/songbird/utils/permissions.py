from discord import Interaction


async def can_interact(interaction: Interaction) -> bool:
    if not interaction.message or not interaction.user or not interaction.message.interaction:
        return False

    if interaction.user.id != interaction.message.interaction.user.id:
        await interaction.response.send_message("You do not have permission to interact with this", ephemeral=True)
        return False

    return True
