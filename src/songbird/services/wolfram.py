import httpx
from structlog import BoundLogger

from songbird.config import Settings
from songbird.utils.env import load_from_env
from songbird.utils.logging import get_logger


class WolframService:
    def __init__(
        self,
        settings: Settings,
        logger: BoundLogger | None = None,
    ) -> None:
        self._api_key = settings.wolfram.api_key
        self._api_url = "http://api.wolframalpha.com/v1/simple"
        self._logger = logger or get_logger(__name__)

    async def query(self, question: str) -> bytes:
        params = {
            "i": question,
            "appid": self._api_key,
            "background": "181a1c",
            "foreground": "ffffff",
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                self._logger.info(
                    "Wolfram query started",
                    query=question,
                )

                response = await client.get(self._api_url, params=params, follow_redirects=True)

                self._logger.info(
                    "Wolfram query completed",
                    query=question,
                    status_code=response.status_code,
                )

                # Handle different error status codes
                if response.status_code == 501:
                    raise Exception("Wolfram Alpha could not understand the query")
                elif response.status_code == 400:
                    raise Exception("Invalid query format")
                elif response.is_error:
                    raise Exception("Error querying Wolfram Alpha")

                result_gif = response.content

                if not result_gif:
                    raise Exception("No result returned from Wolfram Alpha")

                return result_gif

        except httpx.TimeoutException as e:
            self._logger.error(
                "Wolfram query timed out",
                query=question,
                error=str(e),
            )
            raise Exception("Request to Wolfram Alpha timed out") from e

        except httpx.RequestError as e:
            self._logger.error(
                "Wolfram query failed",
                query=question,
                error=str(e),
            )
            raise Exception("Network error while querying Wolfram Alpha") from e

        except Exception as e:
            self._logger.error(
                "Wolfram query failed",
                query=question,
                error=str(e),
            )
            raise
