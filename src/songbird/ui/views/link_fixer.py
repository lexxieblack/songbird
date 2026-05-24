import contextlib

from discord import ButtonStyle, HTTPException, Interaction, Message
from discord.ui import ActionRow, Button, DesignerView, TextDisplay, button

from songbird.utils.text import link


class ButtonRow(ActionRow):
    def __init__(self, original_message: Message):
        super().__init__(id=127)
        self.original_message = original_message

    @button(label="Restore", style=ButtonStyle.red)
    async def delete_button(self, _: Button, interaction: Interaction):
        if interaction.user.id != self.original_message.author.id:  # type: ignore
            await interaction.response.send_message("❌ Only the person who posted the links can restore them!", ephemeral=True)
            return

        await interaction.response.defer()

        with contextlib.suppress(HTTPException):
            await self.original_message.edit(suppress_embeds=False)

        if interaction.message:
            with contextlib.suppress(HTTPException):
                await interaction.message.delete()


class RestoreView(DesignerView):
    def __init__(self, links: list[str], original_message: Message):
        super().__init__(timeout=120)
        for i, url in enumerate(links, 1):
            self.add_item(TextDisplay(link(str(i), url)))
        self.add_item(ButtonRow(original_message=original_message))

    async def on_timeout(self):
        self.remove_item(127)
        await self.message.edit(view=self)  # type: ignore
