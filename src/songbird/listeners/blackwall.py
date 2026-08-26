import contextlib

import discord
import structlog

from songbird.bot import SongbirdBot

logger = structlog.get_logger(__name__)


def load_blackwall_listener(bot: SongbirdBot) -> None:
    @bot.listen()
    async def on_message(message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        author = message.author
        if not isinstance(author, discord.Member):
            return

        if not bot.services.blackwall:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id

        config = await bot.services.blackwall.get_blackwall(guild_id)
        if config is None or config.channel_id != channel_id:
            return

        if author.guild_permissions.administrator:
            return

        whitelisted = set(config.whitelisted_roles)
        if whitelisted and any(role.id in whitelisted for role in author.roles):
            return

        logger.info(
            "Blackwall triggered",
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=author.id,
        )

        try:
            await author.ban(reason="Blackwall honeypot — unauthorised bot detection", delete_message_seconds=86400)
        except discord.Forbidden:
            logger.warning("Blackwall: missing ban permission", guild_id=guild_id, user_id=author.id)
        except discord.HTTPException as e:
            logger.error("Blackwall: failed to ban user", guild_id=guild_id, user_id=author.id, error=str(e))
        else:
            await bot.services.blackwall.increment_blackwall(guild_id)

        with contextlib.suppress(discord.HTTPException):
            await message.delete()
