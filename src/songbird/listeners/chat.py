from contextlib import suppress

import discord

from songbird.bot import SongbirdBot
from songbird.commands.llm.guild_chat import GuildChatHandler
from songbird.commands.llm.private_chat import PrivateChatHandler
from songbird.listeners.common import send_messages
from songbird.services.container import create_guild_conversation_service, create_private_conversation_service, get_session
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


def load_chat(bot: SongbirdBot) -> None:
    settings = bot.settings
    services = bot.services

    @bot.listen()
    async def on_message(message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return

        if await bot.services.management.check_user_banned(message.author.id):  # type: ignore[union-attr]
            logger.info("Ignored message from banned user", user_id=message.author.id)
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_guild = isinstance(message.channel, (discord.TextChannel, discord.Thread))
        guild = message.guild
        if is_guild and guild is not None and await bot.services.management.check_guild_banned(guild.id):  # type: ignore[union-attr]
            logger.info("Ignored message from banned guild", guild_id=guild.id)
            return

        is_mentioned = bot.user in message.mentions if bot.user else False

        if not is_dm and not is_mentioned:
            return

        content = message.content
        if is_mentioned and bot.user:
            content = content.replace(f"<@{bot.user.id}>", bot.user.display_name)
            content = content.replace(f"<@!{bot.user.id}>", bot.user.display_name)

        if not content:
            return

        if not is_dm and not is_guild:
            logger.info(
                "Message skipped: unsupported channel type",
                user_id=message.author.id,
                channel_type=type(message.channel),
            )
            return

        logger.info("Message received", user_id=message.author.id, content=message.content)
        if is_dm:
            logger.info(
                "Message is DM",
                user_id=message.author.id,
                username=message.author.name,
                display_name=message.author.display_name,
            )
            async with get_session(services) as session:
                await message.channel.trigger_typing()
                conversation_service = create_private_conversation_service(session, services)
                chat_handler = PrivateChatHandler(settings, conversation_service)

                channel_name = f"DM with {message.author.name}"

                logger.info("Calling chat handler", user_id=message.author.id, channel_name=channel_name)

                try:
                    response = await chat_handler.chat(
                        user_id=message.author.id,
                        message=content,
                        username=message.author.name,
                        display_name=message.author.display_name,
                        guild_name=message.guild.name if message.guild else None,
                        channel_name=channel_name,
                    )
                except Exception:
                    logger.exception("DM chat handler failed", user_id=message.author.id)
                    response = None

        else:
            logger.info(
                "Message is in guild",
                user_id=message.author.id,
                guild_name=message.guild.name if message.guild else None,
            )
            async with get_session(services) as session:
                await message.channel.trigger_typing()
                guild_conversation_service = create_guild_conversation_service(session, services)
                guild_chat_handler = GuildChatHandler(settings, guild_conversation_service)

                guild_channel_name = message.channel.name  # type: ignore[union-attr]

                logger.info("Calling chat handler", user_id=message.author.id, channel_name=guild_channel_name)

                try:
                    response = await guild_chat_handler.chat(
                        guild_id=message.guild.id,  # type: ignore[union-attr]
                        message=content,
                        user_id=message.author.id,
                        username=message.author.name,
                        display_name=message.author.display_name,
                        guild_name=message.guild.name if message.guild else None,
                        channel_name=guild_channel_name,
                    )
                except Exception:
                    logger.exception("Guild chat handler failed", user_id=message.author.id)
                    response = None

        if not response:
            logger.info("No response generated", user_id=message.author.id)
            await message.channel.send(
                "My neural pathways got a bit scrambled. Try again?",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        logger.info("Response received", user_id=message.author.id, response_length=len(response))

        with suppress(Exception):
            await send_messages(message.channel, response)
        logger.info("Response sent successfully", user_id=message.author.id)
