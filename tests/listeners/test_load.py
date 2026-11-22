"""Listener registration/unregistration wiring."""

from typing import Any

import pytest

from songbird.bot import SongbirdBot
from songbird.listeners import load_listeners, unload_listeners
from songbird.listeners.link_fixer import CACHED_MESSAGES

pytestmark = pytest.mark.discord


def test_load_listeners_registers_every_callback(fake_bot: SongbirdBot) -> None:
    load_listeners(fake_bot)

    listeners: list[Any] = vars(fake_bot)["listeners"]
    names = [listener.__name__ for listener in listeners]
    assert len(listeners) == 5
    assert names.count("on_message") == 3
    assert names.count("on_message_edit") == 1
    assert names.count("on_guild_join") == 1


def test_unload_listeners_clears_link_cache() -> None:
    CACHED_MESSAGES.add(1)

    unload_listeners()

    assert not CACHED_MESSAGES
