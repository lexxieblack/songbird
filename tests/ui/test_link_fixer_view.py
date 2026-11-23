"""RestoreLinkView: restoring the original embed and deleting fixed copies."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from songbird.ui.views.link_fixer import RestoreLinkView
from tests.ui.fakes import FakeInteraction, as_interaction

pytestmark = pytest.mark.discord


def _message(message_id: int = 1) -> Any:
    message = SimpleNamespace(id=message_id, author=SimpleNamespace(id=7))
    message.channel = SimpleNamespace()
    message.edit = AsyncMock()
    return message


def _restore_button(view: RestoreLinkView) -> Any:
    return view.children[0]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]


async def test_restore_refetches_and_unhides_original() -> None:
    original = _message(10)
    refetched = _message(10)
    refetched.edit = AsyncMock()
    original.channel.fetch_message = AsyncMock(return_value=refetched)
    cached = {10}
    view = RestoreLinkView(original, cached)
    interaction = FakeInteraction()

    await _restore_button(view).callback(as_interaction(interaction))

    assert interaction.response.defer_calls == [{}]
    assert cached == set()
    original.channel.fetch_message.assert_awaited_once_with(10)
    refetched.edit.assert_awaited_once_with(suppress_embeds=False)


async def test_restore_deletes_fixed_messages() -> None:
    original = _message(10)
    original.channel.fetch_message = AsyncMock(return_value=_message(10))
    fixed = _message(11)
    fixed.delete = AsyncMock()
    view = RestoreLinkView(original, {10}, [fixed])
    interaction = FakeInteraction()

    await _restore_button(view).callback(as_interaction(interaction))

    fixed.delete.assert_awaited_once()


async def test_restore_suppresses_http_errors() -> None:
    original = _message(10)
    original.channel.fetch_message = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "gone"))
    view = RestoreLinkView(original, {10})
    interaction = FakeInteraction()

    await _restore_button(view).callback(as_interaction(interaction))

    assert interaction.response.defer_calls == [{}]


async def test_restore_works_without_interaction_metadata() -> None:
    # Regression: the view is sent with a plain channel.send, so the message has no interaction metadata
    # and can_interact used to reject every click.
    original = _message(10)
    original.channel.fetch_message = AsyncMock(return_value=_message(10))
    view = RestoreLinkView(original, {10})
    interaction = FakeInteraction()
    interaction.message.interaction_metadata = None
    interaction.message.interaction = None

    await _restore_button(view).callback(as_interaction(interaction))

    assert interaction.response.defer_calls == [{}]
    original.channel.fetch_message.assert_awaited_once_with(10)


async def test_restore_ignores_other_users() -> None:
    original = _message(10)
    original.channel.fetch_message = AsyncMock()
    view = RestoreLinkView(original, {10})
    interaction = FakeInteraction(user_id=8, permitted=False)

    await _restore_button(view).callback(as_interaction(interaction))

    assert interaction.response.defer_calls == []
    original.channel.fetch_message.assert_not_awaited()


async def test_timeout_clears_items_and_releases_cache_entry() -> None:
    cached = {1}
    view = RestoreLinkView(_message(), cached)

    await view.on_timeout()

    assert view.children == []  # pyright: ignore[reportUnknownMemberType]
    assert cached == set()
