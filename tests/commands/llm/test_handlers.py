"""LLM command handler: prompt wiring, blank input and failure strings."""

from typing import Any, cast

from songbird.commands.llm.handler import LLMHandler
from songbird.config import Settings
from tests.support.llm import FakeLLMService


def _handler(llm: FakeLLMService, system_prompt: str, **results: Any) -> LLMHandler:
    return LLMHandler(cast(Any, llm), system_prompt, **results)


async def test_blank_message_is_rejected(settings: Settings) -> None:
    llm = FakeLLMService()
    handler = _handler(llm, settings.llm.quickchat_system_prompt)

    assert await handler.generate("  ") == "Error: no text provided"
    assert llm.requests == []


async def test_blank_result_can_be_none(settings: Settings) -> None:
    llm = FakeLLMService()
    handler = _handler(llm, settings.llm.summary_system_prompt, empty_result=None)

    assert await handler.generate("   ") is None
    assert llm.requests == []


async def test_uses_configured_prompt(settings: Settings) -> None:
    llm = FakeLLMService("answer")
    handler = _handler(llm, settings.llm.quickchat_system_prompt)

    assert await handler.generate("question") == "answer"
    assert llm.requests[0].user_prompt == "question"
    assert llm.requests[0].system_prompt == settings.llm.quickchat_system_prompt


async def test_reports_llm_failure(settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("down")
    handler = _handler(llm, settings.llm.quickchat_system_prompt)

    assert await handler.generate("question") == "Error: failed to generate response"


async def test_error_result_is_configurable(settings: Settings) -> None:
    llm = FakeLLMService()
    llm.error = RuntimeError("down")
    handler = _handler(llm, settings.llm.summary_system_prompt, error_result="Error: failed to generate summary")

    assert await handler.generate("hello") == "Error: failed to generate summary"
