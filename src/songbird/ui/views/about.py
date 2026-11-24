from discord.ui import DesignerView, Section, Separator, TextDisplay, Thumbnail

from songbird import __version__
from songbird.bot import SongbirdBot
from songbird.ui.custom_components import BotLinkRow, generate_container
from songbird.utils.constants import SColor


class AboutView(DesignerView):
    def __init__(self, bot: SongbirdBot) -> None:
        super().__init__()
        if not bot.user:
            return

        owner_id = bot.settings.bot.owner_id
        owner_mention = f"<@{owner_id}> · " if owner_id else ""
        love_message = f"-# *Made with :hearts: by {owner_mention}v{__version__}*"

        self.add_item(
            generate_container(
                title=f"## About {bot.user.name}",
                components=[
                    Section(
                        TextDisplay(bot.settings.bot.short_description),
                        accessory=Thumbnail(url=bot.user.display_avatar.url),
                    ),
                    TextDisplay(
                        "**One install, two ways.** Add me to your account and I travel with you; add me to a server and we can share the room. "
                        "Your conversations stay yours either way."
                    ),
                    TextDisplay(love_message),
                    Separator(),
                    BotLinkRow(bot),
                ],  # pyright: ignore[reportUnknownArgumentType]
                color=SColor.SONGBIRD,
            )
        )
