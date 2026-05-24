from discord import InputTextStyle, Interaction
from discord.ui import InputText, Modal

from songbird.models.chat.exceptions import UserInfoNotFoundError
from songbird.services.container import ServiceContainer, get_session, get_user_info_repo
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class UserInfoModal(Modal):
    def __init__(self, services: ServiceContainer, user_info: str | None = None) -> None:
        super().__init__(title="Edit your information")
        self.services = services

        self.info_text = InputText(
            label="Information to memorize",
            placeholder="Enter the text you want memorized...",
            style=InputTextStyle.paragraph,
            min_length=1,
            max_length=1000,
            value=user_info,
        )

        self.add_item(self.info_text)

    @classmethod
    async def create(cls, user_id: int, services: ServiceContainer) -> "UserInfoModal":
        async with get_session(services) as session:
            user_info_repo = get_user_info_repo(session)
            try:
                info = await user_info_repo.get_user_info(user_id)
                user_info = info.user_info
            except UserInfoNotFoundError:
                await user_info_repo.create_user_info(user_id, "")
                user_info = None

        return cls(services, user_info)

    async def callback(self, interaction: Interaction) -> None:
        text = self.info_text.value or ""
        if not interaction.user:
            await interaction.response.send_message("Error: user not found", ephemeral=True)
            return

        logger.debug("Saving user info", user_id=interaction.user.id, info=text)
        async with get_session(self.services) as session:
            user_info_repo = get_user_info_repo(session)
            await user_info_repo.update_user_info(interaction.user.id, text)
        await interaction.response.send_message("Information saved successfully!", ephemeral=True)
