"""Minimal recording fake for discord.Interaction used by UI callback tests."""

from types import SimpleNamespace
from typing import Any, cast

import discord


class FakeResponse:
    def __init__(self) -> None:
        self.defer_calls: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.modals: list[object] = []
        self.edits: list[dict[str, Any]] = []

    async def defer(self, **kwargs: Any) -> None:
        self.defer_calls.append(kwargs)

    async def send_message(self, *args: Any, **kwargs: Any) -> None:
        self.messages.append({"args": args, **kwargs})

    async def send_modal(self, modal: object) -> None:
        self.modals.append(modal)

    async def edit_message(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)


class FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send(self, *args: Any, **kwargs: Any) -> None:
        self.messages.append({"args": args, **kwargs})


class FakeInteraction:
    """Duck-types the interaction surface: response, followup, client and message."""

    def __init__(self, user_id: int = 7, permitted: bool = True) -> None:
        self.user = SimpleNamespace(id=user_id, name="tester")
        # can_interact compares the clicker against the interaction's original user.
        author_id = user_id if permitted else user_id + 1
        author = SimpleNamespace(id=author_id)
        self.message = SimpleNamespace(
            interaction_metadata=SimpleNamespace(user=author),
            interaction=SimpleNamespace(user=author),
            flags=discord.MessageFlags(),
            delete=self._delete_message,
        )
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.client = SimpleNamespace(get_channel=lambda _channel_id: None)  # pyright: ignore[reportUnknownLambdaType]
        self.deleted_original = False
        self.deleted_message = False
        self.edit_original: list[dict[str, Any]] = []
        self.respond_calls: list[dict[str, Any]] = []

    async def _delete_message(self) -> None:
        self.deleted_message = True

    async def delete_original_response(self) -> None:
        self.deleted_original = True

    async def edit_original_response(self, **kwargs: Any) -> None:
        self.edit_original.append(kwargs)

    async def respond(self, *args: Any, **kwargs: Any) -> None:
        self.respond_calls.append({"args": args, **kwargs})


def as_interaction(fake: FakeInteraction) -> discord.Interaction:
    return cast(discord.Interaction, fake)
