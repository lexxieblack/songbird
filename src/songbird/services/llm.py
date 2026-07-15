import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from google.genai import Client
from google.genai.types import (
    Content,
    GenerateContentConfig,
    GoogleSearch,
    HttpOptions,
    HttpRetryOptions,
    Part,
    Tool,
)
from structlog import BoundLogger

from songbird.models.chat.base import MessageRole
from songbird.models.llm import LLMRequest
from songbird.utils.logging import get_logger

if TYPE_CHECKING:
    from songbird.config import Settings


class LLMService:
    def __init__(
        self,
        settings: "Settings",
        logger: BoundLogger | None = None,
    ) -> None:
        self._model = settings.llm.model
        self._fallback_model = settings.llm.fallback_model
        self._primary_exhausted = False
        self._exhausted_date = datetime.now(UTC).date()
        retry = settings.llm.retry
        self._client = Client(
            api_key=settings.llm.api_key,
            http_options=HttpOptions(
                retry_options=HttpRetryOptions(
                    attempts=retry.max_attempts,
                    initial_delay=retry.initial_delay,
                    max_delay=retry.max_delay,
                ),
                timeout=120000,  # 2 minutes in milliseconds
            ),
        )
        self.logger = logger or get_logger(__name__)

    async def call(self, request: LLMRequest) -> str:
        self._check_reset()
        messages = self._build_messages(request)
        return await self._call_llm(request.system_prompt, messages)

    def _check_reset(self) -> None:
        today = datetime.now(UTC).date()
        if self._exhausted_date != today:
            self._primary_exhausted = False
            self._exhausted_date = today

    @staticmethod
    def _is_quota_error(e: Exception) -> bool:
        code = getattr(e, "code", None)
        if code == 429:
            return True
        msg = str(e).lower()
        return "quota" in msg or "exhausted" in msg or "rate" in msg

    def _build_config(self, system_prompt: str | None = None) -> GenerateContentConfig:
        return GenerateContentConfig(
            system_instruction=system_prompt,
            # thinking_config=ThinkingConfig(thinking_level=ThinkingLevel.LOW),
            tools=[
                Tool(google_search=GoogleSearch()),
                # Tool(url_context=UrlContext()),
            ],
        )

    async def _call_llm(
        self,
        system_prompt: str | None = None,
        messages: list[Content] | None = None,
    ) -> str:
        model = self._fallback_model if self._primary_exhausted else self._model

        self.logger.info(
            "LLM call",
            model=model,
            message_count=len(messages or []),
            primary_exhausted=self._primary_exhausted,
        )

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=messages,
                config=self._build_config(system_prompt),
            )
            return response.text or ""
        except Exception as e:
            if model == self._model and self._is_quota_error(e):
                self._primary_exhausted = True
                self.logger.info("Primary model exhausted, falling back", error=str(e), fallback=self._fallback_model)
                return await self._call_llm(system_prompt, messages)
            raise

    def _build_messages(self, request: LLMRequest) -> list[Content]:
        messages: list[Content] = []

        if request.context_messages:
            for message in request.context_messages:
                messages.append(
                    Content(
                        role=message.role.value,
                        parts=[Part(text=message.content)],
                    )
                )

        messages.append(
            Content(
                role=MessageRole.USER.value,
                parts=[Part(text=request.user_prompt)],
            )
        )

        return messages
