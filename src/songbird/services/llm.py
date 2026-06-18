import asyncio
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
        messages = self._build_messages(request)
        return await self._call_llm(request.system_prompt, messages)

    async def _call_llm(
        self,
        system_prompt: str | None = None,
        messages: list[Content] | None = None,
    ) -> str:
        self.logger.info(
            "LLM call",
            model=self._model,
            message_count=len(messages or []),
        )

        config = GenerateContentConfig(
            system_instruction=system_prompt,
            # thinking_config=ThinkingConfig(thinking_level=ThinkingLevel.LOW),
            tools=[
                Tool(google_search=GoogleSearch()),
                # Tool(url_context=UrlContext()),
            ],
        )

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=messages,
            config=config,
        )

        content = response.text or ""

        self.logger.info(
            "LLM response",
            model=self._model,
            response_length=len(content),
        )

        return content

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
