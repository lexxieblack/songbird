import contextlib
from typing import Any

from discord import ButtonStyle, HTTPException, Interaction, Message
from discord.ui import Button, View, button

from songbird.utils.permissions import can_interact


class RestoreLinkView(View):
    def __init__(self, original_message: Message, cached_messages: set[int], fixed_messages: list[Message] | None = None):
        super().__init__(timeout=60)
        self.original_message = original_message
        self.cached_messages = cached_messages
        self.fixed_messages = fixed_messages or []

    async def on_timeout(self) -> None:
        self.clear_items()
        if isinstance(self.message, Message):
            await self.message.edit(view=self)

    @button(label="Restore", style=ButtonStyle.secondary, emoji="⬅️", id=127)
    async def restore(self, _: Button[Any], interaction: Interaction) -> None:
        if not await can_interact(interaction):
            return

        await interaction.response.defer()

        with contextlib.suppress(HTTPException):
            self.cached_messages.discard(self.original_message.id)
            original = await self.original_message.channel.fetch_message(self.original_message.id)
            await original.edit(suppress_embeds=False)

        for fixed_message in self.fixed_messages:
            with contextlib.suppress(HTTPException):
                await fixed_message.delete()
