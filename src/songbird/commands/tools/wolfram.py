from io import BytesIO

from discord import File

from songbird.services.wolfram import WolframService
from songbird.utils.logging import get_logger


class WolframHandler:
    def __init__(self, wolfram_service: WolframService) -> None:
        self.service = wolfram_service
        self.logger = get_logger(__name__)

    async def query(self, question: str) -> File | None:
        self.logger.info("Wolfram query started", query=question)

        try:
            reply_gif = await self.service.query(question)
        except Exception as e:
            self.logger.error("Wolfram query failed", query=question, error=str(e))
            return None

        self.logger.info("Wolfram query completed", query=question)

        return File(
            fp=BytesIO(reply_gif),
            filename="wolfram.gif",
        )
