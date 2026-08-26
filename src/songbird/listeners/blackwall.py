import contextlib

import discord

from songbird.bot import SongbirdBot
from songbird.models.management.audit_log import AuditLogAction
from songbird.services.container import create_audit_log_service, get_session
from songbird.ui.views.blackwall import BlackwallLogView
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


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

        blackwall = await bot.services.blackwall.get_blackwall(guild_id)
        if blackwall is None or blackwall.channel_id != channel_id:
            return

        if author.guild_permissions.administrator:
            return

        whitelisted = set(blackwall.whitelisted_roles)
        if whitelisted and any(role.id in whitelisted for role in author.roles):
            return

        logger.info(
            "Blackwall triggered",
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=author.id,
        )

        if blackwall.log_channel_id and isinstance(channel := bot.get_channel(blackwall.log_channel_id), discord.TextChannel):
            view = BlackwallLogView(member=author, message=message)
            await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())

        try:
            # pass
            await author.ban(reason="Blackwall honeypot - unauthorised bot detection", delete_message_seconds=86400)
        except discord.Forbidden:
            logger.warning("Blackwall: missing ban permission", guild_id=guild_id, user_id=author.id)
        except discord.HTTPException as e:
            logger.error("Blackwall: failed to ban user", guild_id=guild_id, user_id=author.id, error=str(e))
        else:
            await bot.services.blackwall.increment_blackwall(guild_id)

            async with get_session(bot.services) as session:
                audit_log = create_audit_log_service(session)
                await audit_log.log(
                    action=AuditLogAction.BLACKWALL_BAN,
                    target_id=author.id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                )

        with contextlib.suppress(discord.HTTPException):
            await message.delete()
