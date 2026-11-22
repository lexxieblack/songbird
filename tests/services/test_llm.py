# pyright: reportPrivateUsage=false

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from songbird.config import Settings
from songbird.models.chat.base import MessageRole
from songbird.models.chat.message import Message
from songbird.models.llm import LLMRequest
from songbird.services.llm import LLMService
from songbird.utils.id_factory import make_id

Handler = Any


def _message(role: MessageRole, content: str) -> Message:
    return Message(id=make_id(), user_id=1, role=role, content=content, created_at=datetime.now(UTC))


def _service(settings: Settings, handler: Any) -> LLMService:
    service = LLMService(settings)
    # Swapping the Google client is the only seam; everything below it is service logic.
    service._client = cast(Any, SimpleNamespace(models=SimpleNamespace(generate_content=handler)))  # pyright: ignore[reportPrivateUsage] # noqa: SLF001
    return service


async def test_call_builds_context_and_config(settings: Settings) -> None:
    calls: list[dict[str, Any]] = []

    def handler(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(text="answer")

    service = _service(settings, handler)
    request = LLMRequest(
        system_prompt="system",
        user_prompt="hello",
        context_messages=[_message(MessageRole.USER, "earlier"), _message(MessageRole.MODEL, "reply")],
    )

    assert await service.call(request) == "answer"

    sent = calls[0]
    assert sent["model"] == settings.llm.model
    assert [part.text for content in sent["contents"] for part in content.parts] == ["earlier", "reply", "hello"]
    assert [content.role for content in sent["contents"]] == ["user", "model", "user"]
    assert sent["config"].system_instruction == "system"
    assert sent["config"].tools[0].google_search is not None


async def test_empty_response_becomes_empty_string(settings: Settings) -> None:
    def _make_namespace(**_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(text="")

    service = _service(settings, _make_namespace)

    assert await service.call(LLMRequest(user_prompt="hi")) == ""


async def test_quota_error_falls_back_and_keeps_using_fallback(settings: Settings) -> None:
    seen: list[str] = []

    def handler(**kwargs: Any) -> SimpleNamespace:
        seen.append(kwargs["model"])
        if kwargs["model"] == settings.llm.model:
            raise RuntimeError("429 quota exceeded")
        return SimpleNamespace(text="fallback answer")

    service = _service(settings, handler)

    assert await service.call(LLMRequest(user_prompt="one")) == "fallback answer"
    assert await service.call(LLMRequest(user_prompt="two")) == "fallback answer"

    assert seen == [settings.llm.model, settings.llm.fallback_model, settings.llm.fallback_model]
    assert service._primary_exhausted  # pyright: ignore[reportPrivateUsage] # noqa: SLF001


async def test_non_quota_error_propagates(settings: Settings) -> None:
    service = _service(settings, _raise(RuntimeError("bad request")))

    with pytest.raises(RuntimeError, match="bad request"):
        await service.call(LLMRequest(user_prompt="hi"))


async def test_quota_error_on_fallback_propagates(settings: Settings) -> None:
    service = _service(settings, _raise(RuntimeError("quota exceeded")))
    service._primary_exhausted = True  # noqa: SLF001

    with pytest.raises(RuntimeError, match="quota exceeded"):
        await service.call(LLMRequest(user_prompt="hi"))


async def test_primary_tries_again_on_a_new_day(settings: Settings) -> None:
    models: list[str] = []

    def handler(**kwargs: Any) -> SimpleNamespace:
        models.append(kwargs["model"])
        return SimpleNamespace(text="ok")

    service = _service(settings, handler)
    service._primary_exhausted = True  # noqa: SLF001
    service._exhausted_date = date(2000, 1, 1)  # noqa: SLF001

    assert await service.call(LLMRequest(user_prompt="hi")) == "ok"

    assert models == [settings.llm.model]
    assert service._primary_exhausted is False  # noqa: SLF001


class _CodedError(Exception):
    code = 429


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_CodedError("anything"), True),
        (RuntimeError("RESOURCE EXHAUSTED"), True),
        (RuntimeError("quota exceeded"), True),
        (RuntimeError("rate limit hit"), True),
        (RuntimeError("failed to generate content"), False),
        (RuntimeError("bad request"), False),
    ],
)
def test_quota_error_detection(error: Exception, expected: bool) -> None:
    assert LLMService._is_quota_error(error) is expected  # noqa: SLF001


def _raise(error: Exception) -> Any:
    def handler(**_kwargs: Any) -> SimpleNamespace:
        raise error

    return handler
