from discord.ui import DesignerView, TextDisplay

from songbird.ui.custom_components import generate_container


class TranslateView(DesignerView):
    def __init__(self, source_name: str, target_name: str, translated_text: str) -> None:
        super().__init__(timeout=180)
        self.add_item(
            generate_container(
                title=f"## {source_name} > {target_name}",
                components=[TextDisplay(translated_text)],
            )
        )
