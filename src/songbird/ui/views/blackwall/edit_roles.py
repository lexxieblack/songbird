from collections.abc import Callable
from typing import Any

from discord import ButtonStyle, Color, Interaction, MediaGalleryItem, SelectDefaultValue, SelectDefaultValueType
from discord.ui import ActionRow, DesignerView, MediaGallery, RoleSelect, Separator, TextDisplay

from songbird.config import Settings
from songbird.ui.custom_components import generate_container
from songbird.ui.views.blackwall.buttons import _ActionButton
from songbird.utils.permissions import can_interact


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
