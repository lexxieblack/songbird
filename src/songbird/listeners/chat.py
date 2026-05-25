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

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_guild = isinstance(message.channel, (discord.TextChannel, discord.Thread))
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

                channel_name = f"DM with {message.author.name}" if is_dm else message.channel.name  # type: ignore

                logger.info("Calling chat handler", user_id=message.author.id, channel_name=channel_name)

                response = await chat_handler.chat(
                    user_id=message.author.id,
                    message=content,
                    username=message.author.name,
                    display_name=message.author.display_name,
                    guild_name=message.guild.name if message.guild else None,
                    channel_name=channel_name,
                )

        else:
            logger.info(
                "Message is in guild",
                user_id=message.author.id,
                guild_name=message.guild.name if message.guild else None,
            )
            async with get_session(services) as session:
                await message.channel.trigger_typing()
                conversation_service = create_guild_conversation_service(session, services)
                chat_handler = GuildChatHandler(settings, conversation_service)

                channel_name = f"DM with {message.author.name}" if is_dm else message.channel.name  # type: ignore

                logger.info("Calling chat handler", user_id=message.author.id, channel_name=channel_name)

                response = await chat_handler.chat(
                    guild_id=message.guild.id,  # type: ignore
                    message=content,
                    username=message.author.name,
                    display_name=message.author.display_name,
                    guild_name=message.guild.name if message.guild else None,
                    channel_name=channel_name,
                )

        if not response:
            logger.info("No response generated", user_id=message.author.id)
            return

        logger.info("Response received", user_id=message.author.id, response_length=len(response))

        await send_messages(message.channel, response)
        logger.info("Response sent successfully", user_id=message.author.id)
