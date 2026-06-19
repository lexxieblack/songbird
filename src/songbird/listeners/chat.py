from contextlib import suppress

from discord import AllowedMentions, DeletedReferencedMessage, DMChannel, Message, TextChannel, Thread

from songbird.bot import SongbirdBot
from songbird.commands.llm.guild_chat import GuildChatHandler
from songbird.commands.llm.private_chat import PrivateChatHandler
from songbird.listeners.common import send_messages
from songbird.services.container import create_guild_conversation_service, create_private_conversation_service, get_session
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


async def _is_message_relevant(bot: SongbirdBot, message: Message) -> bool:
    if message.author.bot or not message.content:
        # Ignore own messages and empty messages
        return False

    is_dm = isinstance(message.channel, DMChannel)
    is_guild = isinstance(message.channel, (TextChannel, Thread))

    if is_dm:
        return not await bot.services.management.check_user_banned(message.author.id)  # type: ignore[union-attr]

    if is_guild and bot.user and bot.user in message.mentions:
        if await bot.services.management.check_guild_banned(message.guild.id):  # type: ignore[union-attr]
            message.guild.leave()  # type: ignore
            return False
        return True

    return False


def _get_reply_context(message: Message, user_message: str) -> str:
    if not message.reference:
        return user_message

    reffered_message = message.reference.resolved
    user_message = (
        f"Message from {message.author.display_name} (ID: {message.author.id}, Username: {message.author.name}):"
        "<message>"
        f"{user_message}"
        "</message>"
    )

    if isinstance(reffered_message, Message):
        user_message = user_message + (
            f"In reply to {reffered_message.author.display_name}'s message (ID: {reffered_message.author.id}, Username: {reffered_message.author.name}):"
            "<reply_message>"
            f"{reffered_message.content}"
            "</reply_message>"
        )
    elif isinstance(reffered_message, DeletedReferencedMessage):
        user_message = user_message + "In reply to a deleted message"

    return user_message


async def _handle_dm_message(bot: SongbirdBot, message: Message, user_message: str) -> str | None:
    logger.info(
        "Message is DM",
        user_id=message.author.id,
        username=message.author.name,
        display_name=message.author.display_name,
    )

    async with get_session(bot.services) as session:
        await message.channel.trigger_typing()
        conversation_service = create_private_conversation_service(session, bot.services)
        chat_handler = PrivateChatHandler(bot.settings, conversation_service)

        channel_name = f"DM with {message.author.name}"

        logger.info("Calling chat handler", user_id=message.author.id, channel_name=channel_name)

        try:
            return await chat_handler.chat(
                user_id=message.author.id,
                message=user_message,
                username=message.author.name,
                display_name=message.author.display_name,
                guild_name=message.guild.name if message.guild else None,
                channel_name=channel_name,
            )
        except Exception:
            logger.exception("DM chat handler failed", user_id=message.author.id)
    return None


async def _handle_guild_message(bot: SongbirdBot, message: Message, user_message: str) -> str | None:
    logger.info(
        "Message is in guild",
        user_id=message.author.id,
        guild_name=message.guild.name if message.guild else None,
    )

    async with get_session(bot.services) as session:
        await message.channel.trigger_typing()
        guild_conversation_service = create_guild_conversation_service(session, bot.services)
        guild_chat_handler = GuildChatHandler(bot.settings, guild_conversation_service)

        guild_channel_name = message.channel.name  # type: ignore[union-attr]

        logger.info("Calling chat handler", user_id=message.author.id, channel_name=guild_channel_name)

        try:
            return await guild_chat_handler.chat(
                guild_id=message.guild.id,  # type: ignore[union-attr]
                message=user_message,
                user_id=message.author.id,
                username=message.author.name,
                display_name=message.author.display_name,
                guild_name=message.guild.name if message.guild else None,
                channel_name=guild_channel_name,
            )
        except Exception:
            logger.exception("Guild chat handler failed", user_id=message.author.id)
    return None


def load_chat(bot: SongbirdBot) -> None:
    @bot.listen()
    async def on_message(message: Message) -> None:
        if not await _is_message_relevant(bot, message):
            return

        logger.info("Message received", user_id=message.author.id, content=message.content)

        user_message = message.content
        user_message = user_message.replace(f"<@{bot.user.id}>", bot.user.display_name)  # pyright: ignore[reportOptionalMemberAccess]
        user_message = user_message.replace(f"<@!{bot.user.id}>", bot.user.display_name)  # pyright: ignore[reportOptionalMemberAccess]

        user_message = _get_reply_context(message, user_message)

        if isinstance(message.channel, DMChannel):
            response = await _handle_dm_message(bot, message, user_message)
        else:
            response = await _handle_guild_message(bot, message, user_message)

        if not response:
            logger.info("No response generated", user_id=message.author.id)
            await message.channel.send("My neural pathways got a bit scrambled.", allowed_mentions=AllowedMentions.none())
            return

        logger.info("Response received", user_id=message.author.id, response_length=len(response))

        with suppress(Exception):
            await send_messages(message.channel, response)
        logger.info("Response sent successfully", user_id=message.author.id)
