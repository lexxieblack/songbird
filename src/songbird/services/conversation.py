from typing import Any

from structlog import BoundLogger

from songbird.config import Settings
from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError, UserInfoNotFoundError
from songbird.models.chat.guild_message import GuildMessage
from songbird.models.chat.message import Message
from songbird.models.conversation import ConversationContext
from songbird.models.llm import LLMRequest
from songbird.repositories.chat.message import BaseMessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.services.llm import LLMService
from songbird.utils.logging import get_logger
from songbird.utils.prompts import build_user_context, get_system_prompt

STATIC_REPLY = "*static crackles* Something's... not right in my neural pathways.\nGive me a moment to recalibrate, choom."


class ConversationService:
    """One chat flow for both history tables; subclasses supply the key and prompt text."""

    def __init__(
        self,
        llm: "LLMService",
        message_repo: "BaseMessageRepository[Any]",
        settings: "Settings",
        logger: BoundLogger | None = None,
    ) -> None:
        self.llm = llm
        self.message_repo = message_repo
        self.settings = settings
        self.logger = logger or get_logger(__name__)

    async def chat(
        self,
        key: int,
        message: str,
        context: ConversationContext,
    ) -> str:
        if not message or not message.strip():
            self.logger.warning("No message to chat")
            return "Error: no message provided"

        self.logger.info(
            "Chat started",
            **{self.message_repo.key: key},
            username=context.username,
            message=message,
            context=context.model_dump_json(),
        )

        user_info = await self._get_user_info(context.user_id, context.username)
        messages = await self._get_past_messages(key, context.username)
        system_prompt = self._build_system_prompt(context, user_info)

        # End the read transaction so the pooled connection is not held through the model call.
        await self.message_repo.session.commit()

        try:
            llm_request = LLMRequest(
                system_prompt=system_prompt,
                user_prompt=self._format_user_message(context, message),
                context_messages=messages,
            )
            reply = await self.llm.call(llm_request)

            if not reply or not reply.strip():
                self.logger.warning("Empty LLM response, skipping save", **{self.message_repo.key: key}, username=context.username)
                return ""

            save = await self._save_message(
                key=key, message=llm_request.user_prompt, role=MessageRole.USER, username=context.username
            )
            if not save:
                return "Error: failed to save message"

            await self._save_message(key=key, message=reply, role=MessageRole.MODEL, username=context.username)

            return reply
        except Exception as e:
            self.logger.exception("Chat failed", username=context.username, error=e)
            return STATIC_REPLY

    async def _save_message(self, key: int, message: str, role: MessageRole, username: str) -> bool:
        try:
            await self.message_repo.create_message(key, role, message)
            self.logger.debug(
                "Message saved",
                **{self.message_repo.key: key},
                username=username,
                role=role.value,
                content=message,
            )
            return True
        except MessageAlreadyExistsError:
            self.logger.exception(
                "Message already exists",
                **{self.message_repo.key: key},
                username=username,
                role=role.value,
                message=message,
            )
        except Exception as e:
            self.logger.exception(
                "Failed to save message",
                **{self.message_repo.key: key},
                username=username,
                role=role.value,
                message=message,
                error=e,
            )

        return False

    async def _get_past_messages(self, key: int, username: str) -> list[Message] | list[GuildMessage]:
        self.logger.debug("Getting previous messages", **{self.message_repo.key: key}, username=username)
        try:
            messages = await self.message_repo.get_newest_messages(key=key, limit=self.settings.llm.message_count)
            self.logger.debug(
                "Got previous message", **{self.message_repo.key: key}, username=username, message_count=len(messages)
            )
            return messages[::-1]

        except Exception as e:
            self.logger.exception("Error getting previous messages", **{self.message_repo.key: key}, username=username, error=e)

        return []

    async def _get_user_info(self, _user_id: int, _username: str) -> str | None:
        return None

    def _format_user_message(self, _context: ConversationContext, message: str) -> str:
        return message

    def _build_system_prompt(self, context: ConversationContext, user_info: str | None) -> str:
        return "\n".join([get_system_prompt(self.settings.llm.system_prompt_path), self._context_text(context, user_info)])

    def _context_text(self, _context: ConversationContext, _user_info: str | None) -> str:
        return ""

    async def delete_last_message(self, key: int) -> None:
        await self.message_repo.delete_last_message(key)

    async def delete_all_messages(self, key: int) -> int:
        return await self.message_repo.delete_messages(key)


class PrivateConversationService(ConversationService):
    def __init__(
        self,
        llm: "LLMService",
        message_repo: "BaseMessageRepository[Any]",
        user_info_repo: UserInfoRepository,
        settings: "Settings",
        logger: BoundLogger | None = None,
    ) -> None:
        super().__init__(llm, message_repo, settings, logger)
        self.user_info_repo = user_info_repo

    async def _get_user_info(self, user_id: int, username: str) -> str | None:
        self.logger.debug("Getting user info", user_id=user_id, username=username)
        try:
            info = await self.user_info_repo.get_user_info(user_id)
            self.logger.debug("Got user info", user_id=user_id, username=username)
            return info.user_info

        except UserInfoNotFoundError:
            self.logger.info("User info not found", user_id=user_id, username=username)

        except Exception as e:
            self.logger.exception(
                "Error getting user info",
                user_id=user_id,
                username=username,
                error=e,
            )
        return None

    def _context_text(self, context: ConversationContext, user_info: str | None) -> str:
        user_context = build_user_context(
            user_id=context.user_id,
            username=context.username,
            guild_name=context.guild_name,
            channel_name=context.channel_name,
        )

        parts = ["\nUser Context:", user_context]

        if user_info:
            parts.append(f"\nInformation provided by the user:\n{user_info}")

        return "\n".join(parts)


class GuildConversationService(ConversationService):
    def _format_user_message(self, context: ConversationContext, message: str) -> str:
        return (
            f"{context.display_name} (ID: {context.user_id}, username: {context.username}) "
            f"in channel {context.channel_name} said:\n" + message
        )

    def _context_text(self, context: ConversationContext, _user_info: str | None) -> str:
        return f"\nServer Name: {context.guild_name}"
