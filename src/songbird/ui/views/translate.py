from discord.ui import DesignerView, TextDisplay

from songbird.ui.custom_components import generate_container
from songbird.utils.text import truncate_text


class TranslateView(DesignerView):
    def __init__(self, source_name: str, target_name: str, translated_text: str) -> None:
        super().__init__(timeout=180)
        self.add_item(
            generate_container(
                title=f"## {source_name} > {target_name}",
                # TextDisplay stops at 4000 characters.
                components=[TextDisplay(truncate_text(translated_text, 4000))],  # pyright: ignore[reportUnknownArgumentType]
            )
        )
