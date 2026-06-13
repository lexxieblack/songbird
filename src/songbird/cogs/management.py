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

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot

logger = structlog.get_logger(__name__)


class ManagementCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

        self.logger.debug("Management commands initialized")

    @discord.slash_command(name="ban-user", description="Ban a user from using the bot")
    @commands.is_owner()
    async def ban_user(
        self,
        ctx: discord.ApplicationContext,
        user_id: str = discord.Option(str, description="User ID to ban"),  # type: ignore[assignment]
        reason: str | None = discord.Option(str, description="Reason for ban", required=False, default=None),  # type: ignore[assignment]
    ) -> None:
        try:
            uid = int(user_id)
        except ValueError:
            await self.send_error(ctx, "Invalid user ID.")
            return

        try:
            await self.services.management.ban_user(uid, reason)  # type: ignore[union-attr]
        except UserBanAlreadyExistsError:
            await self.send_error(ctx, "User already banned.")
            return

        parts = [f"User **{uid}** banned."]
        if reason:
            parts.append(f"Reason: {reason}")
        await self.send_success(ctx, " ".join(parts))

    @discord.slash_command(name="unban-user", description="Unban a user from using the bot")
    @commands.is_owner()
    async def unban_user(
        self,
        ctx: discord.ApplicationContext,
        user_id: str = discord.Option(str, description="User ID to unban"),  # type: ignore[assignment]
    ) -> None:
        try:
            uid = int(user_id)
        except ValueError:
            await self.send_error(ctx, "Invalid user ID.")
            return

        try:
            await self.services.management.unban_user(uid)  # type: ignore[union-attr]
        except UserBanNotFoundError:
            await self.send_error(ctx, "User not found in ban list.")
            return

        await self.send_success(ctx, f"User **{uid}** unbanned.")

    @discord.slash_command(name="list-user-bans", description="List all banned users")
    @commands.is_owner()
    async def list_user_bans(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        bans = await self.services.management.list_user_bans()  # type: ignore[union-attr]

        if not bans:
            await self.send_success(ctx, "No users are currently banned.")
            return

        lines: list[str] = []
        for ban in bans:
            reason = f" — {ban.reason}" if ban.reason else ""
            ts = ban.created_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"• **{ban.user_id}**{reason} (banned {ts})")

        embed = discord.Embed(
            title="Banned Users",
            description="\n".join(lines),
            colour=discord.Color.red(),
        )
        await ctx.respond(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @discord.slash_command(name="ban-guild", description="Ban a guild from using the bot")
    @commands.is_owner()
    async def ban_guild(
        self,
        ctx: discord.ApplicationContext,
        guild_id: str = discord.Option(str, description="Guild ID to ban"),  # type: ignore[assignment]
        reason: str | None = discord.Option(str, description="Reason for ban", required=False, default=None),  # type: ignore[assignment]
    ) -> None:
        try:
            gid = int(guild_id)
        except ValueError:
            await self.send_error(ctx, "Invalid guild ID.")
            return

        try:
            await self.services.management.ban_guild(gid, reason)  # type: ignore[union-attr]
        except GuildBanAlreadyExistsError:
            await self.send_error(ctx, "Guild already banned.")
            return

        parts = [f"Guild **{gid}** banned."]
        if reason:
            parts.append(f"Reason: {reason}")
        await self.send_success(ctx, " ".join(parts))

    @discord.slash_command(name="unban-guild", description="Unban a guild from using the bot")
    @commands.is_owner()
    async def unban_guild(
        self,
        ctx: discord.ApplicationContext,
        guild_id: str = discord.Option(str, description="Guild ID to unban"),  # type: ignore[assignment]
    ) -> None:
        try:
            gid = int(guild_id)
        except ValueError:
            await self.send_error(ctx, "Invalid guild ID.")
            return

        try:
            await self.services.management.unban_guild(gid)  # type: ignore[union-attr]
        except GuildBanNotFoundError:
            await self.send_error(ctx, "Guild not found in ban list.")
            return

        await self.send_success(ctx, f"Guild **{gid}** unbanned.")

    @discord.slash_command(name="list-guild-bans", description="List all banned guilds")
    @commands.is_owner()
    async def list_guild_bans(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        bans = await self.services.management.list_guild_bans()  # type: ignore[union-attr]

        if not bans:
            await self.send_success(ctx, "No guilds are currently banned.")
            return

        lines: list[str] = []
        for ban in bans:
            reason = f" — {ban.reason}" if ban.reason else ""
            ts = ban.created_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"• **{ban.guild_id}**{reason} (banned {ts})")

        embed = discord.Embed(
            title="Banned Guilds",
            description="\n".join(lines),
            colour=discord.Color.red(),
        )
        await ctx.respond(embed=embed, allowed_mentions=discord.AllowedMentions.none())


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(ManagementCog(bot))
