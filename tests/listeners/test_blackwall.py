# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

"""Blackwall honeypot listener: gating, punishments, cooldown, audit logging."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.listeners import blackwall as blackwall_module
from songbird.models.management.audit_log import AuditLogAction
from songbird.models.management.blackwall import BlackwallPunishment
from songbird.ui.views.blackwall.log import BlackwallLogView
from tests.support.discord import make_channel, make_guild, make_member, make_message

pytestmark = pytest.mark.discord

Listener = Callable[..., Awaitable[None]]


@asynccontextmanager
async def _session(_services: object) -> AsyncGenerator[object]:
    yield object()


def _listener(bot: SongbirdBot) -> Listener:
    return cast(Listener, vars(bot)["listeners"][0])


def _blackwall(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "guild_id": 1,
        "channel_id": 2,
        "log_channel_id": None,
        "whitelisted_roles": [],
        "punishment": BlackwallPunishment.BAN,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install(
    monkeypatch: pytest.MonkeyPatch, bot: SongbirdBot, blackwall: SimpleNamespace
) -> tuple[SimpleNamespace, SimpleNamespace]:
    service = SimpleNamespace(
        get_blackwall=AsyncMock(return_value=blackwall),
        increment_blackwall=AsyncMock(),
    )
    audit = SimpleNamespace(log=AsyncMock())
    monkeypatch.setattr(bot.services, "blackwall", service)
    monkeypatch.setattr(blackwall_module, "get_session", _session)
    monkeypatch.setattr(blackwall_module, "create_audit_log_service", lambda *_, **__: audit)
    return service, audit


def _response(status: int, reason: str) -> Any:
    return SimpleNamespace(status=status, reason=reason)


def _forbidden() -> discord.Forbidden:
    return discord.Forbidden(_response(403, "Forbidden"), "missing permissions")


def _http_error() -> discord.HTTPException:
    return discord.HTTPException(_response(500, "Server Error"), "boom")


def _member(*, ban: AsyncMock | None = None, kick: AsyncMock | None = None, send: AsyncMock | None = None) -> Any:
    member: Any = make_member(
        id=9,
        bot=False,
        guild_permissions=SimpleNamespace(administrator=False),
        roles=[],
        ban=ban or AsyncMock(),
        kick=kick or AsyncMock(),
        send=send or AsyncMock(),
    )
    member.name = "spammer"
    member.display_name = "Spammer"
    member.mention = "<@9>"
    member.created_at = datetime.now(UTC)
    member.joined_at = None
    member.display_avatar = SimpleNamespace(url="https://example.com/avatar.png")
    return member


def _trigger_message(member: discord.Member, *, delete: AsyncMock | None = None) -> Any:
    channel = make_channel(id=2)
    guild = make_guild(id=1)
    guild.name = "Test Guild"
    return make_message(
        content="honeypot bait",
        author=member,
        guild=guild,
        channel=channel,
        attachments=[],
        delete=delete or AsyncMock(),
    )


async def test_bot_message_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    member.bot = True
    service, _ = _install(monkeypatch, fake_bot, _blackwall())
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    service.get_blackwall.assert_not_awaited()
    member.ban.assert_not_awaited()


async def test_non_member_author_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = _install(monkeypatch, fake_bot, _blackwall())
    user = MagicMock(spec=discord.User, bot=False)
    message = _trigger_message(cast(discord.Member, user))
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    service.get_blackwall.assert_not_awaited()


async def test_message_outside_guild_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = _install(monkeypatch, fake_bot, _blackwall())
    message = _trigger_message(_member())
    message.guild = None
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    service.get_blackwall.assert_not_awaited()


async def test_missing_blackwall_service_is_ignored(fake_bot: SongbirdBot) -> None:
    message = _trigger_message(_member())
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    message.author.ban.assert_not_awaited()


async def test_unconfigured_guild_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    service, _ = _install(monkeypatch, fake_bot, _blackwall())
    service.get_blackwall.return_value = None
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    member.ban.assert_not_awaited()


async def test_other_channel_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    _install(monkeypatch, fake_bot, _blackwall(channel_id=99))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    member.ban.assert_not_awaited()


async def test_administrator_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    member.guild_permissions = SimpleNamespace(administrator=True)
    _install(monkeypatch, fake_bot, _blackwall())
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    member.ban.assert_not_awaited()


async def test_whitelisted_role_is_ignored(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    member.roles = [SimpleNamespace(id=42)]
    _install(monkeypatch, fake_bot, _blackwall(whitelisted_roles=[42]))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    member.ban.assert_not_awaited()


async def test_ban_punishes_increments_and_audits(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    ban = AsyncMock()
    member = _member(ban=ban)
    service, audit = _install(monkeypatch, fake_bot, _blackwall(punishment=BlackwallPunishment.BAN))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    ban.assert_awaited_once()
    assert ban.await_args is not None
    assert ban.await_args.kwargs["delete_message_seconds"] == 86400
    service.increment_blackwall.assert_awaited_once_with(1)
    audit.log.assert_awaited_once()
    assert audit.log.await_args is not None
    assert audit.log.await_args.kwargs["action"] is AuditLogAction.BLACKWALL_BAN
    assert audit.log.await_args.kwargs["target_id"] == 9
    assert audit.log.await_args.kwargs["guild_id"] == 1
    assert audit.log.await_args.kwargs["channel_id"] == 2
    assert audit.log.await_args.kwargs["metadata"] == {"punishment": "ban"}
    message.delete.assert_awaited_once()


async def test_kick_punishes_member(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    kick = AsyncMock()
    member = _member(kick=kick)
    service, audit = _install(monkeypatch, fake_bot, _blackwall(punishment=BlackwallPunishment.KICK))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    kick.assert_awaited_once()
    service.increment_blackwall.assert_awaited_once_with(1)
    audit.log.assert_awaited_once()


async def test_kick_forbidden_does_not_count_as_punished(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    kick = AsyncMock(side_effect=_forbidden())
    member = _member(kick=kick)
    service, audit = _install(monkeypatch, fake_bot, _blackwall(punishment=BlackwallPunishment.KICK))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    kick.assert_awaited_once()
    service.increment_blackwall.assert_not_awaited()
    audit.log.assert_not_awaited()
    message.delete.assert_awaited_once()


async def test_warn_dms_once_then_respects_cooldown(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    send = AsyncMock()
    member = _member(send=send)
    service, _ = _install(monkeypatch, fake_bot, _blackwall(punishment=BlackwallPunishment.WARN))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)
    await _listener(fake_bot)(message)

    send.assert_awaited_once()
    assert send.await_args is not None
    assert "Warning from Test Guild" in send.await_args.args[0]
    assert "unauthorised bots" in send.await_args.args[0]
    assert (1, 9) in blackwall_module._warn_cooldown
    assert service.increment_blackwall.await_count == 2


async def test_log_punishment_only_deletes_message(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    service, audit = _install(monkeypatch, fake_bot, _blackwall(punishment=BlackwallPunishment.LOG))
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    member.ban.assert_not_awaited()
    member.kick.assert_not_awaited()
    member.send.assert_not_awaited()
    service.increment_blackwall.assert_not_awaited()
    audit.log.assert_not_awaited()
    message.delete.assert_awaited_once()


async def test_log_channel_gets_blackwall_view(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    log_send = AsyncMock()
    log_channel = make_channel(id=5, send=log_send)
    _install(monkeypatch, fake_bot, _blackwall(log_channel_id=5))
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: log_channel)
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    log_send.assert_awaited_once()
    assert log_send.await_args is not None
    assert isinstance(log_send.await_args.kwargs["view"], BlackwallLogView)
    assert isinstance(log_send.await_args.kwargs["allowed_mentions"], discord.AllowedMentions)


async def test_log_channel_http_error_is_suppressed(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    member = _member()
    log_channel = make_channel(id=5, send=AsyncMock(side_effect=_http_error()))
    _install(monkeypatch, fake_bot, _blackwall(log_channel_id=5))
    monkeypatch.setattr(fake_bot, "get_channel", lambda _channel_id: log_channel)
    message = _trigger_message(member)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    member.ban.assert_awaited_once()


async def test_message_delete_http_error_is_suppressed(fake_bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    delete = AsyncMock(side_effect=_http_error())
    member = _member()
    _install(monkeypatch, fake_bot, _blackwall(punishment=BlackwallPunishment.BAN))
    message = _trigger_message(member, delete=delete)
    blackwall_module.load_blackwall_listener(fake_bot)

    await _listener(fake_bot)(message)

    delete.assert_awaited_once()
    member.ban.assert_awaited_once()


async def test_warn_forbidden_returns_true_without_setting_cooldown() -> None:
    send = AsyncMock(side_effect=_forbidden())
    author = _member(send=send)
    guild = make_guild(id=1)
    guild.name = "Test Guild"

    assert await blackwall_module._apply_punishment(author, guild, BlackwallPunishment.WARN) is True
    assert (1, 9) not in blackwall_module._warn_cooldown


async def test_warn_http_error_returns_true() -> None:
    send = AsyncMock(side_effect=_http_error())
    author = _member(send=send)
    guild = make_guild(id=1)

    assert await blackwall_module._apply_punishment(author, guild, BlackwallPunishment.WARN) is True


async def test_kick_http_error_returns_false() -> None:
    kick = AsyncMock(side_effect=_http_error())
    author = _member(kick=kick)
    guild = make_guild(id=1)

    assert await blackwall_module._apply_punishment(author, guild, BlackwallPunishment.KICK) is False


async def test_ban_forbidden_returns_false() -> None:
    ban = AsyncMock(side_effect=_forbidden())
    author = _member(ban=ban)
    guild = make_guild(id=1)

    assert await blackwall_module._apply_punishment(author, guild, BlackwallPunishment.BAN) is False


async def test_ban_http_error_returns_false() -> None:
    ban = AsyncMock(side_effect=_http_error())
    author = _member(ban=ban)
    guild = make_guild(id=1)

    assert await blackwall_module._apply_punishment(author, guild, BlackwallPunishment.BAN) is False
