from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from discord import Bot
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from songbird.repositories.chat.guild_message import GuildMessageRepository
from songbird.repositories.chat.message import MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.repositories.feedback.thread import ThreadRepository
from songbird.services.feedback import FeedbackService
from songbird.services.guild_conversation import GuildConversationService
from songbird.services.link_fixer import LinkFixerService
from songbird.services.llm import LLMService
from songbird.services.translation import TranslationService
from songbird.services.wolfram import WolframService
from songbird.utils.logging import get_logger

if TYPE_CHECKING:
    from songbird.config import Settings
    from songbird.services.private_conversation import PrivateConversationService


logger = get_logger(__name__)


@dataclass
class ServiceContainer:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    llm: LLMService
    translation: TranslationService
    link_fixer: LinkFixerService
    wolfram: WolframService
    settings: "Settings"


async def create_container(settings: "Settings") -> ServiceContainer:
    """Create and initialise the service container with all dependencies.

    Creates the database engine with connection pooling, session factory,
    and all service instances wired up with their dependencies.

    Args:
        settings: Application settings containing database URL, API keys, and other configuration.

    Returns:
        A fully initialised ServiceContainer with all services ready to use.
    """
    log = logger.bind(component="container")
    log.info("Creating service container")

    # Create async database engine with connection pool settings
    engine = create_async_engine(
        settings.db.url,
        echo=False,  # Set to True for SQL debugging
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # Recycle connections after 30 minutes
        pool_pre_ping=True,  # Enable connection health checks
    )

    log.info("Database engine created", pool_size=5, max_overflow=10)

    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Create service instances
    llm_service = LLMService(settings, logger=log.bind(service="llm"))
    translation_service = TranslationService(logger=log.bind(service="translation"))
    link_fixer_service = LinkFixerService(settings, logger=log.bind(service="link_fixer"))
    wolfram_service = WolframService(settings, logger=log.bind(service="wolfram"))

    log.info("services_created")

    container = ServiceContainer(
        engine=engine,
        session_factory=session_factory,
        llm=llm_service,
        translation=translation_service,
        link_fixer=link_fixer_service,
        wolfram=wolfram_service,
        settings=settings,
    )

    log.info("Service container ready")

    return container


async def close_container(container: ServiceContainer) -> None:
    """Close the service container and release all resources.

    Disposes of the database engine connection pool and closes any HTTP clients held by services.

    Args:
        container: The service container to close.
    """
    log = logger.bind(component="container")
    log.info("Closing service container")

    # Close HTTP clients in services that have them
    try:
        await container.translation.close()
        log.debug("Translation service closed")
    except Exception as e:
        log.warning("Translation service close error", error=str(e))

    # Dispose of database engine
    try:
        await container.engine.dispose()
        log.debug("Databse engine disposed")
    except Exception as e:
        log.warning("Database engine dispose error", error=str(e))

    log.info("Service container closed")


@asynccontextmanager
async def get_session(container: ServiceContainer) -> AsyncIterator[AsyncSession]:
    """Context manager for obtaining a database session.

    Provides a database session that automatically commits on success and rolls back on exception.
    The session is closed when the context manager exits.

    Args:
        container: The service container with the session factory.

    Yields:
        An AsyncSession for database operations.

    Example:
        >>> async with get_session(container) as session:
        >>>    repo = ConversationRepository(session)
        >>>    messages = await repo.get_user_messages(user_id)
    """
    session = container.session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_message_repo(session: AsyncSession) -> MessageRepository:
    return MessageRepository(session)


def get_guild_message_repo(session: AsyncSession) -> GuildMessageRepository:
    return GuildMessageRepository(session)


def get_user_info_repo(session: AsyncSession) -> UserInfoRepository:
    return UserInfoRepository(session)


def get_feedback_repo(session: AsyncSession) -> ThreadRepository:
    return ThreadRepository(session)


def create_private_conversation_service(session: AsyncSession, container: ServiceContainer) -> "PrivateConversationService":
    from songbird.services.private_conversation import PrivateConversationService

    message_repo = get_message_repo(session)
    user_info_repo = get_user_info_repo(session)

    return PrivateConversationService(
        llm=container.llm,
        message_repo=message_repo,
        user_info_repo=user_info_repo,
        settings=container.settings,
    )


def create_guild_conversation_service(session: AsyncSession, container: ServiceContainer) -> "GuildConversationService":
    from songbird.services.guild_conversation import GuildConversationService

    guild_message_repo = get_guild_message_repo(session)

    return GuildConversationService(
        llm=container.llm,
        guild_message_repo=guild_message_repo,
        settings=container.settings,
    )


def create_feedback_service(session: AsyncSession, container: ServiceContainer, bot: Bot) -> "FeedbackService":
    from songbird.services.feedback import FeedbackService

    thread_repo = get_feedback_repo(session)

    return FeedbackService(bot=bot, thread_repo=thread_repo, settings=container.settings)
