from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import Table, insert
from sqlalchemy.ext.asyncio import AsyncSession

from songbird.config import Settings
from songbird.models.chat.base import MessageRole
from songbird.models.chat.exceptions import MessageAlreadyExistsError
from songbird.models.chat.guild_message import guild_message_table
from songbird.models.chat.message import message_table
from songbird.models.conversation import ConversationContext
from songbird.repositories.chat.message import BaseMessageRepository, GuildMessageRepository, MessageRepository
from songbird.repositories.chat.user_info import UserInfoRepository
from songbird.services.conversation import ConversationService, GuildConversationService, PrivateConversationService
from songbird.services.llm import LLMService
from songbird.utils.id_factory import make_id
from tests.support.llm import FakeLLMService

pytestmark = pytest.mark.db

PRIVATE_CONTEXT = ConversationContext(user_id=1, username="alice", display_name="Alice", channel_name="dm")
GUILD_CONTEXT = ConversationContext(
    user_id=7,
    username="bob",
    display_name="Bobby",
    guild_name="Test Guild",
    channel_name="general",
)
GUILD_USER_MESSAGE = "Bobby (ID: 7, username: bob) in channel general said:\nhi"


@dataclass(frozen=True)
class Case:
    key: int
    table: Table
    repository: type[BaseMessageRepository[Any]]
    context: ConversationContext
    user_message: str


PRIVATE_CASE = Case(1, message_table, MessageRepository, PRIVATE_CONTEXT, "hi")
GUILD_CASE = Case(7, guild_message_table, GuildMessageRepository, GUILD_CONTEXT, GUILD_USER_MESSAGE)
CASES = [pytest.param(PRIVATE_CASE, id="private"), pytest.param(GUILD_CASE, id="guild")]


def _service(
    case: Case, llm: FakeLLMService, session: AsyncSession, settings: Settings
) -> tuple[ConversationService, BaseMessageRepository[Any]]:
    repo = case.repository(session)
    if case.repository is MessageRepository:
        service: ConversationService = PrivateConversationService(
            llm=cast(LLMService, llm),
            message_repo=repo,
            user_info_repo=UserInfoRepository(session),
            settings=settings,
        )
    else:
        service = GuildConversationService(llm=cast(LLMService, llm), message_repo=repo, settings=settings)
    return service, repo


async def _seed(case: Case, session: AsyncSession, *entries: tuple[MessageRole, str]) -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for offset, (role, content) in enumerate(entries):
        await session.execute(
            insert(case.table).values(
                **{
                    "id": make_id(),
                    case.repository.key: case.key,
                    "role": role.value,
                    "content": content,
                    "created_at": base + timedelta(seconds=offset),
                }
            )
        )
    await session.commit()


