"""Custom buttons, container builders and the confirm view."""

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest
from discord.ui import BaseView, TextDisplay

from songbird.ui.custom_components import (
    BackButton,
    ConfirmView,
    DeleteButton,
    ForwardButton,
    generate_back_container,
    generate_container,
)
from tests.ui.fakes import FakeInteraction, as_interaction

pytestmark = pytest.mark.discord


def _row(view: ConfirmView) -> Any:
    return cast(Any, view).children[1]


# def _container(view: object) -> Any:
#     return cast(Any, view).children[0]


async def _noop(_interaction: discord.Interaction) -> None:
    return None


async def test_delete_button_defers_and_deletes() -> None:
    interaction = FakeInteraction()

    await DeleteButton().callback(as_interaction(interaction))

    assert interaction.response.defer_calls == [{}]
    assert interaction.deleted_message is True


async def test_delete_button_ignores_other_users() -> None:
    interaction = FakeInteraction(permitted=False)

    await DeleteButton().callback(as_interaction(interaction))

    assert interaction.response.defer_calls == []
    assert interaction.deleted_message is False


async def test_delete_button_deletes_ephemeral_via_original_response() -> None:
    interaction = FakeInteraction()
    interaction.message.flags = discord.MessageFlags(ephemeral=True)

    await DeleteButton().callback(as_interaction(interaction))

    assert interaction.deleted_original is True
    assert interaction.deleted_message is False


async def test_delete_button_falls_back_to_webhook_for_original_response() -> None:
    # User-install apps can lack bot guild membership, so message.delete() raises 403.
    interaction = FakeInteraction(delete_forbidden=True)

    await DeleteButton().callback(as_interaction(interaction))

    assert interaction.deleted_original is True
    assert interaction.followup.deleted_ids == []


async def test_delete_button_falls_back_to_webhook_for_followup() -> None:
    interaction = FakeInteraction(delete_forbidden=True)
    interaction.original = SimpleNamespace(id=1)

    await DeleteButton().callback(as_interaction(interaction))

    assert interaction.followup.deleted_ids == [interaction.message.id]
    assert interaction.deleted_original is False


async def test_forward_button_swaps_view() -> None:
    interaction = FakeInteraction()
    target = generate_container("back", [])
    button = ForwardButton(cast(BaseView, target))

    await button.callback(as_interaction(interaction))

    assert interaction.response.edits == [{"view": target}]


async def test_back_button_swaps_view() -> None:
    interaction = FakeInteraction()
    target = generate_container("forward", [])
    button = BackButton(cast(BaseView, target))

    await button.callback(as_interaction(interaction))

    assert interaction.response.edits == [{"view": target}]


async def test_directional_button_ignores_other_users() -> None:
    interaction = FakeInteraction(permitted=False)
    button = BackButton(cast(BaseView, generate_container("x", [])))

    await button.callback(as_interaction(interaction))

    assert interaction.response.edits == []


async def test_generate_container_with_subtitle_and_components() -> None:
    component: TextDisplay[Any, Any] = TextDisplay("body")
    container: Any = generate_container("## Title", [component], subtitle="subtitle")

    section = container.items[0]
    assert [item.content for item in section.items] == ["## Title", "subtitle"]
    assert isinstance(section.accessory, DeleteButton)
    assert container.items[1].divider is True
    assert container.items[2] is component


async def test_generate_container_without_subtitle_or_components() -> None:
    container: Any = generate_container("## Title", [])

    assert len(container.items) == 1
    assert [item.content for item in container.items[0].items] == ["## Title"]


async def test_generate_back_container_uses_back_button() -> None:
    back_view = generate_container("main", [])
    container: Any = generate_back_container("## Details", cast(BaseView, back_view), [TextDisplay("body")], subtitle="sub")  # pyright: ignore[reportUnknownArgumentType]

    section = container.items[0]
    assert [item.content for item in section.items] == ["## Details", "sub"]
    assert isinstance(section.accessory, BackButton)
    assert cast(Any, section.accessory)._target_view is back_view


async def test_confirm_view_invokes_confirm_callback() -> None:
    interaction = FakeInteraction()
    calls: list[str] = []

    async def confirm(_interaction: discord.Interaction) -> None:
        calls.append("confirm")

    view = ConfirmView("sure?", confirm)
    button = _row(view).children[0]

    await button.callback(as_interaction(interaction))

    assert calls == ["confirm"]


async def test_confirm_view_invokes_cancel_callback() -> None:
    interaction = FakeInteraction()
    calls: list[str] = []

    async def cancel(_interaction: discord.Interaction) -> None:
        calls.append("cancel")

    view = ConfirmView("sure?", _noop, cancel_callback=cancel)
    button = _row(view).children[1]

    await button.callback(as_interaction(interaction))

    assert calls == ["cancel"]


async def test_confirm_view_default_cancel_deletes_message() -> None:
    interaction = FakeInteraction()
    view = ConfirmView("sure?", _noop)
    button = _row(view).children[1]

    await button.callback(as_interaction(interaction))

    assert interaction.response.defer_calls == [{}]
    assert interaction.deleted_message is True


async def test_confirm_view_custom_labels_and_timeout() -> None:
    view = ConfirmView("sure?", _noop, confirm_label="Yes", cancel_label="No", timeout=10)

    assert view.timeout == 10
    assert [button.label for button in _row(view).children] == ["Yes", "No"]


async def test_confirm_view_ignores_unauthorised_interaction() -> None:
    interaction = FakeInteraction(permitted=False)
    calls: list[str] = []

    async def confirm(_interaction: discord.Interaction) -> None:
        calls.append("confirm")

    button = _row(ConfirmView("sure?", confirm)).children[0]

    await button.callback(as_interaction(interaction))

    assert calls == []
