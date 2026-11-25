"""Management cog: ban CRUD messaging, owner gating and management-guild scoping."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest
from discord.ext import commands

from songbird.bot import SongbirdBot
from songbird.cogs.management import ManagementCog
from songbird.models.management.exceptions import (
    GuildBanAlreadyExistsError,
    GuildBanNotFoundError,
    UserBanAlreadyExistsError,
    UserBanNotFoundError,
)
from songbird.models.management.guild_ban import GuildBan
from songbird.models.management.user_ban import UserBan
from tests.cogs._support import invoke
from tests.support.discord import FakeCtx

pytestmark = pytest.mark.discord

COMMANDS = ["ban_user", "unban_user", "list_user_bans", "ban_guild", "unban_guild", "list_guild_bans"]


def _fake(ctx: discord.ApplicationContext) -> FakeCtx:
    return cast(FakeCtx, ctx)


def _management(**overrides: Any) -> Any:
    methods: dict[str, Any] = {
        "check_user_banned": AsyncMock(return_value=False),
        "check_guild_banned": AsyncMock(return_value=False),
        "ban_user": AsyncMock(),
        "unban_user": AsyncMock(),
        "list_user_bans": AsyncMock(return_value=[]),
        "ban_guild": AsyncMock(),
        "unban_guild": AsyncMock(),
        "list_guild_bans": AsyncMock(return_value=[]),
    }
    methods.update(overrides)
    return SimpleNamespace(**methods)


def _install(bot: SongbirdBot, service: Any) -> None:
    cast(Any, bot.services).management = service


@pytest.fixture
def cog(fake_bot: SongbirdBot) -> ManagementCog:
    return ManagementCog(fake_bot)


async def test_ban_user_rejects_invalid_id(cog: ManagementCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "ban_user", fake_ctx, user_id="not-a-number")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Invalid user ID."
    assert ctx.last_ephemeral is True


async def test_ban_user_reports_success_with_reason(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management()
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "ban_user", fake_ctx, user_id="123", reason="spam")

    service.ban_user.assert_awaited_once_with(123, "spam")
    assert ctx.defer_calls == [{"ephemeral": True}]
    assert ctx.last_embed is not None
    assert ctx.last_embed.title == "Success"
    assert ctx.last_embed.description == "User **123** banned. Reason: spam"
    assert ctx.last_ephemeral is True


async def test_ban_user_reports_duplicate(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management(ban_user=AsyncMock(side_effect=UserBanAlreadyExistsError()))
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "ban_user", fake_ctx, user_id="123")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "User already banned."


async def test_unban_user_reports_missing(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management(unban_user=AsyncMock(side_effect=UserBanNotFoundError()))
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "unban_user", fake_ctx, user_id="123")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "User not found in ban list."


async def test_unban_user_reports_success(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management()
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "unban_user", fake_ctx, user_id="123")

    service.unban_user.assert_awaited_once_with(123)
    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "User **123** unbanned."


async def test_list_user_bans_empty(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    _install(fake_bot, _management())
    ctx = _fake(fake_ctx)

    await invoke(cog, "list_user_bans", fake_ctx)

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "No users are currently banned."


async def test_list_user_bans_builds_embed(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    ban = UserBan(user_id=123, reason="spam", created_at=datetime(2024, 1, 2, 3, 4, tzinfo=UTC))
    _install(fake_bot, _management(list_user_bans=AsyncMock(return_value=[ban])))
    ctx = _fake(fake_ctx)

    await invoke(cog, "list_user_bans", fake_ctx)

    embed = ctx.followup.calls[0][1]["embed"]
    assert embed.title == "Banned Users"
    assert embed.description == "• **123** — spam (banned 2024-01-02 03:04 UTC)"
    assert ctx.followup.calls[0][1]["ephemeral"] is True


async def test_list_user_bans_caps_long_lists(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    bans = [UserBan(user_id=i, reason=None, created_at=datetime(2024, 1, 2, 3, 4, tzinfo=UTC)) for i in range(35)]
    _install(fake_bot, _management(list_user_bans=AsyncMock(return_value=bans)))
    ctx = _fake(fake_ctx)

    await invoke(cog, "list_user_bans", fake_ctx)

    description = ctx.followup.calls[0][1]["embed"].description
    assert description.count("•") == 30
    assert description.endswith("... and 5 more")


async def test_ban_guild_rejects_invalid_id(cog: ManagementCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "ban_guild", fake_ctx, guild_id="nope")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Invalid guild ID."


async def test_ban_guild_reports_duplicate(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management(ban_guild=AsyncMock(side_effect=GuildBanAlreadyExistsError()))
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "ban_guild", fake_ctx, guild_id="456")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Guild already banned."


async def test_unban_guild_reports_missing(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management(unban_guild=AsyncMock(side_effect=GuildBanNotFoundError()))
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "unban_guild", fake_ctx, guild_id="456")

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Guild not found in ban list."


async def test_unban_guild_reports_success(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _management()
    _install(fake_bot, service)
    ctx = _fake(fake_ctx)

    await invoke(cog, "unban_guild", fake_ctx, guild_id="456")

    service.unban_guild.assert_awaited_once_with(456)
    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Guild **456** unbanned."


async def test_list_guild_bans_builds_embed(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    ban = GuildBan(guild_id=456, reason=None, created_at=datetime(2024, 5, 6, 7, 8, tzinfo=UTC))
    _install(fake_bot, _management(list_guild_bans=AsyncMock(return_value=[ban])))
    ctx = _fake(fake_ctx)

    await invoke(cog, "list_guild_bans", fake_ctx)

    embed = ctx.followup.calls[0][1]["embed"]
    assert embed.title == "Banned Guilds"
    assert embed.description == "• **456** (banned 2024-05-06 07:08 UTC)"


async def test_all_management_commands_require_owner(
    cog: ManagementCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    setattr(fake_ctx, "bot", fake_bot)  # noqa: B010 - ApplicationContext.bot is read-only

    for name in COMMANDS:
        command = getattr(cog, name)
        assert command.name == name.replace("_", "-")
        assert len(command.checks) == 1
        with pytest.raises(commands.NotOwner):
            await command.checks[0](fake_ctx)


def test_commands_are_scoped_to_management_guild(fake_bot: SongbirdBot) -> None:
    fake_bot.settings.bot.management_guild_id = 999

    cog = ManagementCog(fake_bot)

    assert [command.guild_ids for command in cog.get_commands()] == [[999]] * len(COMMANDS)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType, reportUnknownMemberType]
