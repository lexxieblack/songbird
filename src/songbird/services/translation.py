from googletrans import Translator  # pyright: ignore[reportMissingTypeStubs]
from pycountry import languages
from structlog import BoundLogger

from songbird.utils.logging import get_logger


class TranslationService:
    def __init__(self, logger: BoundLogger | None = None) -> None:
        self.logger = logger or get_logger(__name__)
        self.translator = Translator()

    def get_language_code(self, language: str) -> str | None:
        try:
            lang_code = languages.lookup(language)  # pyright: ignore[reportUnknownVariableType]
            return lang_code.alpha_2  # type: ignore[no-any-return]
        except (LookupError, AttributeError):
            return None

    def get_language_name(self, language: str) -> str:
        try:
            if len(language) == 2:
                lang = languages.get(alpha_2=language)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                return lang.name if lang else language  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            return languages.lookup(language).name  # type: ignore[no-any-return]
        except LookupError:
            return language

    async def close(self) -> None:
        await self.translator.client.aclose()

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str,
    ) -> str:
        translated_text, _ = await self.translate_with_source(text, target_lang, source_lang)
        return translated_text

    async def translate_with_source(
        self,
        text: str,
        target_lang: str,
        source_lang: str,
    ) -> tuple[str, str]:
        sl = self.get_language_code(source_lang) or "auto"
        tl = self.get_language_code(target_lang)
        if not tl:
            self.logger.warning("Translation target language not supported", target_lang=target_lang)
            return "Error: target language not supported", sl

        try:
            result = await self.translator.translate(text, src=sl, dest=tl)  # pyright: ignore[reportUnknownVariableType, reportCallIssue]
            self.logger.info(
                "Translation successful",
                source_lang=source_lang,
                target_lang=target_lang,
                text_length=len(text),
            )
            return result.text, result.src
        except Exception as e:
            self.logger.error("Failed to translate text", error=e)
            return "Error: failed to translate text", sl
