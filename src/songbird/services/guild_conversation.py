from structlog import BoundLogger

from songbird.config import Settings
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.guild_message import GuildMessage, MessageRole
from songbird.models.conversation import ConversationContext
from songbird.models.llm import LLMRequest
from songbird.repositories.chat.guild_message import GuildMessageRepository
from songbird.services.llm import LLMService
from songbird.utils.logging import get_logger
from songbird.utils.prompts import get_system_prompt


class GuildConversationService:
    def __init__(
        self,
        llm: LLMService,
        guild_message_repo: GuildMessageRepository,
        settings: Settings,
        logger: BoundLogger | None = None,
    ) -> None:
        self.llm = llm
        self.guild_message_repo = guild_message_repo
        self.settings = settings
        self.logger = logger or get_logger(__name__)

    async def chat(
        self,
        guild_id: int,
        message: str,
        context: ConversationContext,
    ) -> str:
        if not message or not message.strip():
            self.logger.warning("No message to chat")
            return "Error: no message provided"

        self.logger.info(
            "Chat started",
            guild_id=guild_id,
            message=message,
            context=context.model_dump_json(),
        )

        messages = await self._get_past_messages(guild_id)
        system_prompt = self._build_system_prompt(context)

        try:
            user_message = f"{context.display_name} (ID: {context.username}) in channel {context.channel_name} said:\n" + message
            save = await self._save_message(guild_id=guild_id, message=user_message, role=MessageRole.USER)
            if not save:
                return "Error: failed to save message"

            llm_request = LLMRequest(
                system_prompt=system_prompt,
                user_prompt=user_message,
                context_messages=messages,
            )
            reply = await self.llm.call(llm_request)

            await self._save_message(guild_id=guild_id, message=reply, role=MessageRole.MODEL)

            return reply
        except Exception as e:
            self.logger.error("Chat failed", error=str(e))
            return "*static crackles* Something's... not right in my neural pathways.\nGive me a moment to recalibrate, choom."

    async def _save_message(self, guild_id: int, message: str, role: MessageRole) -> bool:
        try:
            await self.guild_message_repo.create_message(guild_id, role, message)
            self.logger.debug(
                "Message saved",
                guild_id=guild_id,
                role=role.value,
                content=message,
            )
            return True
        except MessageAlreadyExistsError:
            self.logger.error(
                "Message already exists",
                guild_id=guild_id,
                role=role.value,
                message=message,
            )
        except Exception as e:
            self.logger.error(
                "Failed to save message",
                guild_id=guild_id,
                role=role.value,
                message=message,
                error=str(e),
            )

        return False

    async def _get_past_messages(self, guild_id: int) -> list[GuildMessage]:
        self.logger.debug("Getting previous messages", guild_id=guild_id)
        try:
            messages = await self.guild_message_repo.get_newest_messages(guild_id=guild_id, limit=self.settings.llm.message_count)
            self.logger.debug("Got previous message", guild_id=guild_id, message_count=len(messages))
            return messages

        except Exception as e:
            self.logger.error("Error getting previous messages", guild_id=guild_id, error=str(e))

        return []

    def _build_system_prompt(self, context: ConversationContext) -> str:
        prompt_path = self.settings.llm.system_prompt_path
        base_prompt = get_system_prompt(prompt_path)

        parts = [base_prompt, f"\nServer Name: {context.guild_name}"]

        return "\n".join(parts)

    async def delete_last_message(self, guild_id: int) -> None:
        await self.guild_message_repo.delete_last_message(guild_id)

    async def delete_all_messages(self, guild_id: int) -> int:
        return await self.guild_message_repo.delete_messages(guild_id)
