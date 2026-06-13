from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from discord import AppEmoji, ButtonStyle, Color, GuildEmoji, Interaction, PartialEmoji, SeparatorSpacingSize
from discord.ui import ActionRow, BaseView, Button, Container, DesignerView, Section, TextDisplay, ViewItem

from songbird.utils import emojis
from songbird.utils.constants import Text
from songbird.utils.permissions import can_interact


class DeleteButton(Button[Any]):
    def __init__(self) -> None:
        super().__init__(label=Text.EMOJI_X)

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()


class _DirectionalButton(Button[Any]):
    def __init__(self, emoji: str | GuildEmoji | AppEmoji | PartialEmoji, view: BaseView) -> None:
        super().__init__(emoji=emoji)
        self.view = view

    async def callback(self, interaction: Interaction) -> None:
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
    components: Sequence[ViewItem[Any]],
    subtitle: str | None = None,
    color: Color | None = None,
) -> Container[Any]:
    container: Container[Any] = Container(color=color)

    header: Section[Any] = Section(TextDisplay(title), accessory=DeleteButton())
    if subtitle:
        header.add_text(subtitle)

    container.add_item(header)

    if components:
        container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)

    for component in components:
        container.add_item(component)

    return container


def generate_back_container(title: str, view: BaseView, components: Sequence[ViewItem[Any]], subtitle: str | None = None) -> Container[Any]:
    container: Container[Any] = Container(color=Color.red())

    header: Section[Any] = Section(TextDisplay(title), accessory=BackButton(view))
    if subtitle:
        header.add_text(subtitle)

    container.add_item(header)

    if components:
        container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)

    for component in components:
        container.add_item(component)

    return container


class _ConfirmActionButton(Button[Any]):
    def __init__(self, label: str, style: ButtonStyle, callback_fn: Callable[[Interaction], Awaitable[None]]) -> None:
        super().__init__(label=label, style=style)
        self._callback_fn = callback_fn

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            await self._callback_fn(interaction)


class ConfirmView(DesignerView):
    def __init__(
        self,
        prompt: str,
        confirm_callback: Callable[[Interaction], Awaitable[None]],
        cancel_callback: Callable[[Interaction], Awaitable[None]] | None = None,
        subtitle: str | None = None,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        timeout: int = 180,
    ) -> None:
        super().__init__(timeout=timeout)

        container: Container[Any] = Container(color=Color.red())
        header: Section[Any] = Section(TextDisplay(prompt), accessory=DeleteButton())
        if subtitle:
            header.add_text(subtitle)
        container.add_item(header)
        container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)
        self.add_item(container)

        self.add_item(
            ActionRow(
                _ConfirmActionButton(confirm_label, ButtonStyle.danger, confirm_callback),
                _ConfirmActionButton(cancel_label, ButtonStyle.secondary, cancel_callback or _default_cancel),
            )
        )


async def _default_cancel(interaction: Interaction) -> None:
    await interaction.response.defer()
    await interaction.delete_original_response()
