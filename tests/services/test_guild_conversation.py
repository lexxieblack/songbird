from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.config import Settings
from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.guild_message import guild_message_table
from songbird.models.conversation import ConversationContext
from songbird.repositories.chat.guild_message import GuildMessageRepository
from songbird.services.guild_conversation import GuildConversationService
from songbird.services.llm import LLMService
from songbird.utils.id_factory import make_id
from tests.support.llm import FakeLLMService

pytestmark = pytest.mark.db

CONTEXT = ConversationContext(
    user_id=7,
    username="bob",
    display_name="Bobby",
    guild_name="Test Guild",
    channel_name="general",
)
USER_MESSAGE = "Bobby (ID: 7, username: bob) in channel general said:\nhi"


def _service(
    llm: FakeLLMService, session: AsyncSession, settings: Settings
) -> tuple[GuildConversationService, GuildMessageRepository]:
    messages = GuildMessageRepository(session)
    service = GuildConversationService(
        llm=cast(LLMService, llm),
        guild_message_repo=messages,
        settings=settings,
    )
    return service, messages


async def _contents(messages: GuildMessageRepository) -> list[str]:
    return [message.content for message in reversed(await messages.get_newest_messages(7))]


async def _seed(session: AsyncSession, *entries: tuple[MessageRole, str]) -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for offset, (role, content) in enumerate(entries):
        await session.execute(
            insert(guild_message_table).values(
                id=make_id(), guild_id=7, role=role.value, content=content, created_at=base + timedelta(seconds=offset)
            )
        )
    await session.commit()


async def test_blank_message_is_rejected(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    service, messages = _service(llm, session, settings)

    assert await service.chat(7, "", CONTEXT) == "Error: no message provided"
    assert llm.requests == []
    assert await messages.get_newest_messages(7) == []


async def test_chat_answers_and_saves_formatted_messages(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("hello bob")
    service, messages = _service(llm, session, settings)

    assert await service.chat(7, "hi", CONTEXT) == "hello bob"

    request = llm.requests[0]
    assert request.user_prompt == USER_MESSAGE
    assert "Server Name: Test Guild" in (request.system_prompt or "")
    assert set(await _contents(messages)) == {USER_MESSAGE, "hello bob"}


async def test_past_messages_are_sent_oldest_first(session: AsyncSession, settings: Settings) -> None:
    await _seed(session, (MessageRole.USER, "one"), (MessageRole.MODEL, "two"))
    llm = FakeLLMService("reply")
    service, _ = _service(llm, session, settings)

    await service.chat(7, "three", CONTEXT)

    context = llm.requests[0].context_messages
    assert context is not None
    assert [message.content for message in context] == ["one", "two"]


async def test_empty_llm_response_saves_nothing(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("")
    service, messages = _service(llm, session, settings)

    assert await service.chat(7, "hi", CONTEXT) == ""
    assert await messages.get_newest_messages(7) == []


async def test_llm_error_returns_static_reply_and_saves_nothing(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("upstream down")
    service, messages = _service(llm, session, settings)

    reply = await service.chat(7, "hi", CONTEXT)

    assert "static crackles" in reply
    assert await messages.get_newest_messages(7) == []


async def test_save_failure_returns_error(monkeypatch: pytest.MonkeyPatch, session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("reply")
    service, messages = _service(llm, session, settings)

    async def _duplicate(*_args: Any) -> Any:
        raise MessageAlreadyExistsError()

    monkeypatch.setattr(messages, "create_message", _duplicate)

    assert await service.chat(7, "hi", CONTEXT) == "Error: failed to save message"
    assert await messages.get_newest_messages(7) == []


async def test_delete_helpers(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    service, messages = _service(llm, session, settings)
    await _seed(session, (MessageRole.USER, "one"), (MessageRole.MODEL, "two"), (MessageRole.USER, "three"))

    await service.delete_last_message(7)
    assert await _contents(messages) == ["one", "two"]

    assert await service.delete_all_messages(7) == 2
    assert await messages.get_newest_messages(7) == []
