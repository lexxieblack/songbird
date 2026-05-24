from typing import TYPE_CHECKING

import discord

from songbird.cogs.base import BaseCog
from songbird.commands.llm.private_chat import PrivateChatHandler
from songbird.commands.llm.quickchat import QuickchatHandler
from songbird.commands.llm.summary import SummaryHandler
from songbird.services.container import (
    create_private_conversation_service,
    get_session,
)
from songbird.ui.modals.info import UserInfoModal
from songbird.utils.text import truncate_text

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
        text: discord.Option(
            str,
            description="The text to summarise",
            required=False,
            default=None,
        ),  # type: ignore
    ) -> None:
        await ctx.defer()

        self.logger.info("Summary command", user_id=ctx.author.id, text=text)

        try:
            summary_result = await self.summary_handler.summarize(text)
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
        question: discord.Option(
            str,
            description="The question to ask",
        ),  # type: ignore
    ) -> None:
        await ctx.defer()

        self.logger.info("Quickchat command", user_id=ctx.author.id, question=question)

        try:
            answer = await self.quickchat_handler.quickchat(question)
            await ctx.followup.send(answer, allowed_mentions=discord.AllowedMentions.none())
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
        message: discord.Option(
            str,
            description="The message to send to Songbird",
        ),  # type: ignore
    ) -> None:
        await ctx.defer()

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
                    await self._send_messages(ctx.followup, answer)
                    await ctx.followup.send(answer, allowed_mentions=discord.AllowedMentions.none())
                    self.logger.info("Chat success", user_id=ctx.author.id)
                else:
                    await ctx.followup.delete(reason="No response generated.")

        except Exception as e:
            self.logger.error("Chat failed", user_id=ctx.author.id, error=str(e))
            await self.send_error(ctx, "Chat failed.")

    @discord.slash_command(
        name="info",
        description="Set your user information for Songbird",
    )
    async def info(self, ctx: discord.ApplicationContext):
        try:
            modal = await UserInfoModal.create(ctx.author.id, self.services)
            await ctx.interaction.response.send_modal(modal)

        except Exception as e:
            self.logger.error("Info failed", user_id=ctx.author.id, error=str(e), exc_info=True)
            await self.send_error(ctx, "Info failed.")


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(LLMCog(bot))
