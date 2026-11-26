# pyright: reportPrivateUsage=false

"""Blackwall cog: permission gate, service guards and config view rendering."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.cogs.blackwall import BlackwallCog
from songbird.models.management.blackwall import Blackwall, BlackwallPunishment
from songbird.ui.views.blackwall.__main__ import BlackwallView
from tests.cogs._support import invoke
from tests.support.discord import FakeCtx, make_channel, make_guild, make_member

pytestmark = pytest.mark.discord


def _fake(ctx: discord.ApplicationContext) -> FakeCtx:
    return cast(FakeCtx, ctx)


def _services(bot: SongbirdBot) -> Any:
    return cast(Any, bot.services)


def _config(**overrides: Any) -> Blackwall:
    values: dict[str, Any] = {
        "guild_id": 1,
        "channel_id": 10,
        "log_channel_id": None,
        "whitelisted_roles": [],
        "banned_count": 0,
        "punishment": BlackwallPunishment.BAN,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return Blackwall(**values)


def _service(config: Blackwall | None = None) -> Any:
    return SimpleNamespace(
        get_blackwall=AsyncMock(return_value=config),
        create_blackwall=AsyncMock(return_value=config or _config()),
        update_channel=AsyncMock(return_value=config or _config()),
        update_log_channel=AsyncMock(return_value=config or _config()),
        update_roles=AsyncMock(return_value=config or _config()),
        update_punishment=AsyncMock(return_value=config or _config()),
    )


def _admin_ctx(fake_ctx: discord.ApplicationContext) -> FakeCtx:
    ctx = _fake(fake_ctx)
    cast(Any, ctx.guild).id = 1
    cast(Any, ctx.channel).id = 10
    cast(Any, ctx.author).guild_permissions.administrator = True
    return ctx


@pytest.fixture
def cog(fake_bot: SongbirdBot) -> BlackwallCog:
    return BlackwallCog(fake_bot)


async def test_missing_service_sends_error(
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    _services(fake_bot).blackwall = None
    ctx = _admin_ctx(fake_ctx)

    await invoke(cog, "blackwall", fake_ctx)

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "The blackwall service is not available."


async def test_requires_guild_and_member(
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    _services(fake_bot).blackwall = _service()
    ctx = _admin_ctx(fake_ctx)
    setattr(ctx, "guild", None)  # noqa: B010 - fake state reset

    await invoke(cog, "blackwall", fake_ctx)

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "This command can only be used in a server."


async def test_requires_administrator(
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    _services(fake_bot).blackwall = _service()
    ctx = _admin_ctx(fake_ctx)
    ctx.author.guild_permissions.administrator = False

    await invoke(cog, "blackwall", fake_ctx)

    assert ctx.respond_calls[0]["args"] == ("You do not have permission to use this command.",)
    assert ctx.respond_calls[0]["ephemeral"] is True
    assert ctx.defer_calls == []


async def test_existing_config_renders_view(
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    config = _config()
    service = _service(config)
    _services(fake_bot).blackwall = service
    ctx = _admin_ctx(fake_ctx)

    await invoke(cog, "blackwall", fake_ctx)

    service.get_blackwall.assert_awaited_once_with(1)
    service.create_blackwall.assert_not_awaited()
    assert ctx.defer_calls == [{}]
    assert isinstance(ctx.respond_calls[0]["view"], BlackwallView)


async def test_missing_config_is_created(
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _service(None)
    _services(fake_bot).blackwall = service
    ctx = _admin_ctx(fake_ctx)

    await invoke(cog, "blackwall", fake_ctx)

    service.create_blackwall.assert_awaited_once_with(1)
    assert isinstance(ctx.respond_calls[0]["view"], BlackwallView)


async def test_remove_log_channel_clears_only_log_channel(
    monkeypatch: pytest.MonkeyPatch,
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    config = _config(log_channel_id=20)
    service = _service(config)
    _services(fake_bot).blackwall = service
    _admin_ctx(fake_ctx)

    captured: list[tuple[Any, ...]] = []

    def capture(*args: Any, **_kwargs: Any) -> object:
        captured.append(args)
        return object()

    monkeypatch.setattr("songbird.cogs.blackwall._make_view", capture)

    await invoke(cog, "blackwall", fake_ctx)

    interaction = SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    await captured[0][1].on_remove_log_channel(interaction)

    service.update_log_channel.assert_awaited_once_with(1, None)
    service.update_channel.assert_not_awaited()
    interaction.edit_original_response.assert_awaited_once()


async def test_edit_punishment_reads_current_config(
    monkeypatch: pytest.MonkeyPatch,
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    # Regression: the edit view was built from the config captured when /blackwall ran,
    # so opening it after an update showed (and re-saved) the old punishment.
    stale = _config(punishment=BlackwallPunishment.BAN)
    fresh = _config(punishment=BlackwallPunishment.WARN)
    service = _service(stale)
    service.get_blackwall = AsyncMock(side_effect=[stale, fresh])
    _services(fake_bot).blackwall = service
    _admin_ctx(fake_ctx)

    captured: list[tuple[Any, ...]] = []

    def capture(*args: Any, **_kwargs: Any) -> object:
        captured.append(args)
        return object()

    monkeypatch.setattr("songbird.cogs.blackwall._make_view", capture)

    await invoke(cog, "blackwall", fake_ctx)

    interaction = SimpleNamespace(response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()))
    await captured[0][1].on_edit_punishment(interaction)

    view = interaction.response.edit_message.await_args.kwargs["view"]
    text = cast(Any, view).children[0].items[2].content
    assert "Current: **warn**" in text


async def test_config_lookup_failure_sends_error(
    cog: BlackwallCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    service = _service()
    service.get_blackwall = AsyncMock(side_effect=RuntimeError("db down"))
    _services(fake_bot).blackwall = service
    ctx = _admin_ctx(fake_ctx)

    await invoke(cog, "blackwall", fake_ctx)

    assert ctx.last_embed is not None
    assert ctx.last_embed.description == "Failed to check blackwall status."


def test_missing_channel_permissions_rejects_non_text_channel(cog: BlackwallCog) -> None:
    guild = cast(Any, make_guild())
    guild.get_channel.return_value = SimpleNamespace()

    error = cog._missing_channel_permissions(guild, 10, ["view_channel"])

    assert error == "The configured channel <#10> is not a text channel."


def test_missing_channel_permissions_lists_missing(cog: BlackwallCog) -> None:
    channel = cast(Any, make_channel())
    channel.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=False, ban_members=True)
    guild = cast(Any, make_guild())
    guild.get_channel.return_value = channel
    guild.me = make_member()

    error = cog._missing_channel_permissions(guild, 10, ["view_channel", "send_messages", "ban_members"])

    assert error == ("The bot is missing required permissions in <#10>: Send Messages. Grant them and try again.")


def test_missing_channel_permissions_passes_when_all_granted(cog: BlackwallCog) -> None:
    channel = cast(Any, make_channel())
    channel.permissions_for.return_value = SimpleNamespace(view_channel=True, send_messages=True)
    guild = cast(Any, make_guild())
    guild.get_channel.return_value = channel
    guild.me = make_member()

    assert cog._missing_channel_permissions(guild, 10, ["view_channel", "send_messages"]) is None
