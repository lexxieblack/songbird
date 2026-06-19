from songbird.config import Settings
from songbird.models.llm import LLMRequest
from songbird.services.llm import LLMService
from songbird.utils.logging import get_logger


class QuickchatHandler:
    def __init__(self, settings: Settings, llm_service: LLMService) -> None:
        self.llm = llm_service
        self.logger = get_logger(__name__)
        self.system_prompt = settings.llm.quickchat_system_prompt

    async def quickchat(self, message: str) -> str:
        if not message or not message.strip():
            self.logger.warning("Missing text")
            return "Error: no text provided"

        llm_request = LLMRequest(
            user_prompt=message,
            system_prompt=self.system_prompt,
        )

        try:
            self.logger.info("Generating response", text_length=len(message))
            return await self.llm.call(llm_request)
        except Exception as e:
            self.logger.error("Failed to generate response", error=e)
            return "Error: failed to generate response"
