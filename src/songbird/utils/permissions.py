from discord import Interaction, Member


async def can_interact(interaction: Interaction) -> bool:
    if not interaction.message or not interaction.user or not interaction.message.interaction:
        return False

    can_interact = False

    if interaction.user.id == interaction.message.interaction.user.id:
        can_interact = True

    if isinstance(interaction.user, Member) and interaction.user.guild_permissions.manage_messages:
        can_interact = True

    if not can_interact:
        await interaction.response.send_message("You do not have permission to interact with this", ephemeral=True)
        return False

    return True
