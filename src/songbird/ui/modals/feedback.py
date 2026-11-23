from discord import Bot, InputTextStyle, Interaction
from discord.ui import InputText, Modal

from songbird.models.feedback.exceptions import NotForumChannel, ThreadNotFoundError
from songbird.services.container import ServiceContainer, create_feedback_service, get_session
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class FeedbackModal(Modal):
    def __init__(self, services: ServiceContainer, bot: Bot) -> None:
        super().__init__(title="Submit Feedback")
        self.services = services
        self.bot = bot
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

        # Acknowledge within the 3s window; thread creation and the DB can be slow.
        await interaction.response.defer(ephemeral=True)

        # The modal outlives the command's request scope, so it needs its own session.
        async with get_session(self.services) as session:
            feedback_service = create_feedback_service(session, self.services, self.bot)
            try:
                delivered = await feedback_service.send_feedback(interaction.user.id, interaction.user.name, text)
            except (NotForumChannel, ThreadNotFoundError):
                await interaction.followup.send("Error: feedback channel not set up properly", ephemeral=True)
                return

        if delivered:
            await interaction.followup.send("Feedback sent successfully!", ephemeral=True)
        else:
            await interaction.followup.send("Could not deliver your feedback. Please try again later.", ephemeral=True)
