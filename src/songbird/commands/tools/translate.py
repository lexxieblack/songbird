from songbird.services.translation import TranslationService
from songbird.utils.logging import get_logger
from songbird.utils.text import truncate_text


class TranslateHandler:
    def __init__(self, translation_service: TranslationService) -> None:
        self.translation_service = translation_service
        self.logger = get_logger(__name__)

    async def translate_to_message(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> str:
        source_lang = source_lang or "auto"
        translated_text = await self.translate(text, target_lang, source_lang)

        if source_lang == "auto":
            source_lang = await self.detect_language(text)

        source_name = self.get_language_name(source_lang)
        target_name = self.get_language_name(target_lang)

        message_text = f"## {source_name} > {target_name}\n{translated_text}"
        return truncate_text(message_text, 2000)

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
