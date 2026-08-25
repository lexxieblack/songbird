from collections.abc import Callable
from typing import Any

from discord import ButtonStyle, Color, Interaction, SelectDefaultValue, SelectDefaultValueType
from discord.ui import ActionRow, Button, DesignerView, RoleSelect, Section, TextDisplay, ViewItem

from songbird.ui.custom_components import generate_container
from songbird.utils.constants import SColor
from songbird.utils.permissions import can_interact


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
        roles: list[int],
        banned_count: int | None,
        on_set_channel: Callable[[Interaction], Any],
        on_remove_channel: Callable[[Interaction], Any],
        on_edit_roles: Callable[[Interaction], Any],
    ):
        super().__init__(timeout=300)

        self.add_item(
            generate_container(
                title="## Blackwall",
                components=[
                    _make_channel_section(channel_id, on_set_channel, on_remove_channel),
                    _make_roles_section(roles, on_edit_roles),
                    _make_banned_count_section(banned_count or 0),
                ],
                color=Color(SColor.SONGBIRD),
            )
        )


class BlackwallEditRolesView(DesignerView):
    def __init__(
        self,
        current_roles: list[int],
        on_save: Callable[[Interaction], Any],
        on_cancel: Callable[[Interaction], Any],
    ) -> None:
        super().__init__(timeout=300)

        self.role_select = RoleSelect(  # type: ignore[type-var]
            placeholder="Select whitelisted roles",
            min_values=0,
            max_values=25,
            default_values=[SelectDefaultValue(id=r, type=SelectDefaultValueType.role) for r in current_roles],
        )
        self.role_select.callback = self._on_role_select  # type: ignore[method-assign]

        container = generate_container(
            title="## Edit Whitelisted Roles",
            components=[
                TextDisplay("Select the roles that should bypass the blackwall:"),
                ActionRow(self.role_select),
                ActionRow(
                    _ActionButton("Save", ButtonStyle.success, on_save),
                    _ActionButton("Cancel", ButtonStyle.secondary, on_cancel),
                ),
            ],
            color=Color(SColor.SONGBIRD),
        )
        self.add_item(container)

    @staticmethod
    async def _on_role_select(interaction: Interaction) -> None:
        if await can_interact(interaction):
            await interaction.response.defer()


class _ActionButton(Button):
    def __init__(self, label: str, style: ButtonStyle, action: Callable[[Interaction], Any]) -> None:
        super().__init__(label=label, style=style)
        self._action = action

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            await self._action(interaction)
