# pyright: reportUnknownMemberType=false

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any

from discord import AppEmoji, ButtonStyle, Color, GuildEmoji, Interaction, NotFound, PartialEmoji, SeparatorSpacingSize
from discord.ui import ActionRow, BaseView, Button, Container, DesignerView, Section, TextDisplay, ViewItem

from songbird.utils import emojis
from songbird.utils.constants import SColor, Text
from songbird.utils.permissions import can_interact

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot

INVITE_LINK = "https://discord.com/oauth2/authorize?client_id="


class BotLinkRow(ActionRow[Any]):
    """Invite, source, issues, privacy and terms links shared by the about and help menus."""

    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__()

        invite_link = INVITE_LINK + str(bot.user.id) if bot.user else ""
        self.add_item(Button(label="Invite", url=invite_link, disabled=not bot.app_info.bot_public, style=ButtonStyle.url))

        source_link = bot.settings.bot.source_code_url
        self.add_item(Button(label="Source", url=source_link, disabled=not source_link))

        issues_link = bot.settings.bot.issues_url
        self.add_item(Button(label="Issues", url=issues_link, disabled=not issues_link))

        privacy_link = bot.settings.bot.privacy_policy_url
        self.add_item(Button(label="Privacy", url=privacy_link, disabled=not privacy_link))

        terms_link = bot.settings.bot.terms_of_service_url
        self.add_item(Button(label="Terms", url=terms_link, disabled=not terms_link))


class DeleteButton(Button[Any]):
    def __init__(self) -> None:
        super().__init__(label=Text.EMOJI_X)

    async def callback(self, interaction: Interaction) -> None:
        if not await can_interact(interaction):
            return
        await interaction.response.defer()
        await _delete_interaction_message(interaction)


async def _delete_interaction_message(interaction: Interaction) -> None:
    """Delete the message a component sits on, ephemeral or not."""
    if interaction.message is None:
        return
    try:
        if interaction.message.flags.ephemeral:
            # Ephemeral messages have no channel copy, so message.delete() returns 404.
            await interaction.delete_original_response()
        else:
            await interaction.message.delete()
    except NotFound:
        # Already gone, which is the outcome the callers want anyway.
        pass


class _DirectionalButton(Button[Any]):
    def __init__(self, emoji: str | GuildEmoji | AppEmoji | PartialEmoji, view: BaseView) -> None:
        super().__init__(emoji=emoji)
        self._target_view = view

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            await interaction.response.edit_message(view=self._target_view)


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
    color: Color = SColor.SONGBIRD,
) -> Container[Any]:
    container: Container[Any] = Container(color=color)

    header: Section[Any] = Section(TextDisplay(title), accessory=DeleteButton())
    if subtitle:
        header.add_text(subtitle)

    container.add_item(header)  # pyright: ignore[reportUnknownMemberType]

    if components:
        container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)

    for component in components:
        container.add_item(component)  # pyright: ignore[reportUnknownMemberType]

    return container


def generate_back_container(
    title: str,
    view: BaseView,
    components: Sequence[ViewItem[Any]],
    subtitle: str | None = None,
    color: Color = SColor.SONGBIRD,
) -> Container[Any]:
    container: Container[Any] = Container(color=color)

    header: Section[Any] = Section(TextDisplay(title), accessory=BackButton(view))
    if subtitle:
        header.add_text(subtitle)

    container.add_item(header)  # pyright: ignore[reportUnknownMemberType]

    if components:
        container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)

    for component in components:
        container.add_item(component)  # pyright: ignore[reportUnknownMemberType]

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
        color: Color = SColor.SONGBIRD,
    ) -> None:
        super().__init__(timeout=timeout)

        container: Container[Any] = Container(color=color)
        header: Section[Any] = Section(TextDisplay(prompt), accessory=DeleteButton())
        if subtitle:
            header.add_text(subtitle)
        container.add_item(header)  # pyright: ignore[reportUnknownMemberType]
        container.add_separator(divider=True, spacing=SeparatorSpacingSize.large)
        self.add_item(container)

        self.add_item(
            ActionRow(
                _ConfirmActionButton(confirm_label, ButtonStyle.danger, confirm_callback),
                _ConfirmActionButton(cancel_label, ButtonStyle.secondary, cancel_callback or _default_cancel),
            )  # pyright: ignore[reportUnknownArgumentType]
        )


async def _default_cancel(interaction: Interaction) -> None:
    await interaction.response.defer()
    await _delete_interaction_message(interaction)
