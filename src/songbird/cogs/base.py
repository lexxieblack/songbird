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
        self.logger = logger.bind(cog=self.__class__.__name__)  # pyright: ignore[reportUnknownMemberType]

        self.logger.debug("Cog initialized")

    @property
    def services(self) -> "ServiceContainer":
        return self.bot.services

    @property
    def settings(self) -> "Settings":
        return self.bot.settings

    async def _send_embed(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        message: str,
        colour: discord.Colour,
        ephemeral: bool,
    ) -> None:
        embed = discord.Embed(title=title, description=message, colour=colour)

        try:
            await ctx.respond(embed=embed, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            # If respond fails (e.g., already responded), try followup
            try:
                await ctx.followup.send(embed=embed, ephemeral=ephemeral, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                # If that fails too, log it but don't crash
                self.logger.warning("Failed to send message", title=title, error_message=message)

    async def send_error(
        self,
        ctx: discord.ApplicationContext,
        message: str,
        ephemeral: bool = True,
    ) -> None:
        await self._send_embed(ctx, "Error", message, discord.Color.red(), ephemeral)

    async def send_success(
        self,
        ctx: discord.ApplicationContext,
        message: str,
        ephemeral: bool = False,
    ) -> None:
        await self._send_embed(ctx, "Success", message, discord.Colour.green(), ephemeral)

    async def is_owner(self, ctx: discord.ApplicationContext) -> bool:
        return await self.bot.is_owner(ctx.author)

    async def cog_before_invoke(self, ctx: discord.ApplicationContext) -> None:
        """Runs before every application command in every cog, including message commands."""
        if await self.is_owner(ctx):
            return
        if await self.services.management.check_user_banned(ctx.author.id):
            self.logger.info("Blocked banned user", user_id=ctx.author.id, username=ctx.author.name)
            raise commands.CheckFailure("User is banned")

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        self.logger.info("Cog loaded", cog_name=self.__class__.__name__)  # pyright: ignore[reportUnknownMemberType]

    def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        self.logger.info("Cog unloading", cog_name=self.__class__.__name__)  # pyright: ignore[reportUnknownMemberType]
