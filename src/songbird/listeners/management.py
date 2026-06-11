import contextlib

import discord
import structlog

from songbird.bot import SongbirdBot

logger = structlog.get_logger(__name__)


def load_guild_ban_listener(bot: SongbirdBot) -> None:
    @bot.listen()
    async def on_guild_join(guild: discord.Guild) -> None:
        if not await bot.services.management.check_guild_banned(guild.id):
            return

        bot.logger.info("Leaving banned guild", guild_id=guild.id, guild_name=guild.name)

        owner_name = str(guild.owner) if guild.owner else "Unknown"
        member_count = guild.member_count or 0

        await bot.message_owner(
            f"Left banned guild **{guild.name}** (ID: {guild.id})\nOwner: {owner_name}\nMembers: {member_count}"
        )

        with contextlib.suppress(discord.HTTPException, discord.Forbidden):
            await guild.leave()
