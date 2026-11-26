from songbird.models.llm import LLMRequest
from songbird.services.llm import LLMService
from songbird.utils.logging import get_logger


class LLMHandler:
    def __init__(
        self,
        llm_service: LLMService,
        system_prompt: str,
        *,
        empty_result: str | None = "Error: no text provided",
        error_result: str = "Error: failed to generate response",
    ) -> None:
        self.llm = llm_service
        self.system_prompt = system_prompt
        self.empty_result = empty_result
        self.error_result = error_result
        self.logger = get_logger(__name__)

    async def generate(self, message: str) -> str | None:
        if not message or not message.strip():
            self.logger.warning("Missing text")
            return self.empty_result

        llm_request = LLMRequest(
            user_prompt=message,
            system_prompt=self.system_prompt,
        )

        try:
            self.logger.info("Generating response", text_length=len(message))
            return await self.llm.call(llm_request)
        except Exception as e:
            self.logger.error("Failed to generate response", error=e)
            return self.error_result
