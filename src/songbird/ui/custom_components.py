from collections.abc import Sequence

from discord import AppEmoji, Color, GuildEmoji, Interaction, PartialEmoji, SeparatorSpacingSize
from discord.ui import BaseView, Button, Container, Section, TextDisplay, ViewItem

from songbird.utils import emojis
from songbird.utils.constants import Text
from songbird.utils.permissions import can_interact


class DeleteButton(Button):
    def __init__(self):
        super().__init__(label=Text.EMOJI_X)

    async def callback(self, interaction: Interaction):
        if await can_interact(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()


class _DirectionalButton(Button):
    def __init__(self, emoji: str | GuildEmoji | AppEmoji | PartialEmoji, view: BaseView):
        super().__init__(emoji=emoji)
        self.view = view

    async def callback(self, interaction: Interaction):
        if await can_interact(interaction):
            await interaction.response.edit_message(view=self.view)


class BackButton(_DirectionalButton):
    def __init__(self, view: BaseView):
        super().__init__(emoji=emojis.ARROW_LEFT, view=view)


class ForwardButton(_DirectionalButton):
    def __init__(self, view: BaseView):
        super().__init__(emoji=emojis.ARROW_RIGHT, view=view)


def generate_container(
    title: str,
    components: Sequence[ViewItem],
    subtitle: str | None = None,
    color: Color | None = None,
) -> Container:
    container = Container(color=color)

    header = Section(TextDisplay(title), accessory=DeleteButton())
    if subtitle:
        header.add_text(subtitle)

    container.add_item(header)
    container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)

    for component in components:
        container.add_item(component)

    return container


def generate_back_container(title: str, view: BaseView, components: Sequence[ViewItem], subtitle: str | None = None) -> Container:
    container = Container(color=Color.red())

    header = Section(TextDisplay(title), accessory=BackButton(view))
    if subtitle:
        header.add_text(subtitle)

    container.add_item(header)
    container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)

    for component in components:
        container.add_item(component)

    return container
