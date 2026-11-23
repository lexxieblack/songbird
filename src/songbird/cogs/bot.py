# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

from typing import TYPE_CHECKING

import discord
from discord.commands import AutocompleteContext

from songbird.cogs.base import BaseCog
from songbird.ui.modals.feedback import FeedbackModal
from songbird.ui.views.about import AboutView
from songbird.ui.views.help import HelpView, build_docs, group_by_category, resolve

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot


class BotCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        self.logger.debug("Tool handlers initialized")

    async def help_autocomplete(self, ctx: AutocompleteContext) -> list[discord.OptionChoice]:
        typed = str(ctx.value or "").lower()
        docs = build_docs(self.bot.walk_application_commands())
        choices = [
            discord.OptionChoice(name=f"{group.category.label} (category)", value=group.category.label)
            for group in group_by_category(docs)
        ]
        choices += [discord.OptionChoice(name=doc.label, value=doc.name) for doc in docs]
        return [choice for choice in choices if typed in choice.name.lower()][:25]

    @discord.slash_command(name="help", description="Browse all bot commands")
    async def help(
        self,
        ctx: discord.ApplicationContext,
        query: str | None = discord.Option(  # type: ignore[assignment]
            str,
            description="Open a command or category directly",
            required=False,
            default=None,
            autocomplete=help_autocomplete,
        ),
    ) -> None:
        docs = build_docs(self.bot.walk_application_commands())
        view = HelpView(self.bot, docs, ctx.author.id) if not query else resolve(self.bot, docs, query, ctx.author.id)
        if view is None:
            await ctx.respond(
                "No command or category matches that.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
            )
            return
        await ctx.respond(view=view, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(name="about", description="Get information about the bot")
    async def about(self, ctx: discord.ApplicationContext) -> None:
        main_view = AboutView(self.bot)
        await ctx.respond(view=main_view, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(name="feedback", description="Send feedback to the bot owner")
    async def feedback(self, ctx: discord.ApplicationContext) -> None:
        if self.settings.bot.feedback_channel_id is None:
            await ctx.respond("Feedback is disabled.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return

        try:
            await ctx.response.send_modal(modal=FeedbackModal(self.services, self.bot))
        except Exception as e:
            self.logger.error("Feedback failed", error=e)
            await ctx.respond("Feedback failed.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(BotCog(bot))
