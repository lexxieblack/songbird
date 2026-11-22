"""LLM fakes: the service seam callers use, and the Google client seam beneath it."""

from types import SimpleNamespace

import pytest

from songbird.models.llm import LLMRequest


class FakeLLMService:
    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.requests: list[LLMRequest] = []
        self.error: Exception | None = None

    async def call(self, request: LLMRequest) -> str:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self._responses.pop(0) if self._responses else ""


def llm_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


@pytest.fixture
def fake_llm() -> FakeLLMService:
    return FakeLLMService("fake response")


@pytest.fixture
def fake_genai_client(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    def generate_content(**_kwargs: object) -> SimpleNamespace:
        return llm_response("fake response")

    def make_client(**_kwargs: object) -> SimpleNamespace:
        return client

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    monkeypatch.setattr("songbird.services.llm.Client", make_client)
    return client
