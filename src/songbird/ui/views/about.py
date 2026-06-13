from typing import Any

from discord import ButtonStyle, Color
from discord.ui import ActionRow, Button, DesignerView, Section, Separator, TextDisplay, Thumbnail

from songbird.bot import SongbirdBot
from songbird.ui.custom_components import generate_container

INVITE_LINK = "https://discord.com/oauth2/authorize?client_id="


class _ButtonRow(ActionRow[Any]):
    def __init__(self, bot: SongbirdBot) -> None:
        super().__init__()

        # Invite Button
        invite_link = INVITE_LINK + str(bot.user.id) if bot.user else ""
        is_invite_enabled = bot.app_info.bot_public
        self.add_item(Button(label="Invite", url=invite_link, disabled=not is_invite_enabled, style=ButtonStyle.url))

        # Source Button
        source_link = bot.settings.bot.source_code_url
        self.add_item(Button(label="Source", url=source_link, disabled=not source_link))

        # Privacy Policy Button
        privacy_link = bot.settings.bot.privacy_policy_url
        self.add_item(Button(label="Privacy", url=privacy_link, disabled=not privacy_link))

        # Terms of Service Button
        terms_link = bot.settings.bot.terms_of_service_url
        self.add_item(Button(label="Terms", url=terms_link, disabled=not terms_link))


class AboutView(DesignerView):
    def __init__(self, bot: SongbirdBot) -> None:
        super().__init__()
        if not bot.user:
            return

        love_message = f"-# *Made with :hearts: by <@{owner}>*" if (owner := bot.settings.bot.owner_id) else "-# *Made with :hearts:*"

        self.add_item(
            generate_container(
                title=f"## About {bot.user.name}",
                components=[
                    Section(
                        TextDisplay(bot.settings.bot.short_description),
                        accessory=Thumbnail(url=bot.user.display_avatar.url),
                    ),
                    TextDisplay(love_message),
                    Separator(),
                    _ButtonRow(bot),
                ],
                color=Color.fuchsia(),
            )
        )
