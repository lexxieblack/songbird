from discord import AllowedMentions, Bot, DiscordException, Forbidden, ForumChannel, Thread
from structlog import BoundLogger

from songbird.config import Settings
from songbird.models.feedback.exceptions import NotForumChannel, ThreadNotFoundError
from songbird.repositories.feedback.thread import ThreadRepository
from songbird.utils.logging import get_logger


class FeedbackService:
    def __init__(
        self,
        bot: Bot,
        thread_repo: ThreadRepository,
        settings: Settings,
        logger: BoundLogger | None = None,
    ) -> None:
        self.thread_repo = thread_repo
        self.thread_channel_id = settings.bot.feedback_channel_id
        self.bot = bot
        self.logger = logger or get_logger(__name__)

    async def _create_thread(self, user_name: str, user_id: int) -> int:
        if not self.thread_channel_id:
            return 0

        feedback_channel = self.bot.get_channel(self.thread_channel_id)
        if not feedback_channel:
            raise ThreadNotFoundError(data={"channel_id": self.thread_channel_id})

        if not isinstance(feedback_channel, ForumChannel):
            raise NotForumChannel(data={"channel_id": self.thread_channel_id})

        try:
            thread = await feedback_channel.create_thread(
                name=f"Feedback from {user_name}",
                content=f"This is feedback from <@{user_id}>",
            )
            await self.thread_repo.create_thread(user_id, thread.id)
            return thread.id
        except Forbidden:
            self.logger.exception(
                "No permissions to create a thread",
                user_id=user_id,
                username=user_name,
                channel_id=self.thread_channel_id,
            )

        except Exception as e:
            self.logger.exception(
                "Error creating thread",
                user_id=user_id,
                username=user_name,
                channel_id=self.thread_channel_id,
                error=e,
            )

        return 0

    async def send_feedback(self, user_id: int, user_name: str, message: str) -> bool:
        def thread_channel(thread_id: int) -> Thread | None:
            channel = self.bot.get_channel(thread_id) if thread_id else None
            return channel if isinstance(channel, Thread) else None

        try:
            thread = await self.thread_repo.get_thread(user_id)
        except ThreadNotFoundError:
            thread_id = await self._create_thread(user_name, user_id)
        else:
            thread_id = thread.thread_id
            if thread_channel(thread_id) is None:
                # The stored thread was deleted; forget it and open a fresh one instead of failing forever.
                self.logger.info("Feedback thread missing, recreating", user_id=user_id, username=user_name, thread_id=thread_id)
                await self.thread_repo.delete_thread(user_id)
                thread_id = await self._create_thread(user_name, user_id)

        channel = thread_channel(thread_id)
        if channel is None:
            if thread_id:
                self.logger.error("Feedback thread unavailable", user_id=user_id, username=user_name, thread_id=thread_id)
            return False

        try:
            await channel.send(message, allowed_mentions=AllowedMentions.none())
        except DiscordException as e:
            self.logger.exception("Feedback message failed", user_id=user_id, username=user_name, thread_id=thread_id, error=e)
            return False

        return True
