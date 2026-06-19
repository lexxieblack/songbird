import json
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from songbird.cogs.base import BaseCog
from songbird.commands.llm.private_chat import PrivateChatHandler
from songbird.commands.llm.quickchat import QuickchatHandler
from songbird.commands.llm.summary import SummaryHandler
from songbird.services.container import (
    create_private_conversation_service,
    get_message_repo,
    get_session,
)
from songbird.ui.views.manage import ManageView
from songbird.utils.discord import create_file_text
from songbird.utils.text import split_message, truncate_text

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot


class LLMCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        self.summary_handler = SummaryHandler(self.settings, self.services.llm)
        self.quickchat_handler = QuickchatHandler(self.settings, self.services.llm)

        self.logger.debug("LLM handlers initialized")

    @discord.slash_command(
        name="summary",
        description="Summarise text or content from a URL",
    )
    async def summary(
        self,
        ctx: discord.ApplicationContext,
        text: str | None = discord.Option(str, description="The text to summarise", required=False, default=None),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer()

        if await self._check_banned(ctx):
            return

        self.logger.info("Summary command", user_id=ctx.author.id, text=text)

        try:
            summary_result = await self.summary_handler.summarize(text or "")
            if not summary_result:
                await ctx.followup.delete(reason="Nothing to summarize.")
                return

            await ctx.followup.send(truncate_text(summary_result, 2000), allowed_mentions=discord.AllowedMentions.none())
            self.logger.info("Summary success", user_id=ctx.author.id)

        except Exception as e:
            self.logger.error("Summarization failed", user_id=ctx.author.id, error=str(e))
            await self.send_error(ctx, "Summarization failed.")

    @discord.slash_command(
        name="quickchat",
        description="Ask a quick question",
    )
    async def quickchat(
        self,
        ctx: discord.ApplicationContext,
        question: str = discord.Option(str, description="The question to ask"),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer()

        if await self._check_banned(ctx):
            return

        self.logger.info("Quickchat command", user_id=ctx.author.id, question=question)

        try:
            answer = await self.quickchat_handler.quickchat(question)
            for chunk in split_message(answer):
                if isinstance(chunk, str):
                    await ctx.followup.send(chunk, allowed_mentions=discord.AllowedMentions.none())
                else:
                    await ctx.followup.send(file=chunk, allowed_mentions=discord.AllowedMentions.none())
            self.logger.info("Quickchat success", user_id=ctx.author.id)

        except Exception as e:
            self.logger.error("Quickchat failed", user_id=ctx.author.id, error=str(e))
            await self.send_error(ctx, "Quickchat failed.")

    @discord.slash_command(
        name="chat",
        description="Chat with Songbird",
    )
    async def chat(
        self,
        ctx: discord.ApplicationContext,
        message: str = discord.Option(str, description="The message to send to Songbird"),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer()

        if await self._check_banned(ctx):
            return

        self.logger.info("Chat command", user_id=ctx.author.id, message=message)

        try:
            async with get_session(self.services) as session:
                conversation_service = create_private_conversation_service(session, self.services)
                chat_handler = PrivateChatHandler(self.settings, conversation_service)

                channel_name = f"DM with {ctx.author.name}" if type(ctx.channel) is discord.DMChannel else ctx.channel.name  # type: ignore

                answer = await chat_handler.chat(
                    user_id=ctx.author.id,
                    message=message,
                    username=ctx.author.name,
                    display_name=ctx.author.display_name,
                    guild_name=ctx.guild.name if ctx.guild else None,
                    channel_name=channel_name,
                )

                if answer:
                    for chunk in split_message(answer):
                        if isinstance(chunk, str):
                            await ctx.followup.send(chunk, allowed_mentions=discord.AllowedMentions.none())
                        else:
                            await ctx.followup.send(file=chunk, allowed_mentions=discord.AllowedMentions.none())
                    self.logger.info("Chat success", user_id=ctx.author.id)
                else:
                    await ctx.followup.delete(reason="No response generated.")

        except Exception as e:
            self.logger.error("Chat failed", user_id=ctx.author.id, error=str(e))
            await self.send_error(ctx, "Chat failed.")

    @discord.slash_command(
        name="manage",
        description="Manage your conversation settings",
    )
    async def manage(self, ctx: discord.ApplicationContext) -> None:
        if await self._check_banned(ctx):
            return

        main_view = ManageView(self.services)
        await ctx.respond(view=main_view, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(
        name="export",
        description="Export your private conversation history as JSON",
    )
    @commands.cooldown(1, 43200, commands.BucketType.user)
    async def export(self, ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)

        if await self._check_banned(ctx):
            return

        self.logger.info("Export command", user_id=ctx.author.id)

        try:
            async with get_session(self.services) as session:
                repo = get_message_repo(session)
                messages = await repo.get_all_messages(ctx.author.id)

                if not messages:
                    await self.send_error(ctx, "No conversation history found.")
                    return

                messages_data = [
                    {"role": m.role.value, "content": m.content, "created_at": m.created_at.isoformat()}
                    for m in messages
                ]

                json_str = json.dumps(messages_data, indent=2)
                file = create_file_text(json_str, "conversation_export.json")
                await ctx.followup.send(file=file, allowed_mentions=discord.AllowedMentions.none())

                self.logger.info("Export command success", user_id=ctx.author.id, message_count=len(messages))

        except Exception as e:
            self.logger.error("Export failed", user_id=ctx.author.id, error=str(e))
            await self.send_error(ctx, "Export failed.")


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(LLMCog(bot))
