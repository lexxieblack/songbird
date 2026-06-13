import contextlib
from typing import Any

from discord import ButtonStyle, HTTPException, Interaction, Message
from discord.ui import Button, View, button

from songbird.utils.permissions import can_interact


class RestoreLinkView(View):
    def __init__(self, original_message: Message, cached_messages: set[int]):
        super().__init__(timeout=60)
        self.original_message = original_message
        self.cached_messages = cached_messages

    async def on_timeout(self) -> None:
        self.clear_items()
        await self.message.edit(view=self)

    @button(label="Restore", style=ButtonStyle.secondary, emoji="⬅️", id=127)
    async def restore(self, _: Button[Any], interaction: Interaction) -> None:
        if not can_interact(interaction):
            return

        await interaction.response.defer()

        with contextlib.suppress(HTTPException):
            self.cached_messages.discard(self.original_message.id)
            original = await self.original_message.channel.fetch_message(self.original_message.id)
            await original.edit(suppress=False)

        if interaction.message:
            with contextlib.suppress(HTTPException):
                await interaction.message.delete()
