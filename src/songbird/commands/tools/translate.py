from songbird.services.translation import TranslationService
from songbird.utils.logging import get_logger


class TranslateHandler:
    def __init__(self, translation_service: TranslationService) -> None:
        self.translation_service = translation_service
        self.logger = get_logger(__name__)

    async def translate_with_meta(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> tuple[str, str, str]:
        source_lang = source_lang or "auto"
        translated_text = await self.translate(text, target_lang, source_lang)

        if source_lang == "auto":
            source_lang = await self.detect_language(text)

        source_name = self.get_language_name(source_lang)
        target_name = self.get_language_name(target_lang)

        return source_name, target_name, translated_text

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> str:
        source_lang = source_lang or "auto"
        translated_text = await self.translation_service.translate(
            text=text,
            target_lang=target_lang,
            source_lang=source_lang,
        )

        return translated_text

    def get_language_name(self, lang: str) -> str:
        return self.translation_service.get_language_name(lang)

    async def detect_language(self, text: str) -> str:
        return await self.translation_service.detect_language(text)
