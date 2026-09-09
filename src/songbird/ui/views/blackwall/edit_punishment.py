from collections.abc import Callable
from typing import Any

from discord import ButtonStyle, Color, Interaction, MediaGalleryItem, SelectOption
from discord.ui import ActionRow, DesignerView, MediaGallery, Select, Separator, TextDisplay

from songbird.config import Settings
from songbird.models.management.blackwall import BlackwallPunishment
from songbird.ui.custom_components import generate_container
from songbird.ui.views.blackwall.buttons import _ActionButton
from songbird.utils.permissions import can_interact


class BlackwallEditPunishmentView(DesignerView):
    def __init__(
        self,
        current_punishment: BlackwallPunishment,
        on_save: Callable[[Interaction], Any],
        on_cancel: Callable[[Interaction], Any],
        settings: Settings,
    ) -> None:
        super().__init__(timeout=300)

        self.punishment_select = Select(
            placeholder="Select punishment",
            min_values=1,
            max_values=1,
            options=[SelectOption(label=punishment.value.title(), value=punishment.value) for punishment in BlackwallPunishment],
        )
        self.punishment_select.callback = self._on_punishment_select  # type: ignore[method-assign]

        components = []

        if settings.blackwall.image_url:
            components.append(MediaGallery(MediaGalleryItem(url=settings.blackwall.image_url)))
            components.append(Separator(divider=False))

        components.extend(
            [
                TextDisplay(
                    f"What should happen when an unauthorised user posts in the blackwall channel? (Current: **{current_punishment.value}**)"
                ),
                ActionRow(self.punishment_select),
                ActionRow(
                    _ActionButton("Save", ButtonStyle.success, on_save),
                    _ActionButton("Cancel", ButtonStyle.secondary, on_cancel),
                ),
            ]
        )

        self.add_item(generate_container(title="## Edit Punishment", components=components, color=Color.red()))

    @staticmethod
    async def _on_punishment_select(interaction: Interaction) -> None:
        if await can_interact(interaction):
            await interaction.response.defer()
