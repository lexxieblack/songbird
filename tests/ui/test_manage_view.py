# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

"""ManageView: panel structure, confirmation flows and the user-info button."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest
from discord.ui import ActionRow

from songbird.services.container import ServiceContainer
from songbird.ui.modals.info import UserInfoModal
from songbird.ui.views import manage
from songbird.ui.views.manage import ManageView
from tests.ui.fakes import FakeInteraction, as_interaction

pytestmark = pytest.mark.discord


def _container(view: object) -> Any:
    return cast(Any, view).children[0]


def _services() -> ServiceContainer:
    return cast(ServiceContainer, SimpleNamespace())


def _confirm_button(view: Any) -> Any:
    row = cast(ActionRow[Any], view.children[1])
    return row.children[0]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]


def _patch_session(monkeypatch: pytest.MonkeyPatch, conversation: Any) -> None:
    @asynccontextmanager
    async def fake_session(_services: ServiceContainer) -> AsyncGenerator[object]:
        yield object()

    monkeypatch.setattr(manage, "get_session", fake_session)
    monkeypatch.setattr(manage, "create_private_conversation_service", lambda _session, _services: conversation)


async def test_manage_view_lists_three_actions() -> None:
    view = ManageView(_services())

    sections = _container(view).items[2:]
    assert len(sections) == 3
    assert [section.items[0].content for section in sections] == [
        "### Reset Conversation",
        "### Delete Last Message",
        "### Edit User Info",
    ]


async def test_reset_conversation_success(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[int] = []

    async def delete_all_messages(user_id: int) -> int:
        deleted.append(user_id)
        return 4

    _patch_session(monkeypatch, SimpleNamespace(delete_all_messages=delete_all_messages))
    view = manage._make_reset_confirm_view(ManageView(_services()))  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction(user_id=8)

    await _confirm_button(view).callback(as_interaction(interaction))

    assert deleted == [8]
    assert interaction.response.defer_calls == [{}]
    assert interaction.edit_original[0]["view"].children[0].items[0].items[0].content == "## Conversation Reset"


async def test_reset_conversation_failure_reports_to_user(monkeypatch: pytest.MonkeyPatch) -> None:
    async def delete_all_messages(_user_id: int) -> int:
        raise RuntimeError("db down")

    _patch_session(monkeypatch, SimpleNamespace(delete_all_messages=delete_all_messages))
    view = manage._make_reset_confirm_view(ManageView(_services()))  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await _confirm_button(view).callback(as_interaction(interaction))

    assert interaction.followup.messages == [{"args": ("Failed to delete conversation history.",), "ephemeral": True}]
    assert interaction.edit_original == []


async def test_delete_last_message_success(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[int] = []

    async def delete_last_message(user_id: int) -> None:
        deleted.append(user_id)

    _patch_session(monkeypatch, SimpleNamespace(delete_last_message=delete_last_message))
    view = manage._make_delete_last_confirm_view(ManageView(_services()))  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction(user_id=3)

    await _confirm_button(view).callback(as_interaction(interaction))

    assert deleted == [3]
    assert interaction.edit_original[0]["view"].children[0].items[0].items[0].content == "## Message Deleted"


async def test_delete_last_message_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def delete_last_message(_user_id: int) -> None:
        raise RuntimeError("db down")

    _patch_session(monkeypatch, SimpleNamespace(delete_last_message=delete_last_message))
    view = manage._make_delete_last_confirm_view(ManageView(_services()))  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await _confirm_button(view).callback(as_interaction(interaction))

    assert interaction.followup.messages == [{"args": ("Failed to delete last message.",), "ephemeral": True}]


async def test_cancel_restores_manage_view() -> None:
    manage_view = ManageView(_services())
    view = manage._make_reset_confirm_view(manage_view)  # pyright: ignore[reportPrivateUsage]
    row = cast(ActionRow[Any], view.children[1])  # pyright: ignore[reportUnknownMemberType]
    interaction = FakeInteraction()

    await row.children[1].callback(as_interaction(interaction))  # pyright: ignore[reportUnknownMemberType]

    assert interaction.response.edits == [{"view": manage_view}]


async def test_edit_user_info_button_opens_modal(monkeypatch: pytest.MonkeyPatch) -> None:
    modal = object()

    async def create(_user_id: int, _services: ServiceContainer) -> object:
        return modal

    monkeypatch.setattr(UserInfoModal, "create", create)
    view = ManageView(_services())
    button = _container(view).items[4].accessory
    interaction = FakeInteraction()

    await button.callback(as_interaction(interaction))

    assert interaction.response.modals == [modal]


async def test_edit_user_info_requires_author(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create(_user_id: int, _services: ServiceContainer) -> object:
        raise AssertionError("should not open")

    monkeypatch.setattr(UserInfoModal, "create", create)
    view = ManageView(_services())
    button = _container(view).items[4].accessory
    interaction = FakeInteraction(permitted=False)

    await button.callback(as_interaction(interaction))

    assert interaction.response.modals == []
