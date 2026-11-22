"""`/help`, `/about` and `/feedback` user-visible behaviour."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from songbird.bot import SongbirdBot
from songbird.cogs import bot as bot_cog_module
from songbird.cogs.bot import BotCog
from songbird.ui.modals.feedback import FeedbackModal
from songbird.ui.views.about import AboutView
from songbird.ui.views.help import HelpView
from tests.cogs._support import invoke
from tests.support.discord import FakeCtx

pytestmark = pytest.mark.discord


def _fake(ctx: discord.ApplicationContext) -> FakeCtx:
    return cast(FakeCtx, ctx)


def _services(bot: SongbirdBot) -> Any:
    return cast(Any, bot.services)


@pytest.fixture
def cog(fake_bot: SongbirdBot) -> BotCog:
    return BotCog(fake_bot)


async def test_help_responds_with_help_view(cog: BotCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "help", fake_ctx)

    assert len(ctx.respond_calls) == 1
    call = ctx.respond_calls[0]
    assert isinstance(call["view"], HelpView)
    allowed_mentions = call["allowed_mentions"]
    assert isinstance(allowed_mentions, discord.AllowedMentions)
    assert allowed_mentions.everyone is False


async def test_about_responds_with_about_view(cog: BotCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "about", fake_ctx)

    assert isinstance(ctx.respond_calls[0]["view"], AboutView)


async def test_feedback_disabled_when_no_channel(cog: BotCog, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await invoke(cog, "feedback", fake_ctx)

    assert ctx.respond_calls[0]["args"] == ("Feedback is disabled.",)
    assert ctx.respond_calls[0]["ephemeral"] is True


async def test_feedback_opens_modal(
    monkeypatch: pytest.MonkeyPatch,
    cog: BotCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    fake_bot.settings.bot.feedback_channel_id = 123
    ctx = _fake(fake_ctx)

    @asynccontextmanager
    async def session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        yield SimpleNamespace()

    monkeypatch.setattr(bot_cog_module, "get_session", session)
    monkeypatch.setattr(bot_cog_module, "create_feedback_service", lambda *_args: SimpleNamespace())  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]

    await invoke(cog, "feedback", fake_ctx)

    method, kwargs = ctx.response.calls[0]
    assert method == "send_modal"
    assert isinstance(kwargs["modal"], FeedbackModal)


async def test_feedback_reports_database_failure(
    monkeypatch: pytest.MonkeyPatch,
    cog: BotCog,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    fake_bot.settings.bot.feedback_channel_id = 123
    ctx = _fake(fake_ctx)

    @asynccontextmanager
    async def failing_session(_services: object) -> AsyncGenerator[SimpleNamespace]:
        raise RuntimeError("db down")
        yield SimpleNamespace()

    monkeypatch.setattr(bot_cog_module, "get_session", failing_session)

    await invoke(cog, "feedback", fake_ctx)

    assert ctx.respond_calls[0]["args"] == ("Feedback failed.",)
    assert ctx.respond_calls[0]["ephemeral"] is True
