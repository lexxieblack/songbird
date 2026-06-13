from songbird.config import Settings
from songbird.models.conversation import ConversationContext
from songbird.services.private_conversation import PrivateConversationService
from songbird.utils.logging import get_logger


class PrivateChatHandler:
    def __init__(self, settings: Settings, private_conversation_service: PrivateConversationService):
        self.settings = settings
        self.conversation_service = private_conversation_service
        self.logger = get_logger(__name__)

    async def chat(
        self,
        user_id: int,
        message: str,
        username: str,
        display_name: str,
        guild_name: str | None = None,
        channel_name: str | None = None,
    ) -> str | None:
        if not message or not message.strip():
            return None

        context = ConversationContext(
            username=username,
            display_name=display_name,
            guild_name=guild_name,
            channel_name=channel_name,
        )

        return await self.conversation_service.chat(user_id=user_id, message=message, context=context)
