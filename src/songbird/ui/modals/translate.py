from collections.abc import Awaitable, Callable

from discord import AllowedMentions, InputTextStyle, Interaction, Message
from discord.ui import InputText, Modal

from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class TranslateModal(Modal):
    def __init__(self, translate_callback: Callable[[str, str, (str | None)], Awaitable[str]]) -> None:
        super().__init__(title="Translate Text")
        self.translate_callback = translate_callback
        self.source_language = InputText(
            label="Source Language (Optional)",
            placeholder="auto",
            required=False,
        )
        self.target_language = InputText(
            label="Target Language",
            placeholder="english",
            min_length=1,
        )
        self.text = InputText(
            label="Text to Translate",
            placeholder="Hello world",
            style=InputTextStyle.paragraph,
            min_length=1,
            max_length=4000,
        )

        self.add_item(self.source_language)
        self.add_item(self.target_language)
        self.add_item(self.text)

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        source_language = self.source_language.value.strip()  # type: ignore
        target_language = self.target_language.value.strip()  # type: ignore
        text = self.text.value.strip()  # type: ignore
        translated_text = await self.translate_callback(text, target_language, source_language)

        await interaction.followup.send(translated_text, allowed_mentions=AllowedMentions.none())


class TranslateMessageModal(Modal):
    def __init__(self, message: Message, translate_callback: Callable[[str, str], Awaitable[str]]) -> None:
        super().__init__(title="Translate Text")

        self.text = message.content
        self.translate_callback = translate_callback
        self.target_language = InputText(
            label="Target Language",
            placeholder="Enter the target language...",
            required=True,
        )

        self.add_item(self.target_language)

    async def callback(self, interaction: Interaction) -> None:
        if self.text is None:
            await interaction.respond("Nothing to translate.", ephemeral=True, allowed_mentions=AllowedMentions.none())

        target_language = self.target_language.value.strip()  # type: ignore

        await interaction.response.defer()
        translated_text = await self.translate_callback(self.text, target_language)

        await interaction.followup.send(translated_text, allowed_mentions=AllowedMentions.none())
