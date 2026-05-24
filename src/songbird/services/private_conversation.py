from structlog import BoundLogger

from songbird.config import Settings
from songbird.models.chat.exceptions import MessageAlreadyExistsError, UserInfoNotFoundError
from songbird.models.chat.message import Message, MessageRole
from songbird.models.conversation import ConversationContext
from songbird.models.llm import LLMRequest
from songbird.repositories.chat.message import MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.services.llm import LLMService
from songbird.utils.logging import get_logger
from songbird.utils.prompts import build_user_context, get_system_prompt


class PrivateConversationService:
    def __init__(
        self,
        llm: "LLMService",
        message_repo: "MessageRepository",
        user_info_repo: "UserInfoRepository",
        settings: "Settings",
        logger: BoundLogger | None = None,
    ) -> None:
        self.llm = llm
        self.message_repo = message_repo
        self.user_info_repo = user_info_repo
        self.settings = settings
        self.logger = logger or get_logger(__name__)

    async def chat(
        self,
        user_id: int,
        message: str,
        context: ConversationContext,
    ) -> str:
        if not message or not message.strip():
            self.logger.warning("No message to chat")
            return "Error: no message provided"

        self.logger.info(
            "Chat started",
            user_id=user_id,
            message=message,
            context=context.model_dump_json(),
        )

        user_info = await self._get_user_info(user_id)
        messages = await self._get_past_messages(user_id)
        system_prompt = self._build_system_prompt(
            user_id=user_id,
            username=context.username,
            guild_name=context.guild_name,
            channel_name=context.channel_name,
            user_info=user_info,
        )

        try:
            save = await self._save_message(user_id=user_id, message=message, role=MessageRole.USER)
            if not save:
                return "Error: failed to save message"

            llm_request = LLMRequest(
                system_prompt=system_prompt,
                user_prompt=message,
                context_messages=messages,
            )
            reply = await self.llm.call(llm_request)

            await self._save_message(user_id=user_id, message=reply, role=MessageRole.MODEL)

            return reply
        except Exception as e:
            self.logger.error("Chat failed", error=str(e))
            return "*static crackles* Something's... not right in my neural pathways.\nGive me a moment to recalibrate, choom."

    async def _save_message(self, user_id: int, message: str, role: MessageRole) -> bool:
        try:
            await self.message_repo.create_message(user_id, role, message)
            self.logger.debug(
                "Message saved",
                user_id=user_id,
                role=role.value,
                content=message,
            )
            return True
        except MessageAlreadyExistsError:
            self.logger.error(
                "Message already exists",
                user_id=user_id,
                role=role.value,
                message=message,
            )
        except Exception as e:
            self.logger.error(
                "Failed to save message",
                user_id=user_id,
                role=role.value,
                message=message,
                error=str(e),
            )

        return False

    async def _get_user_info(self, user_id: int) -> str | None:
        self.logger.debug("Getting user info", user_id=user_id)
        try:
            info = await self.user_info_repo.get_user_info(user_id)
            self.logger.debug("Got user info", user_id=user_id)
            return info.user_info

        except UserInfoNotFoundError:
            self.logger.info("User info not found", user_id=user_id)

        except Exception as e:
            self.logger.error(
                "Error getting user info",
                user_id=user_id,
                error=str(e),
            )
        return None

    async def _get_past_messages(self, user_id: int) -> list[Message]:
        self.logger.debug("Getting previous messages", user_id=user_id)
        try:
            messages = await self.message_repo.get_newest_messages(user_id=user_id, limit=self.settings.llm.message_count)
            self.logger.debug("Got previous message", user_id=user_id, message_count=len(messages))
            return messages

        except Exception as e:
            self.logger.error("Error getting previous messages", user_id=user_id, error=str(e))

        return []

    def _build_system_prompt(
        self,
        user_id: int,
        username: str,
        guild_name: str | None = None,
        channel_name: str | None = None,
        user_info: str | None = None,
    ) -> str:
        prompt_path = self.settings.llm.system_prompt_path
        base_prompt = get_system_prompt(prompt_path)

        user_context = build_user_context(user_id=user_id, username=username, guild_name=guild_name, channel_name=channel_name)

        parts = [base_prompt, "\nUser Context:", user_context]

        if user_info:
            parts.append(f"\nInformation provided by the user:\n{user_info}")

        return "\n".join(parts)

    async def delete_last_message(self, user_id: int) -> None:
        await self.message_repo.delete_last_message(user_id)

    async def delete_all_messages(self, user_id: int) -> int:
        return await self.message_repo.delete_messages(user_id)
