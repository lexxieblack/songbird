from typing import Any

from discord import Color, Interaction
from discord.ui import Button, DesignerView, Section, TextDisplay

from songbird.services.container import (
    ServiceContainer,
    create_private_conversation_service,
    get_session,
)
from songbird.ui.custom_components import ConfirmView, ForwardButton, generate_container
from songbird.ui.modals.info import UserInfoModal
from songbird.utils import emojis
from songbird.utils.permissions import can_interact


class EditUserInfoButton(Button[Any]):
    def __init__(self, services: ServiceContainer) -> None:
        super().__init__(emoji=emojis.ARROW_RIGHT)
        self.services = services

    async def callback(self, interaction: Interaction) -> None:
        if await can_interact(interaction):
            modal = await UserInfoModal.create(interaction.user.id, self.services)  # type: ignore
            await interaction.response.send_modal(modal)


class ManageView(DesignerView):
    def __init__(self, services: ServiceContainer):
        super().__init__(timeout=180)
        self.services = services

        self.components: list[Section[Any]] = [
            Section(
                TextDisplay("### Reset Conversation"),
                TextDisplay("-# Clear all conversation history"),
                accessory=ForwardButton(view=_make_reset_confirm_view(self)),
            ),
            Section(
                TextDisplay("### Delete Last Message"),
                TextDisplay("-# Remove the last message from you or the AI"),
                accessory=ForwardButton(view=_make_delete_last_confirm_view(self)),
            ),
            Section(
                TextDisplay("### Edit User Info"),
                TextDisplay("-# Edit your context information for the AI"),
                accessory=EditUserInfoButton(services=self.services),
            ),
        ]

        self.add_item(
            generate_container(
                title="## Management Panel",
                components=self.components,
            )
        )


def _make_reset_confirm_view(manage_view: ManageView) -> ConfirmView:
    services = manage_view.services

    async def on_confirm(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            async with get_session(services) as session:
                conversation_service = create_private_conversation_service(session, services)
                deleted_count = await conversation_service.delete_all_messages(interaction.user.id)  # type: ignore
        except Exception:
            await interaction.followup.send("Failed to delete conversation history.", ephemeral=True)
            return
        await interaction.edit_original_response(
            view=_make_success_view("Conversation Reset", f"Deleted {deleted_count} messages."),
        )

    async def on_cancel(interaction: Interaction) -> None:
        await interaction.response.edit_message(view=manage_view)

    return ConfirmView(
        prompt="### Are you sure you want to reset your conversation?",
        subtitle="This will permanently delete all your conversation history.",
        confirm_callback=on_confirm,
        cancel_callback=on_cancel,
        confirm_label="Reset",
    )


def _make_delete_last_confirm_view(manage_view: ManageView) -> ConfirmView:
    services = manage_view.services

    async def on_confirm(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            async with get_session(services) as session:
                conversation_service = create_private_conversation_service(session, services)
                await conversation_service.delete_last_message(interaction.user.id)  # type: ignore
        except Exception:
            await interaction.followup.send("Failed to delete last message.", ephemeral=True)
            return
        await interaction.edit_original_response(
            view=_make_success_view("Message Deleted", "The last message has been removed."),
        )

    async def on_cancel(interaction: Interaction) -> None:
        await interaction.response.edit_message(view=manage_view)

    return ConfirmView(
        prompt="### Delete the last message?",
        subtitle="This will remove the most recent message from you or the AI.",
        confirm_callback=on_confirm,
        cancel_callback=on_cancel,
        confirm_label="Delete",
    )


def _make_success_view(title: str, description: str) -> DesignerView:
    view = DesignerView(timeout=180)
    view.add_item(
        generate_container(
            title=f"## {title}",
            subtitle=description,
            components=[],
            color=Color.green(),
        )
    )
    return view
