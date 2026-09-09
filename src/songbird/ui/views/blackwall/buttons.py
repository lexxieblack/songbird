from collections.abc import Callable
from typing import Any

from discord import AllowedMentions, ButtonStyle, Interaction, TextChannel
from discord.ui import ActionRow, Button

from songbird.ui.views.blackwall.default_warning import BlackwallDefaultWarningView
from songbird.utils.permissions import can_interact


class _ActionButton(Button):
    def __init__(self, label: str, style: ButtonStyle, action: Callable[[Interaction], Any], disabled: bool = False) -> None:
        super().__init__(label=label, style=style, disabled=disabled)
        self._action = action

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            await self._action(interaction)


class _ButtonRow(ActionRow):
    def __init__(self, warning_url: str | None, channel_id: int | None) -> None:
        super().__init__()

        self.add_item(
            _ActionButton(
                "Default Message",
                ButtonStyle.primary,
                self._make_send_warning(warning_url, channel_id),
                disabled=channel_id is None,
            )
        )

    @staticmethod
    def _make_send_warning(warning_url: str | None, channel_id: int | None) -> Callable[[Interaction], Any]:
        async def _send_warning(interaction: Interaction) -> None:
            await interaction.response.defer()
            if channel_id is None:
                await interaction.followup.send("No blackwall channel is set.", ephemeral=True)
                return
            channel = interaction.client.get_channel(channel_id)
            if not isinstance(channel, TextChannel):
                await interaction.followup.send("The configured blackwall channel is unavailable.", ephemeral=True)
                return
            await channel.send(view=BlackwallDefaultWarningView(warning_url), allowed_mentions=AllowedMentions.none())
            await interaction.followup.send(f"Warning posted to <#{channel_id}>.", ephemeral=True)

        return _send_warning
