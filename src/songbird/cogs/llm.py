import json
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from songbird.cogs.base import BaseCog
from songbird.commands.llm.handler import LLMHandler
from songbird.listeners.common import send_messages
from songbird.models.conversation import ConversationContext
from songbird.services.container import (
    create_private_conversation_service,
    get_message_repo,
    get_session,
)
from songbird.ui.views.manage import ManageView
from songbird.utils.discord import create_file_text
from songbird.utils.text import truncate_text

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot

# A 25 MB upload caps out around this many message-sized rows; the newest ones are the useful part.
_EXPORT_MESSAGE_LIMIT = 5000


class LLMCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        self.summary_handler = LLMHandler(
            self.services.llm,
            self.settings.llm.summary_system_prompt,
            empty_result=None,
            error_result="Error: failed to generate summary",
        )
        self.quickchat_handler = LLMHandler(self.services.llm, self.settings.llm.quickchat_system_prompt)
        # Decorator cooldowns are fixed at import time, so /export enforces the configured window itself.
        self._export_cooldown: commands.CooldownMapping = commands.CooldownMapping.from_cooldown(  # pyright: ignore[reportUnknownMemberType]
            1, self.settings.llm.export_cooldown_seconds, commands.BucketType.user
        )

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

        self.logger.info("Summary command", user_id=ctx.author.id, text=text)

        try:
            summary_result = await self.summary_handler.generate(text or "")
            if not summary_result:
                await ctx.delete()
                return

            await ctx.followup.send(truncate_text(summary_result, 2000), allowed_mentions=discord.AllowedMentions.none())
            self.logger.info("Summary success", user_id=ctx.author.id)

        except Exception as e:
            self.logger.error("Summarization failed", user_id=ctx.author.id, error=e)
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

        self.logger.info("Quickchat command", user_id=ctx.author.id, question=question)

        try:
            answer = await self.quickchat_handler.generate(question)
            await send_messages(ctx.followup, answer or "")
            self.logger.info("Quickchat success", user_id=ctx.author.id)

        except Exception as e:
            self.logger.error("Quickchat failed", user_id=ctx.author.id, error=e)
            await self.send_error(ctx, "Quickchat failed.")

    @discord.slash_command(
        name="chat",
        description="Chat with Songbird — works in DMs too",
    )
    async def chat(
        self,
        ctx: discord.ApplicationContext,
        message: str = discord.Option(str, description="The message to send to Songbird"),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer()

        self.logger.info("Chat command", user_id=ctx.author.id, message=message)

        if not message.strip():
            await ctx.delete()
            return

        try:
            async with get_session(self.services) as session:
                conversation_service = create_private_conversation_service(session, self.services)

                channel_name = f"DM with {ctx.author.name}" if type(ctx.channel) is discord.DMChannel else ctx.channel.name  # type: ignore

                context = ConversationContext(
                    user_id=ctx.author.id,
                    username=ctx.author.name,
                    display_name=ctx.author.display_name,
                    guild_name=ctx.guild.name if ctx.guild else None,
                    channel_name=channel_name,  # pyright: ignore[reportUnknownArgumentType]
                )

                answer = await conversation_service.chat(key=ctx.author.id, message=message, context=context)

                if answer:
                    await send_messages(ctx.followup, answer)
                    self.logger.info("Chat success", user_id=ctx.author.id)
                else:
                    await ctx.delete()

        except Exception as e:
            self.logger.error("Chat failed", user_id=ctx.author.id, error=e)
            await self.send_error(ctx, "Chat failed.")

    @discord.slash_command(
        name="manage",
        description="Manage your conversation settings",
    )
    async def manage(self, ctx: discord.ApplicationContext) -> None:
        main_view = ManageView(self.services)
        await ctx.respond(view=main_view, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(
        name="export",
        description="Export your private conversation history as JSON",
    )
    async def export(self, ctx: discord.ApplicationContext) -> None:
        # CooldownMapping is typed for Message, but BucketType.user only reads `.author`.
        bucket = self._export_cooldown.get_bucket(ctx)  # type: ignore[arg-type]
        if (retry_after := bucket.update_rate_limit()) is not None:
            raise commands.CommandOnCooldown(bucket, retry_after, commands.BucketType.user)

        await ctx.defer(ephemeral=True)

        self.logger.info("Export command", user_id=ctx.author.id)

        try:
            async with get_session(self.services) as session:
                repo = get_message_repo(session)
                messages = list(reversed(await repo.get_newest_messages(ctx.author.id, _EXPORT_MESSAGE_LIMIT)))

                if not messages:
                    await self.send_error(ctx, "No conversation history found.")
                    return

                messages_data = [
                    {"role": m.role.value, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages
                ]

                json_str = json.dumps(messages_data, indent=2)
                file = create_file_text(json_str, "conversation_export.json")
                await ctx.followup.send(file=file, allowed_mentions=discord.AllowedMentions.none())

                self.logger.info("Export command success", user_id=ctx.author.id, message_count=len(messages))

        except Exception as e:
            self.logger.error("Export failed", user_id=ctx.author.id, error=e)
            await self.send_error(ctx, "Export failed.")


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(LLMCog(bot))
