import asyncio
from datetime import UTC, datetime, timedelta
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

# Gemini's 429s are usually per-minute limits, so the primary is retried soon instead of being parked until midnight.
_PRIMARY_BLOCK_SECONDS = 300


class LLMService:
    def __init__(
        self,
        settings: "Settings",
        logger: BoundLogger | None = None,
    ) -> None:
        self._model = settings.llm.model
        self._fallback_model = settings.llm.fallback_model
        self._primary_blocked_until: datetime | None = None
        retry = settings.llm.retry
        self._client = Client(
            api_key=settings.llm.api_key,
            http_options=HttpOptions(
                api_version="v1beta",  # system_instruction and google_search are not available on v1
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
        messages = self._build_messages(request)
        return await self._call_llm(request.system_prompt, messages)

    def _primary_blocked(self) -> bool:
        if self._primary_blocked_until is None:
            return False
        if datetime.now(UTC) >= self._primary_blocked_until:
            self._primary_blocked_until = None
            return False
        return True

    @staticmethod
    def _is_quota_error(e: Exception) -> bool:
        code = getattr(e, "code", None)
        if code == 429:
            return True
        msg = str(e).lower()
        return "quota" in msg or "exhausted" in msg or "rate limit" in msg or "rate_limit" in msg

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
        use_primary = not self._primary_blocked()
        model = self._model if use_primary else self._fallback_model

        self.logger.info(
            "LLM call",
            model=model,
            message_count=len(messages or []),
            primary_blocked=not use_primary,
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
            if use_primary and self._is_quota_error(e):
                self._primary_blocked_until = datetime.now(UTC) + timedelta(seconds=_PRIMARY_BLOCK_SECONDS)
                self.logger.info(
                    "Primary model rate-limited, falling back",
                    error=str(e),
                    fallback=self._fallback_model,
                )
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
