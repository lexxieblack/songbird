from contextlib import suppress
from typing import TYPE_CHECKING

import discord
import structlog
from discord.ext import commands

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot
    from songbird.config import Settings
    from songbird.services.container import ServiceContainer


logger = structlog.get_logger(__name__)


class BaseCog(commands.Cog):
    def __init__(self, bot: "SongbirdBot") -> None:
        self.bot = bot
        self.logger = logger.bind(cog=self.__class__.__name__)

        self.logger.debug("Cog initialized")

    @property
    def services(self) -> "ServiceContainer":
        return self.bot.services

    @property
    def settings(self) -> "Settings":
        return self.bot.settings

    async def send_error(
        self,
        ctx: discord.ApplicationContext,
        message: str,
        ephemeral: bool = True,
    ) -> None:
        embed = discord.Embed(
            title="Error",
            description=message,
            colour=discord.Color.red(),
        )

        try:
            await ctx.respond(embed=embed, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            # If respond fails (e.g., already responded), try followup
            try:
                await ctx.followup.send(embed=embed, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                # If that fails too, log it but don't crash
                self.logger.warning(
                    "Failed to send error message",
                    error_message=message,
                )

    async def send_success(
        self,
        ctx: discord.ApplicationContext,
        message: str,
        ephemeral: bool = False,
    ) -> None:
        embed = discord.Embed(
            title="Success",
            description=message,
            colour=discord.Colour.green(),
        )

        try:
            await ctx.respond(embed=embed, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            # If respond fails (e.g., already responded), try followup
            try:
                await ctx.followup.send(embed=embed, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                # If that fails too, log it but don't crash
                self.logger.warning(
                    "Failed to send success message",
                    success_message=message,
                )

    def is_owner(self, ctx: discord.ApplicationContext) -> bool:
        return self.bot.is_owner(ctx.author.id)

    async def _check_banned(self, ctx: discord.ApplicationContext) -> bool:
        """Check if the invoking user is banned.

        Returns True if banned (and silently acks the interaction), False otherwise.
        """
        banned = await self.services.management.check_user_banned(ctx.author.id)  # type: ignore
        if banned:
            self.logger.info("Blocked banned user", user_id=ctx.author.id)
            with suppress(discord.HTTPException):
                await ctx.respond()
            return True
        return False

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.logger.info("Cog loaded", cog_name=self.__class__.__name__)

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.logger.info("Cog unloading", cog_name=self.__class__.__name__)
