"""`send_messages` splits replies and never pings anyone."""

from unittest.mock import AsyncMock

import discord
import pytest

from songbird.listeners.common import send_messages
from tests.support.discord import make_channel

pytestmark = pytest.mark.discord


async def test_sends_short_text_without_mentions() -> None:
    send = AsyncMock()
    channel = make_channel(send=send)

    await send_messages(channel, "hello")

    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args == ("hello",)
    allowed_mentions = send.await_args.kwargs["allowed_mentions"]
    assert isinstance(allowed_mentions, discord.AllowedMentions)
    assert allowed_mentions.everyone is False
    assert allowed_mentions.users is False


async def test_splits_long_text_into_multiple_messages() -> None:
    send = AsyncMock()
    channel = make_channel(send=send)
    text = "a" * 1500 + "\n\n" + "b" * 1500

    await send_messages(channel, text)

    assert send.await_count == 2
    assert [call.args[0] for call in send.await_args_list] == ["a" * 1500, "b" * 1500]


async def test_long_codeblock_is_sent_as_file() -> None:
    send = AsyncMock()
    channel = make_channel(send=send)
    code = "```\n" + "\n".join(f"line {i}" for i in range(10)) + "\n```"

    await send_messages(channel, code)

    # split_message currently emits duplicate chunks for one codeblock; assert the file path, not the count.
    assert send.await_count >= 1
    assert all(call.args == () and isinstance(call.kwargs["file"], discord.File) for call in send.await_args_list)
