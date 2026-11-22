# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

"""SongbirdBot construction, startup, shutdown and helper methods."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.config import Settings
from songbird.services.container import ServiceContainer

pytestmark = pytest.mark.discord

EXTENSIONS = ["songbird.cogs.llm_cog", "songbird.cogs.tools_cog"]


def _class_property(value: Any) -> property:
    return property(lambda _self: value)


def test_constructor_sets_intents_and_owner(bot: SongbirdBot, settings: Settings) -> None:
    assert bot.owner_id == settings.bot.owner_id  # pyright: ignore[reportUnknownMemberType]
    assert bot.intents.members is True
    assert bot.intents.messages is True
    assert bot.intents.message_content is True
    assert bot.intents.guilds is True
    assert bot.intents.presences is False
    assert bot.intents.reactions is False
    assert discord.IntegrationType.user_install in bot.default_command_integration_types  # pyright: ignore[reportUnknownMemberType]


def test_constructor_passes_debug_guild(settings: Settings) -> None:
    debug_settings = settings.model_copy(update={"bot": settings.bot.model_copy(update={"debug_guild_id": 42})})

    bot = SongbirdBot(debug_settings, cast(ServiceContainer, SimpleNamespace()))

    assert bot.debug_guilds == [42]  # pyright: ignore[reportUnknownMemberType]


def test_constructor_without_debug_guild(bot: SongbirdBot) -> None:
    assert bot.debug_guilds is None  # pyright: ignore[reportUnknownMemberType]


def test_constructor_stores_settings_and_services(bot: SongbirdBot, settings: Settings) -> None:
    assert bot.settings is settings
    assert bot.services is not None


async def test_on_ready_sets_presence_and_leaves_banned_guild(
    bot: SongbirdBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    banned_guild = SimpleNamespace(id=2, name="banned", leave=AsyncMock())
    allowed_guild = SimpleNamespace(id=1, name="allowed", leave=AsyncMock())
    monkeypatch.setattr(SongbirdBot, "user", _class_property(SimpleNamespace(name="Songbird")))
    monkeypatch.setattr(SongbirdBot, "guilds", _class_property([allowed_guild, banned_guild]))
    monkeypatch.setattr(bot, "application_info", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(bot, "change_presence", AsyncMock())
    monkeypatch.setattr(bot.services, "management", SimpleNamespace(get_banned_guild_ids=AsyncMock(return_value=[2])))

    await bot.on_ready()

    presence = bot.change_presence.await_args.kwargs  # type: ignore[attr-defined]
    assert presence["status"] is discord.Status.online
    assert presence["activity"].name == bot.settings.bot.activity  # pyright: ignore[reportUnknownMemberType]
    banned_guild.leave.assert_awaited_once()
    allowed_guild.leave.assert_not_awaited()


async def test_on_ready_survives_guild_leave_failure(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    http_error = discord.HTTPException(cast(Any, SimpleNamespace(status=500, reason="server error")), "no")
    failing_guild = SimpleNamespace(id=2, name="banned", leave=AsyncMock(side_effect=http_error))
    monkeypatch.setattr(SongbirdBot, "user", _class_property(SimpleNamespace(name="Songbird")))
    monkeypatch.setattr(SongbirdBot, "guilds", _class_property([failing_guild]))
    monkeypatch.setattr(bot, "application_info", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(bot, "change_presence", AsyncMock())
    monkeypatch.setattr(bot.services, "management", SimpleNamespace(get_banned_guild_ids=AsyncMock(return_value=[2])))

    await bot.on_ready()

    failing_guild.leave.assert_awaited_once()


async def test_on_ready_handles_missing_user(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SongbirdBot, "user", _class_property(None))
    monkeypatch.setattr(SongbirdBot, "guilds", _class_property([]))
    monkeypatch.setattr(bot, "application_info", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(bot, "change_presence", AsyncMock())
    monkeypatch.setattr(bot.services, "management", SimpleNamespace(get_banned_guild_ids=AsyncMock(return_value=[])))

    await bot.on_ready()

    bot.change_presence.assert_awaited_once()  # type: ignore[attr-defined]


async def test_is_owner(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "owner_id", 5)

    assert await bot.is_owner(cast(discord.User, SimpleNamespace(id=5))) is True
    assert await bot.is_owner(cast(discord.User, SimpleNamespace(id=6))) is False


async def test_is_owner_without_owner_id(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "owner_id", None)

    assert await bot.is_owner(cast(discord.User, SimpleNamespace(id=1))) is False


async def test_message_owner_returns_false_without_owner(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "owner_id", None)

    assert await bot.message_owner("hi") is False


async def test_message_owner_returns_false_when_user_missing(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "owner_id", 5)
    monkeypatch.setattr(bot, "fetch_user", lambda _user_id: None)

    assert await bot.message_owner("hi") is False


async def test_message_owner_sends_dm(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    send = AsyncMock()
    monkeypatch.setattr(bot, "owner_id", 5)
    monkeypatch.setattr(bot, "fetch_user", lambda _user_id: SimpleNamespace(send=send))

    assert await bot.message_owner("hi") is True
    send.assert_awaited_once_with("hi")


@pytest.mark.parametrize(
    "error",
    [
        discord.ExtensionAlreadyLoaded("x"),
        discord.ExtensionNotFound("x"),
        discord.ExtensionFailed("x", RuntimeError("boom")),
        RuntimeError("boom"),
    ],
)
async def test_load_cogs_swallows_each_failure(
    bot: SongbirdBot,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    monkeypatch.setattr("songbird.cogs.EXTENSIONS", EXTENSIONS)
    calls: list[str] = []

    def load_extension(name: str) -> None:
        calls.append(name)
        raise error

    monkeypatch.setattr(bot, "load_extension", load_extension)

    bot.load_cogs()

    assert calls == EXTENSIONS


async def test_load_cogs_loads_every_extension(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("songbird.cogs.EXTENSIONS", EXTENSIONS)
    calls: list[str] = []
    monkeypatch.setattr(bot, "load_extension", calls.append)

    bot.load_cogs()

    assert calls == EXTENSIONS


async def test_close_cleans_services_and_listeners(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[object] = []
    unloaded: list[bool] = []
    parent_closed: list[bool] = []

    async def close_container(services: object) -> None:
        closed.append(services)

    async def bot_close(_self: discord.Client) -> None:
        parent_closed.append(True)

    monkeypatch.setattr("songbird.bot.close_container", close_container)
    monkeypatch.setattr("songbird.listeners.unload_listeners", lambda: unloaded.append(True))
    monkeypatch.setattr(discord.Client, "close", bot_close)

    await bot.close()

    assert closed == [bot.services]
    assert unloaded == [True]
    assert parent_closed == [True]


async def test_close_still_closes_when_service_teardown_fails(bot: SongbirdBot, monkeypatch: pytest.MonkeyPatch) -> None:
    unloaded: list[bool] = []
    parent_closed: list[bool] = []

    async def close_container(_services: object) -> None:
        raise RuntimeError("boom")

    async def bot_close(_self: discord.Client) -> None:
        parent_closed.append(True)

    monkeypatch.setattr("songbird.bot.close_container", close_container)
    monkeypatch.setattr("songbird.listeners.unload_listeners", lambda: unloaded.append(True))
    monkeypatch.setattr(discord.Client, "close", bot_close)

    await bot.close()

    assert unloaded == [True]
    assert parent_closed == [True]
