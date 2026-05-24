from typing import TYPE_CHECKING

import discord
import structlog
from discord.ext import commands

from songbird.services.container import ServiceContainer, close_container

if TYPE_CHECKING:
    from songbird.config import Settings


logger = structlog.get_logger(__name__)


class SongbirdBot(discord.Bot):
    def __init__(self, settings: "Settings", services: ServiceContainer) -> None:
        # Configure intents
        intents = discord.Intents.none()
        intents.members = True
        intents.messages = True
        intents.typing = True
        intents.message_content = True
        intents.guilds = True

        # Initialise parent class with intents
        debug_guilds = [settings.bot.debug_guild_id] if settings.bot.debug_guild_id else None
        super().__init__(
            intents=intents,
            owner_id=settings.bot.owner_id,
            debug_guilds=debug_guilds,
            default_command_integration_types=[discord.IntegrationType.user_install],
        )

        # Store settings and services
        self.settings = settings
        self.services = services

        # Initialise logger
        self.logger = logger.bind(component="bot")

        self.logger.info("Bot initialized", owner_id=settings.bot.owner_id)

    async def on_ready(self) -> None:
        bot_name = self.user.name if self.user else "Unknown"
        guild_count = len(self.guilds)

        self.app_info = await self.application_info()

        activity = self.settings.bot.activity
        activity = discord.CustomActivity(name=activity)
        await self.change_presence(status=discord.Status[self.settings.bot.status], activity=activity)
        self.logger.debug("Bot presence set", activity=activity)

        self.logger.info("Bot ready", bot_name=bot_name, guild_count=guild_count)

    async def on_application_command_error(
        self,
        context: discord.ApplicationContext,
        exception: discord.DiscordException,
    ) -> None:
        # Get the original error if wrapped
        original_error = getattr(exception, "original", exception)

        # Log the error with context
        self.logger.error(
            "command_error",
            command=context.command.name if context.command else "unknown",
            user_id=context.author.id,
            guild_id=context.guild.id if context.guild else None,
            error=str(original_error),
            error_type=type(original_error).__name__,
        )

        # Handle specific error types
        if isinstance(original_error, commands.CommandOnCooldown):
            retry_after = round(original_error.retry_after, 1)
            await context.respond(f"This command is on cooldown. Please try again in {retry_after} seconds.", ephemeral=True)
            return

        if isinstance(original_error, commands.MissingPermissions):
            missing = ", ".join(original_error.missing_permissions)
            await context.respond(f"You don't have permission to use this command. Missing: {missing}", ephemeral=True)
            return

        if isinstance(original_error, commands.BotMissingPermissions):
            missing = ", ".join(original_error.missing_permissions)
            await context.respond(f"I don't have the required permissions. Missing: {missing}", ephemeral=True)
            return

        if isinstance(original_error, commands.NotOwner):
            await context.respond("This command is only available to the bot owner.", ephemeral=True)
            return

        if isinstance(original_error, commands.NoPrivateMessage):
            await context.respond("This command cannot be used in direct messages.", ephemeral=True)
            return

        if isinstance(original_error, commands.PrivateMessageOnly):
            await context.respond("This command can only be used in direct messages.", ephemeral=True)
            return

        if isinstance(original_error, discord.Forbidden):
            # if "Missing Access" in str(original_error) and "403 Forbidden" in str(original_error):
            await context.respond("The bot doesn't have permission to run this command.", ephemeral=True)
            return

        # Generic error response for unhandled errors
        await context.respond("An error occurred while processing your command. Please try again later.", ephemeral=True)

    def load_cogs(self) -> None:
        # Import the default extensions list
        from songbird.cogs import EXTENSIONS

        self.logger.info("Loading cogs", extension_count=len(EXTENSIONS))

        for extension in EXTENSIONS:
            try:
                self.load_extension(extension)
                self.logger.info("Cog loaded", extension=extension)
            except discord.ExtensionAlreadyLoaded:
                self.logger.warning("Cog already loaded", extension=extension)
            except discord.ExtensionNotFound:
                self.logger.error("Cog not found", extension=extension)
            except discord.ExtensionFailed as exc:
                self.logger.exception(
                    "Cogs load failed",
                    extension=extension,
                    error=str(exc),
                )
            except Exception as exc:
                self.logger.exception(
                    "Cogs load unexpected error",
                    extension=extension,
                    error=str(exc),
                )

        self.logger.info("Cogs loading complete")

    def is_owner(self, user_id: int) -> bool:  # type: ignore
        return self.owner_id is not None and user_id == self.owner_id

    async def message_owner(self, message: str) -> bool:
        if self.owner_id is None:
            self.logger.warning("Owner ID not set")
            return False
        owner = self.fetch_user(self.owner_id)
        if owner is None:
            self.logger.warning("Owner not found")
            return False
        await owner.send(message)
        return True

    async def close(self) -> None:
        self.logger.info("Bot closing")

        # Clean up services
        try:
            await close_container(self.services)
            self.logger.debug("Services closed")
        except Exception as e:
            self.logger.warning("Services close error", error=str(e))

        # Clean up listeners
        from songbird.listeners import unload_listeners

        unload_listeners()

        # Call parent close
        await super().close()

        self.logger.info("Bot closed")
