from collections.abc import Callable
from typing import Any

from discord import (
    ButtonStyle,
    Color,
    Interaction,
    MediaGalleryItem,
)
from discord.ui import (
    DesignerView,
    MediaGallery,
    Section,
    Separator,
    TextDisplay,
    ViewItem,
)

from songbird.config import Settings
from songbird.models.management.blackwall import BlackwallPunishment
from songbird.ui.custom_components import generate_container
from songbird.ui.views.blackwall.buttons import _ActionButton, _ButtonRow


def _make_channel_section(
    channel_id: int | None,
    on_set: Callable[[Interaction], Any],
    on_remove: Callable[[Interaction], Any],
) -> ViewItem:
    if channel_id:
        text = f"<#{channel_id}>"
        button = _ActionButton("Remove", ButtonStyle.danger, on_remove)
    else:
        text = "*Not Set*"
        button = _ActionButton("Set", ButtonStyle.success, on_set)

    return Section(TextDisplay(f"**Channel:** {text}"), accessory=button)


def _make_log_channel_section(
    channel_id: int | None,
    on_set: Callable[[Interaction], Any],
    on_remove: Callable[[Interaction], Any],
) -> ViewItem:
    if channel_id:
        text = f"<#{channel_id}>"
        button = _ActionButton("Remove", ButtonStyle.danger, on_remove)
    else:
        text = "*Not Set*"
        button = _ActionButton("Set", ButtonStyle.success, on_set)

    return Section(TextDisplay(f"**Log Channel:** {text}"), accessory=button)


def _make_roles_section(roles: list[int] | None, on_edit: Callable[[Interaction], Any]) -> ViewItem:
    roles_text = " ".join(f"<@&{r}>" for r in roles) if roles else "*Admins only*"
    button = _ActionButton("Edit", ButtonStyle.primary, on_edit)
    return Section(TextDisplay(f"**Allowed Roles:** {roles_text}"), accessory=button)


def _make_punishment_section(punishment: BlackwallPunishment, on_edit: Callable[[Interaction], Any]) -> ViewItem:
    button = _ActionButton("Change", ButtonStyle.primary, on_edit)
    return Section(TextDisplay(f"**Punishment:** {punishment.value.title()}"), accessory=button)


def _make_banned_count_section(banned_count: int | None) -> ViewItem:
    return TextDisplay(f"**Trigger Count:** {banned_count}")


class BlackwallView(DesignerView):
    def __init__(
        self,
        channel_id: int | None,
        log_channel_id: int | None,
        roles: list[int],
        banned_count: int | None,
        punishment: BlackwallPunishment,
        on_set_channel: Callable[[Interaction], Any],
        on_remove_channel: Callable[[Interaction], Any],
        on_set_log_channel: Callable[[Interaction], Any],
        on_remove_log_channel: Callable[[Interaction], Any],
        on_edit_roles: Callable[[Interaction], Any],
        on_edit_punishment: Callable[[Interaction], Any],
        settings: Settings,
    ):
        super().__init__(timeout=300)

        components = []

        if settings.blackwall.image_url:
            components.append(MediaGallery(MediaGalleryItem(url=settings.blackwall.image_url)))
            components.append(Separator(divider=False))

        components.extend(
            [
                _make_channel_section(channel_id, on_set_channel, on_remove_channel),
                _make_log_channel_section(log_channel_id, on_set_log_channel, on_remove_log_channel),
                _make_roles_section(roles, on_edit_roles),
                _make_punishment_section(punishment, on_edit_punishment),
                _make_banned_count_section(banned_count or 0),
                Separator(),
                _ButtonRow(settings.blackwall.warning_url, channel_id),
            ]
        )

        self.add_item(generate_container(title="## Blackwall", components=components, color=Color.red()))
