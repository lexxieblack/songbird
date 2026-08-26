from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from discord import ButtonStyle, Color, Interaction, MediaGalleryItem, Member, Message, SelectDefaultValue, SelectDefaultValueType
from discord.ui import (
    ActionRow,
    Button,
    Container,
    DesignerView,
    MediaGallery,
    RoleSelect,
    Section,
    Separator,
    TextDisplay,
    Thumbnail,
    ViewItem,
)

from songbird.config import Settings
from songbird.ui.custom_components import generate_container
from songbird.utils.permissions import can_interact
from songbird.utils.text import format_code_block, humanize_timedelta


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


def _make_banned_count_section(banned_count: int | None) -> ViewItem:
    return TextDisplay(f"**Users Banned:** {banned_count}")


class BlackwallView(DesignerView):
    def __init__(
        self,
        channel_id: int | None,
        log_channel_id: int | None,
        roles: list[int],
        banned_count: int | None,
        on_set_channel: Callable[[Interaction], Any],
        on_remove_channel: Callable[[Interaction], Any],
        on_set_log_channel: Callable[[Interaction], Any],
        on_remove_log_channel: Callable[[Interaction], Any],
        on_edit_roles: Callable[[Interaction], Any],
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
                _make_banned_count_section(banned_count or 0),
            ]
        )

        self.add_item(generate_container(title="## Blackwall", components=components, color=Color.red()))


class BlackwallEditRolesView(DesignerView):
    def __init__(
        self,
        current_roles: list[int],
        on_save: Callable[[Interaction], Any],
        on_cancel: Callable[[Interaction], Any],
        settings: Settings,
    ) -> None:
        super().__init__(timeout=300)

        self.role_select = RoleSelect(  # type: ignore[type-var]
            placeholder="Select whitelisted roles",
            min_values=0,
            max_values=25,
            default_values=[SelectDefaultValue(id=r, type=SelectDefaultValueType.role) for r in current_roles],
        )
        self.role_select.callback = self._on_role_select  # type: ignore[method-assign]

        components = []

        if settings.blackwall.image_url:
            components.append(MediaGallery(MediaGalleryItem(url=settings.blackwall.image_url)))
            components.append(Separator(divider=False))

        components.extend(
            [
                TextDisplay("Select the roles that should bypass the blackwall:"),
                ActionRow(self.role_select),
                ActionRow(
                    _ActionButton("Save", ButtonStyle.success, on_save),
                    _ActionButton("Cancel", ButtonStyle.secondary, on_cancel),
                ),
            ]
        )

        self.add_item(generate_container(title="## Edit Whitelisted Roles", components=components, color=Color.red()))

    @staticmethod
    async def _on_role_select(interaction: Interaction) -> None:
        if await can_interact(interaction):
            await interaction.response.defer()


class BlackwallLogView(DesignerView):
    def __init__(self, member: Member, message: Message) -> None:
        super().__init__()

        container = Container()

        container.add_item(
            Section(
                TextDisplay("## Blackwall Ban"),
                TextDisplay(f"**User:** {member.mention}"),
                TextDisplay(f"**Username:** {member.name}"),
                accessory=Thumbnail(url=member.display_avatar.url),
            )
        )

        container.add_item(TextDisplay(f"**Account Age:** {humanize_timedelta(datetime.now(UTC) - member.created_at)}"))
        if member.joined_at:
            container.add_item(TextDisplay(f"**Joined Server:** {humanize_timedelta(datetime.now(UTC) - member.joined_at)}"))
        if len(member.roles) > 1:
            container.add_item(
                TextDisplay(f"**Roles:** {', '.join(role.mention for role in member.roles if role.id != member.guild.id)}")
            )

        container.add_separator()

        container.add_item(TextDisplay(f"**Message:**\n{format_code_block(message.content)}"))

        self.add_item(container)


class _ActionButton(Button):
    def __init__(self, label: str, style: ButtonStyle, action: Callable[[Interaction], Any]) -> None:
        super().__init__(label=label, style=style)
        self._action = action

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            await self._action(interaction)
