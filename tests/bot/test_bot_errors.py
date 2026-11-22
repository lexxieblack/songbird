"""on_application_command_error maps py-cord failures to ephemeral messages."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import discord
import pytest
from discord.ext import commands

from songbird.bot import SongbirdBot

pytestmark = pytest.mark.discord


class _Ctx:
    def __init__(self) -> None:
        self.command: Any = SimpleNamespace(name="chat")
        self.author: Any = SimpleNamespace(id=9)
        self.guild: Any = SimpleNamespace(id=3)
        self.responses: list[dict[str, Any]] = []

    async def respond(self, *args: Any, **kwargs: Any) -> None:
        self.responses.append({"args": args, **kwargs})


def _context() -> tuple[discord.ApplicationContext, _Ctx]:
    ctx = _Ctx()
    return cast(discord.ApplicationContext, ctx), ctx


def _assert_ephemeral(ctx: _Ctx, message: str) -> None:
    assert len(ctx.responses) == 1
    assert ctx.responses[0]["args"] == (message,)
    assert ctx.responses[0]["ephemeral"] is True


async def test_cooldown_is_rounded(bot: SongbirdBot) -> None:
    ctx, fake = _context()
    error = commands.CommandOnCooldown(MagicMock(), 5.26, MagicMock())

    await bot.on_application_command_error(ctx, error)

    _assert_ephemeral(fake, "This command is on cooldown. Please try again in 5.3 seconds.")


async def test_missing_permissions_lists_permissions(bot: SongbirdBot) -> None:
    ctx, fake = _context()

    await bot.on_application_command_error(ctx, commands.MissingPermissions(["ban_members", "kick_members"]))

    _assert_ephemeral(fake, "You don't have permission to use this command. Missing: ban_members, kick_members")


async def test_bot_missing_permissions_lists_permissions(bot: SongbirdBot) -> None:
    ctx, fake = _context()

    await bot.on_application_command_error(ctx, commands.BotMissingPermissions(["send_messages"]))

    _assert_ephemeral(fake, "I don't have the required permissions. Missing: send_messages")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (commands.NotOwner(), "This command is only available to the bot owner."),
        (commands.NoPrivateMessage(), "This command cannot be used in direct messages."),
        (commands.PrivateMessageOnly(), "This command can only be used in direct messages."),
    ],
)
async def test_simple_failures(bot: SongbirdBot, error: commands.CommandError, message: str) -> None:
    ctx, fake = _context()

    await bot.on_application_command_error(ctx, error)

    _assert_ephemeral(fake, message)


async def test_forbidden(bot: SongbirdBot) -> None:
    ctx, fake = _context()
    error = discord.Forbidden(MagicMock(), "missing access")

    await bot.on_application_command_error(ctx, error)

    _assert_ephemeral(fake, "The bot doesn't have permission to run this command.")


async def test_generic_error(bot: SongbirdBot) -> None:
    ctx, fake = _context()

    await bot.on_application_command_error(ctx, discord.DiscordException("boom"))

    _assert_ephemeral(fake, "An error occurred while processing your command. Please try again later.")


async def test_wrapped_original_error_is_unwrapped(bot: SongbirdBot) -> None:
    ctx, fake = _context()
    wrapped = commands.CommandInvokeError(commands.NotOwner())

    await bot.on_application_command_error(ctx, wrapped)

    _assert_ephemeral(fake, "This command is only available to the bot owner.")


async def test_missing_command_name_and_guild_do_not_crash(bot: SongbirdBot) -> None:
    _, fake = _context()
    fake.command = None
    fake.guild = None

    await bot.on_application_command_error(cast(discord.ApplicationContext, fake), discord.DiscordException("boom"))

    _assert_ephemeral(fake, "An error occurred while processing your command. Please try again later.")
