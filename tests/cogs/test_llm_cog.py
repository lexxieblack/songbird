# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

"""`LLMCog` slash commands: deferral, ban checks, handlers and follow-ups."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.cogs import llm as llm_cog_module
from songbird.cogs.llm import LLMCog
from songbird.models.chat.base import MessageRole
from songbird.models.chat.message import Message
from songbird.ui.views.manage import ManageView
from songbird.utils.id_factory import make_id
from tests.cogs._support import invoke
from tests.support.discord import FakeCtx

pytestmark = pytest.mark.discord


def _fake(ctx: discord.ApplicationContext) -> FakeCtx:
    return cast(FakeCtx, ctx)


def _services(bot: SongbirdBot) -> Any:
    return cast(Any, bot.services)


def _set_author_names(ctx: FakeCtx, *, user_id: int | None = None) -> None:
    author = cast(Any, ctx.author)
    if user_id is not None:
        author.id = user_id
    author.name = "lexxie"
    author.display_name = "Lexxie"
    cast(Any, ctx.guild).name = "Guild"
    cast(Any, ctx.channel).name = "general"


def _capture_send(ctx: FakeCtx) -> AsyncMock:
    # `followup.send` is called positionally by these commands; the shared fake only takes kwargs.
    send = AsyncMock()
    setattr(ctx.followup, "send", send)  # noqa: B010 - mypy forbids assigning a method
    return send


class FakeSummary:
    def __init__(self, result: str | None) -> None:
        self.result = result
        self.error: Exception | None = None
        self.texts: list[str] = []

    async def summarize(self, text: str) -> str | None:
        if self.error is not None:
            raise self.error
        self.texts.append(text)
        return self.result


class FakeQuickchat:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.messages: list[str] = []

    async def quickchat(self, message: str) -> str:
        self.messages.append(message)
        return self.answer


class FakeConversation:
    def __init__(self, answer: str | None) -> None:
        self.answer = answer
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    async def chat(self, user_id: int, message: str, context: Any) -> str | None:
        if self.error is not None:
            raise self.error
        self.calls.append({"user_id": user_id, "message": message, "context": context})
        return self.answer


class FakeMessageRepo:
    def __init__(self, messages: list[Message]) -> None:
        self.messages = messages

    async def get_all_messages(self, _user_id: int) -> list[Message]:
        return self.messages


@pytest.fixture
def cog(fake_bot: SongbirdBot) -> LLMCog:
    return LLMCog(fake_bot)


async def test_summary_defers_and_truncates_followup(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeSummary("x" * 2100)
    monkeypatch.setattr(cog, "summary_handler", handler)
    ctx = _fake(fake_ctx)
    send = _capture_send(ctx)

    await invoke(cog, "summary", fake_ctx, text="long text")

    assert ctx.defer_calls == [{}]
    assert handler.texts == ["long text"]
    send.assert_awaited_once()
    call = send.await_args
    assert call is not None
    args, kwargs = call
    assert len(args[0]) == 2000
    assert args[0].endswith("...")
    assert isinstance(kwargs["allowed_mentions"], discord.AllowedMentions)


async def test_summary_with_no_text_uses_empty_string(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeSummary("summary")
    monkeypatch.setattr(cog, "summary_handler", handler)
    ctx = _fake(fake_ctx)
    send = _capture_send(ctx)

    await invoke(cog, "summary", fake_ctx, text=None)

    assert handler.texts == [""]
    assert send.await_args is not None
    assert send.await_args.args[0] == "summary"


async def test_summary_with_nothing_to_summarize_deletes_followup(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    monkeypatch.setattr(cog, "summary_handler", FakeSummary(None))
    ctx = _fake(fake_ctx)

    await invoke(cog, "summary", fake_ctx, text="")

    assert ctx.followup.calls == [("delete", {"reason": "Nothing to summarize."})]


async def test_summary_failure_sends_error(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeSummary("unused")
    handler.error = RuntimeError("llm down")
    monkeypatch.setattr(cog, "summary_handler", handler)
    ctx = _fake(fake_ctx)

    await invoke(cog, "summary", fake_ctx, text="text")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Summarization failed."
    assert ctx.last_ephemeral is True


async def test_quickchat_sends_answer(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    handler = FakeQuickchat("42")
    monkeypatch.setattr(cog, "quickchat_handler", handler)
    ctx = _fake(fake_ctx)
    send = _capture_send(ctx)

    await invoke(cog, "quickchat", fake_ctx, question="meaning")

    assert ctx.defer_calls == [{}]
    assert handler.messages == ["meaning"]
    assert send.await_args is not None
    assert send.await_args.args[0] == "42"


async def test_chat_passes_guild_and_channel_context(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    ctx = _fake(fake_ctx)
    _set_author_names(ctx, user_id=7)
    send = _capture_send(ctx)
    conversation = FakeConversation("hi there")

    @asynccontextmanager
    async def session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        yield SimpleNamespace()

    monkeypatch.setattr(llm_cog_module, "get_session", session)
    monkeypatch.setattr(llm_cog_module, "create_private_conversation_service", lambda *_args: conversation)

    await invoke(cog, "chat", fake_ctx, message="hello")

    assert ctx.defer_calls == [{}]
    call = conversation.calls[0]
    assert call["user_id"] == 7
    assert call["message"] == "hello"
    assert call["context"].username == "lexxie"
    assert call["context"].display_name == "Lexxie"
    assert call["context"].guild_name == "Guild"
    assert call["context"].channel_name == "general"
    assert send.await_args is not None
    assert send.await_args.args[0] == "hi there"


async def test_chat_without_answer_deletes_followup(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    conversation = FakeConversation(None)
    ctx = _fake(fake_ctx)
    _set_author_names(ctx)

    @asynccontextmanager
    async def session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        yield SimpleNamespace()

    monkeypatch.setattr(llm_cog_module, "get_session", session)
    monkeypatch.setattr(llm_cog_module, "create_private_conversation_service", lambda *_args: conversation)

    await invoke(cog, "chat", fake_ctx, message="hello")

    assert ctx.followup.calls == [("delete", {"reason": "No response generated."})]


async def test_chat_failure_sends_error(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    conversation = FakeConversation("unused")
    conversation.error = RuntimeError("boom")
    ctx = _fake(fake_ctx)
    _set_author_names(ctx)

    @asynccontextmanager
    async def session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        yield SimpleNamespace()

    monkeypatch.setattr(llm_cog_module, "get_session", session)
    monkeypatch.setattr(llm_cog_module, "create_private_conversation_service", lambda *_args: conversation)

    await invoke(cog, "chat", fake_ctx, message="hello")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Chat failed."


async def test_manage_responds_with_view(cog: LLMCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "manage", fake_ctx)

    assert isinstance(ctx.respond_calls[0]["view"], ManageView)


async def test_export_sends_json_file(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    ctx = _fake(fake_ctx)
    message = Message(
        id=make_id(),
        user_id=1,
        role=MessageRole.USER,
        content="hello",
        created_at=datetime(2024, 1, 2, 3, 4, tzinfo=UTC),
    )

    @asynccontextmanager
    async def session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        yield SimpleNamespace()

    monkeypatch.setattr(llm_cog_module, "get_session", session)
    monkeypatch.setattr(llm_cog_module, "get_message_repo", lambda _session: FakeMessageRepo([message]))

    await invoke(cog, "export", fake_ctx)

    assert ctx.defer_calls == [{"ephemeral": True}]
    method, kwargs = ctx.followup.calls[0]
    assert method == "send"
    assert kwargs["file"].filename == "conversation_export.json"
    assert isinstance(kwargs["allowed_mentions"], discord.AllowedMentions)


async def test_export_without_history_sends_error(
    monkeypatch: pytest.MonkeyPatch,
    cog: LLMCog,
    fake_ctx: discord.ApplicationContext,
) -> None:
    ctx = _fake(fake_ctx)

    @asynccontextmanager
    async def session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        yield SimpleNamespace()

    monkeypatch.setattr(llm_cog_module, "get_session", session)
    monkeypatch.setattr(llm_cog_module, "get_message_repo", lambda _session: FakeMessageRepo([]))

    await invoke(cog, "export", fake_ctx)

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "No conversation history found."