@pytest.mark.parametrize("case", CASES)
async def test_blank_message_is_rejected(case: Case, session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    service, messages = _service(case, llm, session, settings)

    assert await service.chat(case.key, "   ", case.context) == "Error: no message provided"
    assert llm.requests == []
    assert await messages.get_newest_messages(case.key) == []


@pytest.mark.parametrize("case", CASES)
async def test_chat_saves_both_messages(case: Case, session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("hello")
    service, messages = _service(case, llm, session, settings)

    assert await service.chat(case.key, "hi", case.context) == "hello"

    assert {(m.role, m.content) for m in await messages.get_all_messages(case.key)} == {
        (MessageRole.USER, case.user_message),
        (MessageRole.MODEL, "hello"),
    }


@pytest.mark.parametrize("case", CASES)
async def test_past_messages_are_sent_oldest_first(case: Case, session: AsyncSession, settings: Settings) -> None:
    await _seed(case, session, (MessageRole.USER, "one"), (MessageRole.MODEL, "two"))
    llm = FakeLLMService("reply")
    service, _ = _service(case, llm, session, settings)

    await service.chat(case.key, "three", case.context)

    context = llm.requests[0].context_messages
    assert context is not None
    assert [message.content for message in context] == ["one", "two"]


@pytest.mark.parametrize("case", CASES)
async def test_empty_llm_response_saves_nothing(case: Case, session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("   ")
    service, messages = _service(case, llm, session, settings)

    assert await service.chat(case.key, "hi", case.context) == ""
    assert await messages.get_newest_messages(case.key) == []


@pytest.mark.parametrize("case", CASES)
async def test_llm_error_returns_static_reply_and_saves_nothing(case: Case, session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("upstream down")
    service, messages = _service(case, llm, session, settings)

    reply = await service.chat(case.key, "hi", case.context)

    assert "static crackles" in reply
    assert await messages.get_newest_messages(case.key) == []


@pytest.mark.parametrize("case", CASES)
async def test_user_message_save_failure_returns_error(
    case: Case, monkeypatch: pytest.MonkeyPatch, session: AsyncSession, settings: Settings
) -> None:
    llm = FakeLLMService("reply")
    service, messages = _service(case, llm, session, settings)

    async def _duplicate(*_args: Any) -> Any:
        raise MessageAlreadyExistsError()

    monkeypatch.setattr(messages, "create_message", _duplicate)

    assert await service.chat(case.key, "hi", case.context) == "Error: failed to save message"
    assert await messages.get_newest_messages(case.key) == []


@pytest.mark.parametrize("case", CASES)
async def test_model_message_save_failure_still_returns_reply(
    case: Case, monkeypatch: pytest.MonkeyPatch, session: AsyncSession, settings: Settings
) -> None:
    llm = FakeLLMService("reply")
    service, messages = _service(case, llm, session, settings)
    original = messages.create_message

    async def _fail_on_model(key: int, role: MessageRole, content: str) -> Any:
        if role is MessageRole.MODEL:
            raise MessageAlreadyExistsError()
        return await original(key, role, content)

    monkeypatch.setattr(messages, "create_message", _fail_on_model)

    assert await service.chat(case.key, "hi", case.context) == "reply"
    assert [m.content for m in await messages.get_newest_messages(case.key)] == [case.user_message]


@pytest.mark.parametrize("case", CASES)
async def test_no_transaction_is_open_during_the_llm_call(case: Case, session: AsyncSession, settings: Settings) -> None:
    # Regression: the read transaction kept a pooled connection checked out for the whole model call.
    in_transaction: list[bool] = []

    class RecordingLLM(FakeLLMService):
        async def call(self, request: Any) -> str:
            in_transaction.append(session.in_transaction())
            return await super().call(request)

    service, _ = _service(case, RecordingLLM("reply"), session, settings)

    await service.chat(case.key, "hi", case.context)

    assert in_transaction == [False]


@pytest.mark.parametrize("case", CASES)
async def test_delete_helpers(case: Case, session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService()
    service, messages = _service(case, llm, session, settings)
    await _seed(
        case,
        session,
        (MessageRole.USER, "one"),
        (MessageRole.MODEL, "two"),
        (MessageRole.USER, "three"),
    )

    await service.delete_last_message(case.key)
    assert [m.content for m in await messages.get_all_messages(case.key)] == ["one", "two"]

    assert await service.delete_all_messages(case.key) == 2
    assert await messages.get_all_messages(case.key) == []


async def test_private_prompt_contains_user_context_and_info(session: AsyncSession, settings: Settings) -> None:
    await UserInfoRepository(session).create_user_info(1, "likes cats")
    await session.commit()
    llm = FakeLLMService("hello alice")
    service, _ = _service(PRIVATE_CASE, llm, session, settings)

    assert await service.chat(1, "hi", PRIVATE_CONTEXT) == "hello alice"

    request = llm.requests[0]
    assert request.user_prompt == "hi"
    assert request.context_messages == []
    assert "User: alice (ID: 1)" in (request.system_prompt or "")
    assert "likes cats" in (request.system_prompt or "")


async def test_private_missing_user_info_still_answers(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("reply")
    service, _ = _service(PRIVATE_CASE, llm, session, settings)

    assert await service.chat(1, "hi", PRIVATE_CONTEXT) == "reply"
    assert "Information provided by the user" not in (llm.requests[0].system_prompt or "")


async def test_guild_prompt_contains_formatted_message_and_server(session: AsyncSession, settings: Settings) -> None:
    llm = FakeLLMService("hello bob")
    service, _ = _service(GUILD_CASE, llm, session, settings)

    assert await service.chat(7, "hi", GUILD_CONTEXT) == "hello bob"

    request = llm.requests[0]
    assert request.user_prompt == GUILD_USER_MESSAGE
    assert "Server Name: Test Guild" in (request.system_prompt or "")
