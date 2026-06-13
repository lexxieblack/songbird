import re

from googletrans import Translator
from httpx import AsyncClient, HTTPStatusError, TimeoutException
from pycountry import languages
from structlog import BoundLogger

from songbird.utils.logging import get_logger

# Pattern for extracting the translated text
PATTERN = r'(?s)class="(?:t0|result-container)">(.*?)<'
TIMEOUT = 5


class TranslationService:
    def __init__(self, logger: BoundLogger | None = None) -> None:
        self.logger = logger or get_logger(__name__)
        self._client = AsyncClient(timeout=10.0)
        self.translator = Translator()

    def get_language_code(self, language: str) -> str | None:
        try:
            lang_code = languages.lookup(language)
            return lang_code.alpha_2  # type: ignore[no-any-return]
        except LookupError:
            return None

    def get_language_name(self, language: str) -> str:
        try:
            if len(language) == 2:
                lang = languages.get(alpha_2=language)
                return lang.name if lang else language
            return languages.lookup(language).name  # type: ignore[no-any-return]
        except LookupError:
            return language

    async def close(self) -> None:
        await self._client.aclose()

    async def detect_language(self, text: str) -> str:
        result = await self.translator.detect(text)
        return result.lang  # type: ignore[no-any-return]

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str,
    ) -> str:
        sl = "auto" if source_lang == "auto" else self.get_language_code(source_lang)
        tl = self.get_language_code(target_lang)
        if not tl:
            self.logger.warning("Translation target language not supported", target_lang=target_lang)
            return "Error: target language not supported"

        try:
            translated_text = await self.translator.translate(text, src=sl, dest=tl)
            self.logger.info(
                "Translation successful",
                source_lang=source_lang,
                target_lang=target_lang,
                text_length=len(text),
            )
            return translated_text.text  # type: ignore[no-any-return]
        except Exception as e:
            self.logger.error("Failed to translate text", error=str(e))
            return "Error: failed to translate text"

    async def translate_old(
        self,
        text: str,
        target_lang: str,
        source_lang: str,
    ) -> str:
        if not text or not text.strip():
            self.logger.warning("No text to translate")
            return "Error: no text provided"

        try:
            sl = "auto" if source_lang == "auto" else self.get_language_code(source_lang)
            tl = self.get_language_code(target_lang)
            if not tl:
                self.logger.warning("Translation target language not supported", target_lang=target_lang)
                return "Error: target language not supported"

            url = "https://translate.google.com/m"
            params = {
                "sl": sl,
                "tl": tl,
                "q": text,
            }

            response = await self._client.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()

            result = re.findall(PATTERN, response.text)
            if result:
                self.logger.info(
                    "Translation successful",
                    source_lang=source_lang,
                    target_lang=target_lang,
                    text_length=len(text),
                )
                return result[0]  # type: ignore[no-any-return]
            else:
                self.logger.info(
                    "Translation failed",
                    source_lang=source_lang or "auto",
                    target_lang=target_lang,
                    text_length=len(text),
                )
                return "Error: translation failed"

        except TimeoutException:
            self.logger.error(
                "Translation timed out",
                target_lang=target_lang,
                source_lang=source_lang,
            )
            return text
        except HTTPStatusError as e:
            self.logger.error(
                "Translation failed with status code",
                status_code=e.response.status_code,
                target_lang=target_lang,
                source_lang=source_lang,
            )
            return text
        except Exception as e:
            self.logger.error(
                "Translation failed with error",
                error=str(e),
                error_type=type(e).__name__,
                target_lang=target_lang,
                source_lang=source_lang,
            )
            return text

        finally:
            await self.close()
