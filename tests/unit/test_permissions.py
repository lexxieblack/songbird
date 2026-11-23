from types import SimpleNamespace
from typing import cast

import discord
import pytest

from songbird.utils.permissions import can_interact


class FakeResponse:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def send_message(self, content: str, **kwargs: object) -> None:
        self.calls.append((content, kwargs))


def make_interaction(
    *,
    user_id: int | None = 1,
    author_id: int | None = 1,
    has_message: bool = True,
    has_author: bool = True,
    has_user: bool = True,
    use_metadata: bool = True,
    use_legacy: bool = False,
) -> tuple[discord.Interaction, FakeResponse]:
    response = FakeResponse()
    author = SimpleNamespace(id=author_id)
    message = (
        SimpleNamespace(
            interaction_metadata=SimpleNamespace(user=author) if has_author and use_metadata else None,
            interaction=SimpleNamespace(user=author) if has_author and use_legacy else None,
        )
        if has_message
        else None
    )
    user = SimpleNamespace(id=user_id) if has_user else None

    interaction = cast(discord.Interaction, SimpleNamespace(message=message, user=user, response=response))
    return interaction, response


async def test_allows_the_original_user() -> None:
    interaction, response = make_interaction(user_id=7, author_id=7)

    assert await can_interact(interaction) is True
    assert response.calls == []


async def test_uses_interaction_metadata_for_follow_up_messages() -> None:
    # Follow-ups have no legacy `interaction` field, only `interaction_metadata`.
    interaction, response = make_interaction(user_id=7, author_id=7, use_legacy=False)

    assert await can_interact(interaction) is True
    assert response.calls == []


async def test_falls_back_to_the_legacy_interaction_field() -> None:
    interaction, response = make_interaction(user_id=7, author_id=7, use_metadata=False, use_legacy=True)

    assert await can_interact(interaction) is True
    assert response.calls == []


async def test_explicit_author_id_wins_for_non_interaction_messages() -> None:
    interaction, response = make_interaction(user_id=7, author_id=7, use_metadata=False)

    assert await can_interact(interaction, author_id=7) is True
    assert response.calls == []


async def test_rejects_another_user_and_sends_an_ephemeral_message() -> None:
    interaction, response = make_interaction(user_id=7, author_id=8)

    assert await can_interact(interaction) is False
    assert response.calls == [("You do not have permission to interact with this", {"ephemeral": True})]


@pytest.mark.parametrize(
    ("has_message", "has_author", "has_user"),
    [
        (False, True, True),
        (True, False, True),
        (True, True, False),
    ],
)
async def test_rejects_incomplete_interactions(has_message: bool, has_author: bool, has_user: bool) -> None:
    interaction, response = make_interaction(has_message=has_message, has_author=has_author, has_user=has_user)

    assert await can_interact(interaction) is False
    assert response.calls == [("You do not have permission to interact with this", {"ephemeral": True})]
