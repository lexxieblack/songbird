"""Recording fakes for the py-cord objects Songbird touches.

The fakes duck-type the real API but are not subclasses, so the cast helpers are
the only place a caller meets a plain fake as a real py-cord type.
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.config import Settings
from songbird.utils.logging import get_logger


class FakeResponse:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def defer(self, **kwargs: Any) -> None:
        self.calls.append(("defer", kwargs))

    async def send_message(self, **kwargs: Any) -> None:
        self.calls.append(("send_message", kwargs))

    async def send_modal(self, modal: object) -> None:
        self.calls.append(("send_modal", {"modal": modal}))

    async def edit_message(self, **kwargs: Any) -> None:
        self.calls.append(("edit_message", kwargs))


class FakeFollowup:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def send(self, **kwargs: Any) -> None:
        self.calls.append(("send", kwargs))

    async def delete(self, **kwargs: Any) -> None:
        self.calls.append(("delete", kwargs))


def make_member(**overrides: Any) -> discord.Member:
    return cast(discord.Member, MagicMock(spec=discord.Member, **overrides))


def make_guild(**overrides: Any) -> discord.Guild:
    return cast(discord.Guild, MagicMock(spec=discord.Guild, **overrides))


def make_channel(**overrides: Any) -> discord.TextChannel:
    return cast(discord.TextChannel, MagicMock(spec=discord.TextChannel, **overrides))


def make_message(**overrides: Any) -> discord.Message:
    return cast(discord.Message, MagicMock(spec=discord.Message, **overrides))


class FakeCtx:
    def __init__(self) -> None:
        self.author = make_member()
        self.guild = make_guild()
        self.channel = make_channel()
        self.followup = FakeFollowup()
        self.interaction = SimpleNamespace(response=FakeResponse())
        # cogs/bot.py reaches the interaction response through ctx.response.
        self.response = self.interaction.response

        self.respond_calls: list[dict[str, Any]] = []
        self.last_embed: discord.Embed | None = None
        self.last_ephemeral: bool | None = None
        self.defer_calls: list[dict[str, Any]] = []
        self.sent_modals: list[object] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.deferred = False

    async def defer(self, **kwargs: Any) -> None:
        self.defer_calls.append(kwargs)
        self.deferred = True

    async def respond(self, *args: Any, **kwargs: Any) -> None:
        self.respond_calls.append({"args": args, **kwargs})
        self.last_embed = kwargs.get("embed")
        self.last_ephemeral = kwargs.get("ephemeral")

    async def send_modal(self, modal: object) -> None:
        self.sent_modals.append(modal)

    async def delete(self, **kwargs: Any) -> None:
        self.delete_calls.append(kwargs)


async def _not_banned(_value: object) -> bool:
    return False


class FakeBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.services = SimpleNamespace(
            management=SimpleNamespace(check_user_banned=_not_banned, check_guild_banned=_not_banned),
            llm=None,
            translation=None,
            link_fixer=None,
            wolfram=None,
            currency=None,
            blackwall=None,
        )
        self.user = SimpleNamespace(
            id=0,
            name="Songbird",
            display_name="Songbird",
            display_avatar=SimpleNamespace(url=""),
        )
        self.app_info = SimpleNamespace(bot_public=True)
        self.latency = 0.0
        self.logger = get_logger(__name__)
        self.listeners: list[Callable[..., Any]] = []
        self.cogs: list[object] = []

    def listen(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(callback: Callable[..., Any]) -> Callable[..., Any]:
            self.listeners.append(callback)
            return callback

        return decorator

    async def is_owner(self, _user: object) -> bool:
        return False

    def get_channel(self, _channel_id: int) -> None:
        return None

    def message_owner(self, _message: str) -> None:
        return None

    def add_cog(self, cog: object) -> None:
        self.cogs.append(cog)


def make_fake_bot(settings: Settings) -> SongbirdBot:
    return cast(SongbirdBot, FakeBot(settings))


def make_fake_ctx() -> discord.ApplicationContext:
    return cast(discord.ApplicationContext, FakeCtx())


@pytest.fixture
def fake_bot(settings: Settings) -> SongbirdBot:
    return make_fake_bot(settings)


@pytest.fixture
def fake_ctx() -> discord.ApplicationContext:
    return make_fake_ctx()
