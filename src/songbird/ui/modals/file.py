from io import BytesIO

from discord import AllowedMentions, File, InputTextStyle, Interaction
from discord.ui import InputText, Modal

from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class FileModal(Modal):
    def __init__(self) -> None:
        super().__init__(title="Upload Text as a File")
        self.text = InputText(
            label="Text to send",
            placeholder="Enter the text you want to send...",
            style=InputTextStyle.paragraph,
            min_length=1,
            max_length=4000,
            required=True,
        )
        self.extension = InputText(
            label="File extension (e.g., txt, md, py)",
            placeholder="txt",
            required=False,
        )

        self.add_item(self.text)
        self.add_item(self.extension)

    async def callback(self, interaction: Interaction) -> None:
        text = self.text.value or ""
        extension = self.extension.value.strip() or "txt"  # type: ignore

        file = File(
            # fp=text.encode("utf-8"),
            fp=BytesIO(text.encode("utf-8")),
            filename=f"file.{extension}",
        )
        await interaction.response.send_message(file=file, allowed_mentions=AllowedMentions.none())
