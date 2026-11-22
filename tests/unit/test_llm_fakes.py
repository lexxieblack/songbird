"""The LLM fakes hold up end to end: sync client fake under ``to_thread``, recording service fake."""

from types import SimpleNamespace

from tests.support.llm import FakeLLMService

from songbird.config import Settings
from songbird.models.llm import LLMRequest
from songbird.services.llm import LLMService


# The fixture patches songbird.services.llm.Client; LLMService.__init__ picks the fake up.
async def test_call_returns_fake_response(settings: Settings, fake_genai_client: SimpleNamespace) -> None:  # noqa: ARG001
    service = LLMService(settings)
    result = await service.call(LLMRequest(user_prompt="hi"))
    assert result == "fake response"


async def test_fake_service_records_requests() -> None:
    service = FakeLLMService("first", "second")
    first = LLMRequest(user_prompt="one")
    second = LLMRequest(user_prompt="two")

    assert await service.call(first) == "first"
    assert await service.call(second) == "second"
    assert service.requests == [first, second]
