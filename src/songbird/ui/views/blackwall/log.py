from datetime import UTC, datetime

from discord import Member, Message
from discord.ui import Container, DesignerView, Section, TextDisplay, Thumbnail

from songbird.utils.text import format_code_block, humanize_timedelta


class BlackwallLogView(DesignerView):
    def __init__(self, member: Member, message: Message) -> None:
        super().__init__()

        container = Container()

        container.add_item(
            Section(
                TextDisplay("## Blackwall Trigger"),
                TextDisplay(f"**User:** {member.mention}"),
                TextDisplay(f"**Username:** {member.name}"),
                accessory=Thumbnail(url=member.display_avatar.url),
            )
        )

        container.add_item(TextDisplay(f"**Account Age:** {humanize_timedelta(datetime.now(UTC) - member.created_at)}"))
        if member.joined_at:
            container.add_item(TextDisplay(f"**Joined Server:** {humanize_timedelta(datetime.now(UTC) - member.joined_at)}"))
        if len(member.roles) > 1:
            container.add_item(
                TextDisplay(f"**Roles:** {', '.join(role.mention for role in member.roles if role.id != member.guild.id)}")
            )

        container.add_separator()

        container.add_item(TextDisplay(f"**Message:**\n{format_code_block(message.content)}"))

        self.add_item(container)
