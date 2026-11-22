"""Guild-join ban enforcement listener."""

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.listeners import management
from tests.support.discord import make_guild, make_member

pytestmark = pytest.mark.discord

Listener = Callable[..., Awaitable[None]]


def _listener(bot: SongbirdBot) -> Listener:
    return cast(Listener, vars(bot)["listeners"][0])


def _install(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch, *, banned: bool) -> tuple[Any, AsyncMock]:
    monkeypatch.setattr(bot.services, "management", SimpleNamespace(check_guild_banned=AsyncMock(return_value=banned)))
    owner_message = AsyncMock()
    monkeypatch.setattr(bot, "message_owner", owner_message)
    management.load_guild_ban_listener(bot)
    return bot.services.management, owner_message


def _response(status: int, reason: str) -> Any:
    return SimpleNamespace(status=status, reason=reason)


def _guild(*, owner: discord.Member | None = None, member_count: int | None = 3, leave: AsyncMock | None = None) -> Any:
    guild = make_guild(id=1, owner=owner, member_count=member_count, leave=leave or AsyncMock())
    guild.name = "Spam Guild"
    return guild


async def test_allowed_guild_is_not_left(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    service, owner_message = _install(fake_bot, monkeypatch, banned=False)
    guild = _guild()

    await _listener(fake_bot)(guild)

    service.check_guild_banned.assert_awaited_once_with(1)
    owner_message.assert_not_awaited()
    guild.leave.assert_not_awaited()


async def test_banned_guild_is_reported_and_left(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    _, owner_message = _install(fake_bot, monkeypatch, banned=True)
    owner = make_member()
    guild = _guild(owner=owner)

    await _listener(fake_bot)(guild)

    owner_message.assert_awaited_once()
    assert owner_message.await_args is not None
    text = owner_message.await_args.args[0]
    assert "Left banned guild **Spam Guild** (ID: 1)" in text
    assert str(owner) in text
    assert "Members: 3" in text
    guild.leave.assert_awaited_once()


async def test_banned_guild_without_owner_or_member_count(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    _, owner_message = _install(fake_bot, monkeypatch, banned=True)
    guild = _guild(owner=None, member_count=None)

    await _listener(fake_bot)(guild)

    assert owner_message.await_args is not None
    text = owner_message.await_args.args[0]
    assert "Owner: Unknown" in text
    assert "Members: 0" in text


@pytest.mark.parametrize(
    "error",
    [
        discord.HTTPException(_response(500, "Server Error"), "boom"),
        discord.Forbidden(_response(403, "Forbidden"), "missing"),
    ],
)
async def test_leave_failures_are_suppressed(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    _, owner_message = _install(fake_bot, monkeypatch, banned=True)
    guild = _guild(leave=AsyncMock(side_effect=error))

    await _listener(fake_bot)(guild)

    owner_message.assert_awaited_once()
    guild.leave.assert_awaited_once()
