# pyright: reportPrivateUsage=false

from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.bot import SongbirdBot
from songbird.config import Settings
from songbird.models.chat.base import MessageRole
from songbird.repositories.chat.message import GuildMessageRepository, MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.services.audit_log import AuditLogService
from songbird.services.blackwall import BlackwallService
from songbird.services.container import (
    ServiceContainer,
    close_container,
    create_audit_log_service,
    create_container,
    create_feedback_service,
    create_guild_conversation_service,
    create_private_conversation_service,
    get_guild_message_repo,
    get_message_repo,
    get_session,
    get_user_info_repo,
)
from songbird.services.currency import CurrencyService
from songbird.services.link_fixer import LinkFixerService
from songbird.services.llm import LLMService
from songbird.services.management import BanEnforcementService
from songbird.services.translation import TranslationService
from songbird.services.wolfram import WolframService


async def test_create_container_wires_every_service(settings: Settings, fake_genai_client: SimpleNamespace) -> None:  # noqa: ARG001
    container = await create_container(settings)
    try:
        assert container.settings is settings
        assert isinstance(container.llm, LLMService)
        assert isinstance(container.translation, TranslationService)
        assert isinstance(container.link_fixer, LinkFixerService)
        assert isinstance(container.wolfram, WolframService)
        assert isinstance(container.currency, CurrencyService)
        assert container.engine.url.drivername == "postgresql+psycopg"
        assert container.session_factory is not None

        assert isinstance(container.blackwall, BlackwallService)
        assert container.blackwall.session_factory is container.session_factory
        assert isinstance(container.management, BanEnforcementService)
        assert container.management.session_factory is container.session_factory
    finally:
        await close_container(container)


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


async def test_close_container_releases_clients(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    fake_genai_client: SimpleNamespace,  # noqa: ARG001
) -> None:
    container = await create_container(settings)
    await container.engine.dispose()
    engine = _Engine()
    container.engine = cast(Any, engine)
    closed: list[bool] = []
    original_close = container.translation.close

    async def close() -> None:
        closed.append(True)
        await original_close()

    monkeypatch.setattr(container.translation, "close", close)

    await close_container(container)

    assert closed == [True]
    assert engine.disposed is True


async def test_close_container_swallows_cleanup_errors(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    fake_genai_client: SimpleNamespace,  # noqa: ARG001
) -> None:
    container = await create_container(settings)
    await container.engine.dispose()
    engine = _Engine()
    container.engine = cast(Any, engine)

    async def broken() -> None:
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(container.translation, "close", broken)

    await close_container(container)

    assert engine.disposed is True


@pytest.mark.db
async def test_get_session_commits(db_container: ServiceContainer, session: AsyncSession) -> None:
    async with get_session(db_container) as active:
        await MessageRepository(active).create_message(5, MessageRole.USER, "kept")

    assert [message.content for message in await MessageRepository(session).get_newest_messages(5)] == ["kept"]


@pytest.mark.db
async def test_get_session_rolls_back_on_error(db_container: ServiceContainer, session: AsyncSession) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with get_session(db_container) as active:
            await MessageRepository(active).create_message(5, MessageRole.USER, "discarded")
            raise RuntimeError("boom")

    assert await MessageRepository(session).get_newest_messages(5) == []


@pytest.mark.db
@pytest.mark.parametrize(
    ("factory", "repository"),
    [
        (get_message_repo, MessageRepository),
        (get_guild_message_repo, GuildMessageRepository),
        (get_user_info_repo, UserInfoRepository),
    ],
)
async def test_repository_factories_bind_the_session(session: AsyncSession, factory: Any, repository: type[object]) -> None:
    repo: Any = factory(session)

    assert repo.session is session
    assert isinstance(repo, repository)


async def test_request_scoped_service_factories(
    settings: Settings,
    fake_bot: SongbirdBot,
    fake_genai_client: SimpleNamespace,  # noqa: ARG001
) -> None:
    container = await create_container(settings)
    dummy_session = cast(AsyncSession, object())
    try:
        private = create_private_conversation_service(dummy_session, container)
        assert private.llm is container.llm
        assert private.message_repo.session is dummy_session
        assert private.user_info_repo.session is dummy_session
        assert private.settings is settings

        guild = create_guild_conversation_service(dummy_session, container)
        assert guild.llm is container.llm
        assert guild.message_repo.session is dummy_session
        assert guild.settings is settings

        feedback = create_feedback_service(dummy_session, container, fake_bot)
        assert feedback.bot is fake_bot
        assert feedback.thread_repo.session is dummy_session
        assert feedback.thread_channel_id == settings.bot.feedback_channel_id

        audit = create_audit_log_service(dummy_session)
        assert isinstance(audit, AuditLogService)
        assert audit.repository.session is dummy_session
    finally:
        await close_container(container)
