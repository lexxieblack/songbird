from discord import Interaction


async def can_interact(interaction: Interaction, author_id: int | None = None) -> bool:
    """Allow only the user who owns the message to use its components.

    Pass `author_id` explicitly for messages that are not interaction responses (e.g. a plain channel send),
    since those carry no interaction metadata.
    """
    message = interaction.message
    if author_id is None and message is not None:
        metadata = message.interaction_metadata
        if metadata is not None:
            author_id = metadata.user.id
        else:
            legacy = message.interaction  # deprecated fallback for older payloads
            author_id = legacy.user.id if legacy is not None else None

    if author_id is None or interaction.user is None or interaction.user.id != author_id:
        await interaction.response.send_message("You do not have permission to interact with this", ephemeral=True)
        return False

    return True
