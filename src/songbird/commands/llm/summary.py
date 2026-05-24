from songbird.config import Settings
from songbird.models.llm import LLMRequest
from songbird.services.llm import LLMService
from songbird.utils.logging import get_logger


class SummaryHandler:
    def __init__(self, settings: Settings, llm_service: LLMService) -> None:
        self.llm = llm_service
        self.logger = get_logger(__name__)
        self.system_prompt = settings.llm.summary_system_prompt

    async def summarize(self, text: str) -> str | None:
        if not text or not text.strip():
            self.logger.warning("Summarize text called with empty text")
            return None

        text_stripped = text.strip()
        self.logger.info("Summarizing text", text_length=len(text_stripped))

        llm_request = LLMRequest(
            user_prompt=text,
            system_prompt=self.system_prompt,
        )

        try:
            self.logger.info("Generating summary", text_length=len(text))
            return await self.llm.call(llm_request)
        except Exception as e:
            self.logger.error("Failed to generate summary", error=str(e))
            return "Error: failed to generate summary"
