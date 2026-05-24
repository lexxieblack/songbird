import contextlib

from discord import ButtonStyle, HTTPException, Interaction, Member, Message
from discord.ui import Button, View, button


class RestoreLinkView(View):
    def __init__(self, original_message: Message, cached_messages: set[int]):
        super().__init__(timeout=120)
        self.original_message = original_message
        self.cached_messages = cached_messages

    @button(label="Restore", style=ButtonStyle.secondary, emoji="⬅️")
    async def retore(self, _: Button, interaction: Interaction) -> None:
        if not interaction.user:
            return

        if (
            interaction.user.id != self.original_message.author.id
            or isinstance(interaction.user, Member)
            and not interaction.user.guild_permissions.manage_messages
        ):
            await interaction.response.send_message("❌ Only the person who posted the links can restore them!", ephemeral=True)
            return

        await interaction.response.defer()

        with contextlib.suppress(HTTPException):
            self.cached_messages.discard(self.original_message.id)
            original = await self.original_message.channel.fetch_message(self.original_message.id)
            await original.edit(suppress=False)

        if interaction.message:
            with contextlib.suppress(HTTPException):
                await interaction.message.delete()
