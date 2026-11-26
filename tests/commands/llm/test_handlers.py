"""LLM command handlers: context construction, prompt wiring and failure strings."""

from typing import Any, cast

from songbird.commands.llm.guild_chat import GuildChatHandler
from songbird.commands.llm.private_chat import PrivateChatHandler
from songbird.commands.llm.quickchat import QuickchatHandler
from songbird.commands.llm.summary import SummaryHandler
from songbird.config import Settings
from songbird.models.conversation import ConversationContext
from tests.support.llm import FakeLLMService


class FakeGuildService:
    def __init__(self, answer: str = "reply") -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    async def chat(self, key: int, message: str, context: ConversationContext) -> str:
        self.calls.append({"guild_id": key, "message": message, "context": context})
        return self.answer


class FakePrivateService:
    def __init__(self, answer: str = "reply") -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    async def chat(self, key: int, message: str, context: ConversationContext) -> str:
        self.calls.append({"user_id": key, "message": message, "context": context})
        return self.answer


def _guild_handler(settings: Settings, service: FakeGuildService) -> GuildChatHandler:
    return GuildChatHandler(settings, cast(Any, service))


def _private_handler(settings: Settings, service: FakePrivateService) -> PrivateChatHandler:
    return PrivateChatHandler(settings, cast(Any, service))


async def test_guild_chat_ignores_blank_message(settings: Settings) -> None:
    service = FakeGuildService()
    handler = _guild_handler(settings, service)

    assert await handler.chat(1, "   ", 2, "user", "User") is None
    assert service.calls == []


async def test_guild_chat_builds_context(settings: Settings) -> None:
    service = FakeGuildService("answer")
    handler = _guild_handler(settings, service)

    result = await handler.chat(1, "hello", 2, "user", "User", guild_name="Guild", channel_name="general")

    assert result == "answer"
    call = service.calls[0]
    assert call["guild_id"] == 1
    assert call["message"] == "hello"
    assert call["context"] == ConversationContext(
        user_id=2,
        username="user",
        display_name="User",
        guild_name="Guild",
        channel_name="general",
    )


async def test_private_chat_ignores_blank_message(settings: Settings) -> None:
    service = FakePrivateService()
    handler = _private_handler(settings, service)

    assert await handler.chat(2, "\n", "user", "User") is None
    assert service.calls == []


async def test_private_chat_builds_context(settings: Settings) -> None:
    service = FakePrivateService("answer")
    handler = _private_handler(settings, service)

    result = await handler.chat(2, "hello", "user", "User", guild_name=None, channel_name="dm")

    assert result == "answer"
    call = service.calls[0]
    assert call["user_id"] == 2
    assert call["message"] == "hello"
    assert call["context"].channel_name == "dm"


async def test_quickchat_rejects_blank_message(settings: Settings) -> None:
    llm = FakeLLMService()
    handler = QuickchatHandler(settings, cast(Any, llm))

    assert await handler.quickchat("  ") == "Error: no text provided"
    assert llm.requests == []


async def test_quickchat_uses_configured_prompt(settings: Settings) -> None:
    llm = FakeLLMService("answer")
    handler = QuickchatHandler(settings, cast(Any, llm))

    assert await handler.quickchat("question") == "answer"
    assert llm.requests[0].user_prompt == "question"
    assert llm.requests[0].system_prompt == settings.llm.quickchat_system_prompt


async def test_quickchat_reports_llm_failure(settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("down")
    handler = QuickchatHandler(settings, cast(Any, llm))

    assert await handler.quickchat("question") == "Error: failed to generate response"


async def test_summary_ignores_blank_text(settings: Settings) -> None:
    llm = FakeLLMService()
    handler = SummaryHandler(settings, cast(Any, llm))

    assert await handler.summarize("   ") is None
    assert llm.requests == []


async def test_summary_uses_configured_prompt(settings: Settings) -> None:
    llm = FakeLLMService("summary")
    handler = SummaryHandler(settings, cast(Any, llm))

    assert await handler.summarize("  hello  ") == "summary"
    assert llm.requests[0].user_prompt == "  hello  "
    assert llm.requests[0].system_prompt == settings.llm.summary_system_prompt


async def test_summary_reports_llm_failure(settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("down")
    handler = SummaryHandler(settings, cast(Any, llm))

    assert await handler.summarize("hello") == "Error: failed to generate summary"
