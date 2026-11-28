from collections.abc import Sequence
from typing import TYPE_CHECKING

import discord
import structlog
from discord.ext import commands

from songbird.cogs.base import BaseCog
from songbird.models.management.exceptions import (
    GuildBanAlreadyExistsError,
    GuildBanNotFoundError,
    UserBanAlreadyExistsError,
    UserBanNotFoundError,
)
from songbird.models.management.guild_ban import GuildBan
from songbird.models.management.user_ban import UserBan

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot

logger = structlog.get_logger(__name__)

# Embed descriptions stop at 4096 characters; 30 rows plus the overflow line stay well under it.
_MAX_BAN_ROWS = 30


def _parse_id(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


class ManagementCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        guild_id = bot.settings.bot.management_guild_id
        if guild_id:
            for cmd in self.get_commands():  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                if isinstance(cmd, discord.ApplicationCommand):
                    cmd.guild_ids = [guild_id]

        self.logger.debug("Management commands initialized")

    @discord.slash_command(name="ban-user", description="Ban a user from using the bot")
    @commands.is_owner()
    async def ban_user(
        self,
        ctx: discord.ApplicationContext,
        user_id: str = discord.Option(str, description="User ID to ban"),  # type: ignore[assignment]
        reason: str | None = discord.Option(str, description="Reason for ban", required=False, default=None),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer(ephemeral=True)

        uid = _parse_id(user_id)
        if uid is None:
            await self.send_error(ctx, "Invalid user ID.")
            return

        try:
            await self.services.management.ban_user(uid, reason)
        except UserBanAlreadyExistsError:
            await self.send_error(ctx, "User already banned.")
            return

        parts = [f"User **{uid}** banned."]
        if reason:
            parts.append(f"Reason: {reason}")
        await self.send_success(ctx, " ".join(parts), ephemeral=True)

    @discord.slash_command(name="unban-user", description="Unban a user from using the bot")
    @commands.is_owner()
    async def unban_user(
        self,
        ctx: discord.ApplicationContext,
        user_id: str = discord.Option(str, description="User ID to unban"),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer(ephemeral=True)

        uid = _parse_id(user_id)
        if uid is None:
            await self.send_error(ctx, "Invalid user ID.")
            return

        try:
            await self.services.management.unban_user(uid)
        except UserBanNotFoundError:
            await self.send_error(ctx, "User not found in ban list.")
            return

        await self.send_success(ctx, f"User **{uid}** unbanned.", ephemeral=True)

    async def _send_ban_list(
        self,
        ctx: discord.ApplicationContext,
        bans: Sequence[UserBan | GuildBan],
        noun: str,
    ) -> None:
        if not bans:
            await self.send_success(ctx, f"No {noun}s are currently banned.", ephemeral=True)
            return

        lines: list[str] = []
        for ban in bans[:_MAX_BAN_ROWS]:
            reason = f" — {ban.reason}" if ban.reason else ""
            ts = ban.created_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"• **{getattr(ban, noun + '_id')}**{reason} (banned {ts})")
        if len(bans) > _MAX_BAN_ROWS:
            lines.append(f"... and {len(bans) - _MAX_BAN_ROWS} more")

        embed = discord.Embed(
            title=f"Banned {noun.title()}s",
            description="\n".join(lines),
            colour=discord.Color.red(),
        )
        await ctx.followup.send(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(name="list-user-bans", description="List all banned users")
    @commands.is_owner()
    async def list_user_bans(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        await ctx.defer(ephemeral=True)
        await self._send_ban_list(ctx, await self.services.management.list_user_bans(), "user")

    @discord.slash_command(name="ban-guild", description="Ban a guild from using the bot")
    @commands.is_owner()
    async def ban_guild(
        self,
        ctx: discord.ApplicationContext,
        guild_id: str = discord.Option(str, description="Guild ID to ban"),  # type: ignore[assignment]
        reason: str | None = discord.Option(str, description="Reason for ban", required=False, default=None),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer(ephemeral=True)

        gid = _parse_id(guild_id)
        if gid is None:
            await self.send_error(ctx, "Invalid guild ID.")
            return

        try:
            await self.services.management.ban_guild(gid, reason)
        except GuildBanAlreadyExistsError:
            await self.send_error(ctx, "Guild already banned.")
            return

        parts = [f"Guild **{gid}** banned."]
        if reason:
            parts.append(f"Reason: {reason}")
        await self.send_success(ctx, " ".join(parts), ephemeral=True)

    @discord.slash_command(name="unban-guild", description="Unban a guild from using the bot")
    @commands.is_owner()
    async def unban_guild(
        self,
        ctx: discord.ApplicationContext,
        guild_id: str = discord.Option(str, description="Guild ID to unban"),  # type: ignore[assignment]
    ) -> None:
        await ctx.defer(ephemeral=True)

        gid = _parse_id(guild_id)
        if gid is None:
            await self.send_error(ctx, "Invalid guild ID.")
            return

        try:
            await self.services.management.unban_guild(gid)
        except GuildBanNotFoundError:
            await self.send_error(ctx, "Guild not found in ban list.")
            return

        await self.send_success(ctx, f"Guild **{gid}** unbanned.", ephemeral=True)

    @discord.slash_command(name="list-guild-bans", description="List all banned guilds")
    @commands.is_owner()
    async def list_guild_bans(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        await ctx.defer(ephemeral=True)
        await self._send_ban_list(ctx, await self.services.management.list_guild_bans(), "guild")


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(ManagementCog(bot))
