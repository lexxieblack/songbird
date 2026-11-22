from typing import Any

from discord import MediaGalleryItem
from discord.ui import Container, DesignerView, MediaGallery

from songbird.utils.constants import SColor


class BlackwallDefaultWarningView(DesignerView):
    def __init__(self, warning_url: str | None) -> None:
        super().__init__()
        container: Container[Any] = Container()
        container.colour = SColor.BLACKWALL

        if warning_url:
            container.add_item(MediaGallery(MediaGalleryItem(url=warning_url)))  # type: ignore[no-untyped-call]
            container.add_separator()
        container.add_text("### [WARNING] UNAUTHORIZED DATA STREAM DETECTED.")
        container.add_text("*This channel is actively monitored by automated NetWatch protocols.*")
        container.add_text("⛔ Do not post messages in this channel ⛔")
        container.add_text("*Any messages in this node will trigger immediate automated containment actions against your account.*")
        container.add_separator()
        container.add_text("-# Songbird Defence Systems // Node ID: `#BLACKWALL`")

        self.add_item(container)
