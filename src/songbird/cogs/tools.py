from typing import TYPE_CHECKING

import discord

from songbird.cogs.base import BaseCog
from songbird.commands.tools.fix import FixHandler
from songbird.commands.tools.translate import TranslateHandler
from songbird.commands.tools.wolfram import WolframHandler
from songbird.ui.modals.file import FileModal
from songbird.ui.modals.translate import TranslateMessageModal, TranslateModal
from songbird.ui.views.translate import TranslateView

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot


class ToolsCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        self.translate_handler = TranslateHandler(self.services.translation)
        self.wolfram_handler = WolframHandler(self.services.wolfram)
        self.fix_handler = FixHandler(self.services.link_fixer)

        self.logger.debug("Tool handlers initialized")

    @discord.slash_command(
        name="translate",
        description="Translate text between languages using Google Translate",
    )
    async def translate(
        self,
        ctx: discord.ApplicationContext,
        text: str | None = discord.Option(str, description="The text to translate", required=False, default=None),  # type: ignore[assignment]
        to_lang: str = discord.Option(str, description="Target language to translate to", required=False, default="en"),  # type: ignore[assignment]
        from_lang: str | None = discord.Option(str, description="Source language (auto-detect if not specified)", required=False, default=None),  # type: ignore[assignment]
    ) -> None:
        if await self._check_banned(ctx):
            return

        if not text:
            modal = TranslateModal(self.translate_handler.translate_with_meta)
            await ctx.interaction.response.send_modal(modal)
            return

        await ctx.defer()

        self.logger.info(
            "Translate command",
            user_id=ctx.author.id,
            to_lang=to_lang,
            from_lang=from_lang,
            text_length=len(text),
        )

        try:
            source_name, target_name, translated_text = await self.translate_handler.translate_with_meta(
                text=text,
                target_lang=to_lang,
                source_lang=from_lang,
            )

            view = TranslateView(source_name, target_name, translated_text)
            await ctx.followup.send(view=view, allowed_mentions=discord.AllowedMentions.none())

            self.logger.info(
                "Translate success",
                user_id=ctx.author.id,
                source_lang=from_lang,
                target_lang=to_lang,
            )

        except Exception as e:
            self.logger.error("translate_error", user_id=ctx.author.id, error=str(e))
            await self.send_error(ctx, "Translation failed.")

    @discord.message_command(
        name="Translate",
    )
    async def translate_message(
        self,
        ctx: discord.ApplicationContext,
        message: discord.Message,
    ) -> None:
        if await self._check_banned(ctx):
            return

        modal = TranslateMessageModal(message, self.translate_handler.translate_with_meta)
        await ctx.send_modal(modal)

    @discord.slash_command(
        name="file",
        description="Sends a text file with the given content",
    )
    async def file(self, ctx: discord.ApplicationContext) -> None:
        if await self._check_banned(ctx):
            return

        modal = FileModal()
        await ctx.send_modal(modal)

    @discord.slash_command(
        name="wolfram",
        description="Query Wolfram Alpha for computational knowledge",
    )
    async def wolfram(
        self,
        ctx: discord.ApplicationContext,
        query: str = discord.Option(str, description="The query to send to Wolfram Alpha"),  # type: ignore[assignment]
    ) -> None:
        if await self._check_banned(ctx):
            return

        if not query:
            await self.send_error(ctx, "Please provide link to fix.")
            return

        await ctx.defer()

        self.logger.info("Wolfram command", user_id=ctx.author.id, query=query)

        try:
            reply_gif = await self.wolfram_handler.query(query)
            if reply_gif:
                await ctx.followup.send(file=reply_gif)
                self.logger.info("Wolfram query completed", user_id=ctx.author.id, query=query)
            else:
                await self.send_error(ctx, "Wolfram query failed.")

        except Exception as e:
            self.logger.error("Wolfram query failed", user_id=ctx.author.id, query=query, error=str(e))
            await self.send_error(ctx, "Wolfram query failed.")

    @discord.slash_command(
        name="fix",
        description="Fix social media links for better embeds",
    )
    async def fix(
        self,
        ctx: discord.ApplicationContext,
        link: str = discord.Option(str, description="The link to fix and sanitize"),  # type: ignore[assignment]
    ) -> None:
        if await self._check_banned(ctx):
            return

        if not link:
            await self.send_error(ctx, "Please provide a link to fix.")
            return

        await ctx.defer()

        self.logger.info("Fix command", user_id=ctx.author.id, text_length=len(link))

        try:
            fixed_link = await self.fix_handler.fix_link(link)

            await ctx.followup.send(fixed_link)

            self.logger.info("Fix success", user_id=ctx.author.id)

        except Exception as e:
            self.logger.error("Fix error", user_id=ctx.author.id, error=str(e), exc_info=True)
            await self.send_error(ctx, "Link fixing failed.")

    @discord.slash_command(
        name="ping",
        description="Ping the bot",
    )
    async def ping(self, ctx: discord.ApplicationContext) -> None:
        if await self._check_banned(ctx):
            return

        latency = round(self.bot.latency * 1000)
        await ctx.respond(f":satellite: `{latency}`ms")


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(ToolsCog(bot))
