"""Entry point for running Songbird via `uv run -m songbird`."""

import asyncio
import sys

from songbird.listeners import load_listeners


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()

    from songbird.config import load_config
    from songbird.utils.logging import setup_logging

    # Load configuration (will validate environment variables)
    try:
        settings = load_config()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup structured logging
    logger = setup_logging(settings.log_level)
    logger.info(
        "Songbird starting",
        version="3.0.0",
        log_level=settings.log_level,
    )

    # Run the async startup
    try:
        asyncio.run(async_main(settings, logger))
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.exception("Fatal error", error=str(e))
        sys.exit(1)


async def async_main(settings: "Settings", logger: "BoundLogger") -> None:
    from songbird.bot import SongbirdBot
    from songbird.services.container import create_container

    # Create service container with all dependencies
    logger.info("Creating service container")
    container = await create_container(settings)

    # Create bot instance
    logger.info("Creating bot instance", owner_id=settings.bot.owner_id)
    bot = SongbirdBot(settings, container)

    # Load all cogs
    bot.load_cogs()

    # Load listeners
    load_listeners(bot)
    logger.info("Listeners loaded")

    # Start the bot
    try:
        logger.info("Connecting to Discord")
        await bot.start(settings.discord_token)
    finally:
        # Ensure cleanup on shutdown
        logger.info("Shutting down")
        if not bot.is_closed():
            await bot.close()


# Type hints for function signatures
if __name__ == "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from structlog import BoundLogger

        from songbird.config import Settings

    main()
