from discord import Bot, Forbidden, ForumChannel, Thread
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
            self.logger.error(
                "No permissions to create a thread",
                user_id=user_id,
                channel_id=self.thread_channel_id,
            )

        except Exception as e:
            self.logger.error(
                "Error creating thread",
                user_id=user_id,
                channel_id=self.thread_channel_id,
                error=str(e),
            )

        return 0

    async def send_feedback(self, user_id: int, user_name: str, message: str) -> None:
        try:
            thread = await self.thread_repo.get_thread(user_id)
            thread_id = thread.thread_id
        except ThreadNotFoundError:
            thread_id = await self._create_thread(user_name, user_id)
        except Exception:
            raise

        if thread_id == 0:
            return

        channel = self.bot.get_channel(thread_id)
        if not channel or not isinstance(channel, Thread):
            return

        await channel.send(message)
