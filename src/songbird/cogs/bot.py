from typing import TYPE_CHECKING

import discord

from songbird.cogs.base import BaseCog
from songbird.services.container import create_feedback_service, get_session
from songbird.ui.modals.feedback import FeedbackModal
from songbird.ui.views.about import AboutView
from songbird.ui.views.help import HelpView

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot


class BotCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        self.logger.debug("Tool handlers initialized")

    @discord.slash_command(name="help", description="Get information about the bot")
    async def help(self, ctx: discord.ApplicationContext) -> None:
        if await self._check_banned(ctx):
            return
        main_view = HelpView()
        await ctx.respond(view=main_view, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(name="about", description="Get information about the bot")
    async def about(self, ctx: discord.ApplicationContext) -> None:
        if await self._check_banned(ctx):
            return
        main_view = AboutView(self.bot)
        await ctx.respond(view=main_view, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(name="feedback", description="Send feedback to the bot owner")
    async def feedback(self, ctx: discord.ApplicationContext) -> None:
        if await self._check_banned(ctx):
            return
        if self.settings.bot.feedback_channel_id is None:
            await ctx.respond("Feedback is disabled.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return

        try:
            async with get_session(self.services) as session:
                feedback_service = create_feedback_service(session, self.services, self.bot)
                await ctx.response.send_modal(modal=FeedbackModal(feedback_service=feedback_service))
        except Exception as e:
            self.logger.error("Feedback failed", error=str(e))
            await ctx.respond("Feedback failed.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(BotCog(bot))
