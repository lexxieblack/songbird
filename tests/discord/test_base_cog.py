"""The shared `BaseCog` response path builds the expected embeds and mentions."""

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest
from tests.support.discord import FakeCtx

from songbird.bot import SongbirdBot
from songbird.cogs.base import BaseCog

pytestmark = pytest.mark.discord


class DummyCog(BaseCog):
    pass


def _fake(ctx: discord.ApplicationContext) -> FakeCtx:
    # The fixtures hand out real py-cord types; the recording state lives on the fake.
    return cast(FakeCtx, ctx)


async def test_send_error_builds_red_embed(fake_bot: SongbirdBot, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await DummyCog(fake_bot).send_error(fake_ctx, "boom")

    assert ctx.last_embed is not None
    assert ctx.last_embed.title == "Error"
    assert ctx.last_embed.description == "boom"
    assert ctx.last_embed.colour == discord.Color.red()
    assert ctx.last_ephemeral is True

    allowed_mentions = ctx.respond_calls[0].get("allowed_mentions")
    assert isinstance(allowed_mentions, discord.AllowedMentions)
    assert allowed_mentions.everyone is False
    assert allowed_mentions.users is False
    assert allowed_mentions.roles is False
    assert allowed_mentions.replied_user is False


async def test_send_success_builds_green_embed(fake_bot: SongbirdBot, fake_ctx: discord.ApplicationContext) -> None:
    ctx = _fake(fake_ctx)

    await DummyCog(fake_bot).send_success(fake_ctx, "done")

    assert ctx.last_embed is not None
    assert ctx.last_embed.title == "Success"
    assert ctx.last_embed.colour == discord.Colour.green()
    assert ctx.last_ephemeral is False


async def test_http_exception_falls_back_to_followup(
    monkeypatch: pytest.MonkeyPatch,
    fake_bot: SongbirdBot,
    fake_ctx: discord.ApplicationContext,
) -> None:
    ctx = _fake(fake_ctx)

    async def _raise(*_args: Any, **_kwargs: Any) -> None:
        response = cast(Any, SimpleNamespace(status=400, reason="Bad Request"))
        raise discord.HTTPException(response=response, message="already responded")

    monkeypatch.setattr(fake_ctx, "respond", _raise)

    await DummyCog(fake_bot).send_error(fake_ctx, "boom")

    assert ctx.respond_calls == []
    assert len(ctx.followup.calls) == 1
    method, kwargs = ctx.followup.calls[0]
    assert method == "send"
    assert kwargs["embed"].title == "Error"
    assert kwargs["ephemeral"] is True
