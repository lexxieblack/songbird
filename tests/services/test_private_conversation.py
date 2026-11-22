from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.config import Settings
from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.message import message_table
from songbird.models.conversation import ConversationContext
from songbird.repositories.chat.message import MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.services.llm import LLMService
from songbird.services.private_conversation import PrivateConversationService
from songbird.utils.id_factory import make_id
from tests.support.llm import FakeLLMService

pytestmark = pytest.mark.db

CONTEXT = ConversationContext(user_id=1, username="alice", display_name="Alice", channel_name="dm")


def _service(
    llm: FakeLLMService, session: AsyncSession, settings: Settings
) -> tuple[PrivateConversationService, MessageRepository]:
    messages = MessageRepository(session)
    service = PrivateConversationService(
        llm=cast(LLMService, llm),
        message_repo=messages,
        user_info_repo=UserInfoRepository(session),
        settings=settings,
    )
    return service, messages


async def _seed(session: AsyncSession, *entries: tuple[MessageRole, str]) -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for offset, (role, content) in enumerate(entries):
        await session.execute(
            insert(message_table).values(
                id=make_id(), user_id=1, role=role.value, content=content, created_at=base + timedelta(seconds=offset)
            )
        )
    await session.commit()


async def test_blank_message_is_rejected(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    service, messages = _service(llm, session, settings)

    assert await service.chat(1, "   ", CONTEXT) == "Error: no message provided"
    assert llm.requests == []
    assert await messages.get_newest_messages(1) == []


async def test_chat_answers_and_saves_both_messages(session: AsyncSession, settings: Settings) -> None:
    await UserInfoRepository(session).create_user_info(1, "likes cats")
    await session.commit()
    llm = FakeLLMService("hello alice")
    service, messages = _service(llm, session, settings)

    assert await service.chat(1, "hi", CONTEXT) == "hello alice"

    request = llm.requests[0]
    assert request.user_prompt == "hi"
    assert request.context_messages == []
    assert "User: alice (ID: 1)" in (request.system_prompt or "")
    assert "likes cats" in (request.system_prompt or "")
    assert {(m.role, m.content) for m in await messages.get_all_messages(1)} == {
        (MessageRole.USER, "hi"),
        (MessageRole.MODEL, "hello alice"),
    }


async def test_past_messages_are_sent_oldest_first(session: AsyncSession, settings: Settings) -> None:
    await _seed(session, (MessageRole.USER, "one"), (MessageRole.MODEL, "two"))
    llm = FakeLLMService("reply")
    service, _ = _service(llm, session, settings)

    await service.chat(1, "three", CONTEXT)

    context = llm.requests[0].context_messages
    assert context is not None
    assert [message.content for message in context] == ["one", "two"]


async def test_empty_llm_response_saves_nothing(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("   ")
    service, messages = _service(llm, session, settings)

    assert await service.chat(1, "hi", CONTEXT) == ""
    assert await messages.get_newest_messages(1) == []


async def test_llm_error_returns_static_reply_and_saves_nothing(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("upstream down")
    service, messages = _service(llm, session, settings)

    reply = await service.chat(1, "hi", CONTEXT)

    assert "static crackles" in reply
    assert await messages.get_newest_messages(1) == []


async def test_user_message_save_failure_returns_error(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, settings: Settings
) -> None:
    llm = FakeLLMService("reply")
    service, messages = _service(llm, session, settings)

    async def _duplicate(*_args: Any) -> Any:
        raise MessageAlreadyExistsError()

    monkeypatch.setattr(messages, "create_message", _duplicate)

    assert await service.chat(1, "hi", CONTEXT) == "Error: failed to save message"
    assert await messages.get_newest_messages(1) == []


async def test_model_message_save_failure_still_returns_reply(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession, settings: Settings
) -> None:
    llm = FakeLLMService("reply")
    service, messages = _service(llm, session, settings)
    original = messages.create_message

    async def _fail_on_model(user_id: int, role: MessageRole, content: str) -> Any:
        if role is MessageRole.MODEL:
            raise MessageAlreadyExistsError()
        return await original(user_id, role, content)

    monkeypatch.setattr(messages, "create_message", _fail_on_model)

    assert await service.chat(1, "hi", CONTEXT) == "reply"
    assert [m.content for m in await messages.get_newest_messages(1)] == ["hi"]


async def test_missing_user_info_still_answers(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("reply")
    service, _ = _service(llm, session, settings)

    assert await service.chat(1, "hi", CONTEXT) == "reply"
    assert "Information provided by the user" not in (llm.requests[0].system_prompt or "")


async def test_delete_helpers(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    service, messages = _service(llm, session, settings)
    await _seed(session, (MessageRole.USER, "one"), (MessageRole.MODEL, "two"), (MessageRole.USER, "three"))

    await service.delete_last_message(1)
    assert [m.content for m in await messages.get_all_messages(1)] == ["one", "two"]

    assert await service.delete_all_messages(1) == 2
    assert await messages.get_all_messages(1) == []
