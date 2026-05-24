
from discord import InputTextStyle, Interaction
from discord.ui import InputText, Modal

from songbird.models.feedback.exceptions import NotForumChannel
from songbird.services.feedback import FeedbackService
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class FeedbackModal(Modal):
    def __init__(self, feedback_service: FeedbackService) -> None:
        super().__init__(title="Submit Feedback")
        self.feedback_service = feedback_service
        self.text = InputText(
            label="Message to send",
            placeholder="Enter the message you want to send...",
            style=InputTextStyle.paragraph,
            min_length=1,
            max_length=4000,
        )

        self.add_item(self.text)

    async def callback(self, interaction: Interaction) -> None:
        text = self.text.value
        if not text:
            return

        if not interaction.user:
            return

        try:
            await self.feedback_service.send_feedback(interaction.user.id, interaction.user.name, text)
        except NotForumChannel:
            await interaction.response.send_message("Error: feedback channel not set up properly", ephemeral=True)
            return

        await interaction.response.send_message("Feedback sent successfully!", ephemeral=True)
