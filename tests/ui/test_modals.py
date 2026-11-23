"""Modal callbacks: feedback, file upload, user info and translation."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from songbird.config import Settings
from songbird.models.chat.exceptions import UserInfoNotFoundError
from songbird.models.feedback.exceptions import NotForumChannel
from songbird.services.container import ServiceContainer
from songbird.services.feedback import FeedbackService
from songbird.ui.modals.feedback import FeedbackModal
from songbird.ui.modals.file import FileModal
from songbird.ui.modals.info import UserInfoModal
from songbird.ui.modals.translate import TranslateMessageModal, TranslateModal
from songbird.ui.views.translate import TranslateView
from tests.ui.fakes import FakeInteraction, as_interaction

pytestmark = pytest.mark.discord


class _FeedbackService:
    def __init__(self, error: Exception | None = None, delivered: bool = True) -> None:
        self.calls: list[tuple[int, str, str]] = []
        self.error = error
        self.delivered = delivered

    async def send_feedback(self, user_id: int, username: str, text: str) -> bool:
        self.calls.append((user_id, username, text))
        if self.error is not None:
            raise self.error
        return self.delivered


def _feedback_modal(
    monkeypatch: pytest.MonkeyPatch, fake: _FeedbackService, *, sessions: list[object] | None = None
) -> FeedbackModal:
    @asynccontextmanager
    async def fake_session(_services: object) -> AsyncGenerator[object]:
        session = object()
        if sessions is not None:
            sessions.append(session)
        yield session

    def fake_create(_session: object, _services: object, _bot: object) -> FeedbackService:
        return cast(FeedbackService, fake)

    monkeypatch.setattr("songbird.ui.modals.feedback.get_session", fake_session)
    monkeypatch.setattr("songbird.ui.modals.feedback.create_feedback_service", fake_create)

    return FeedbackModal(cast(ServiceContainer, object()), cast(discord.Bot, object()))


def _message(content: str) -> discord.Message:
    return cast(discord.Message, type("_Message", (), {"content": content})())


async def test_feedback_modal_sends_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FeedbackService()
    modal = _feedback_modal(monkeypatch, service)
    modal.text.value = "great bot"  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction(user_id=11)

    await modal.callback(as_interaction(interaction))

    assert service.calls == [(11, "tester", "great bot")]
    assert interaction.response.defer_calls == [{"ephemeral": True}]
    assert interaction.followup.messages == [{"args": ("Feedback sent successfully!",), "ephemeral": True}]


async def test_feedback_modal_opens_its_own_session(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: the modal used the command's session, which was already closed by submit time.
    service = _FeedbackService()
    sessions: list[object] = []
    modal = _feedback_modal(monkeypatch, service, sessions=sessions)
    modal.text.value = "hello"  # pyright: ignore[reportPrivateUsage]

    await modal.callback(as_interaction(FakeInteraction()))

    assert len(sessions) == 1


async def test_feedback_modal_reports_missing_forum(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FeedbackService(NotForumChannel())
    modal = _feedback_modal(monkeypatch, service)
    modal.text.value = "hello"
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert interaction.followup.messages == [{"args": ("Error: feedback channel not set up properly",), "ephemeral": True}]


async def test_feedback_modal_reports_undelivered_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FeedbackService(delivered=False)
    modal = _feedback_modal(monkeypatch, service)
    modal.text.value = "hello"
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert interaction.followup.messages == [
        {"args": ("Could not deliver your feedback. Please try again later.",), "ephemeral": True}
    ]


async def test_feedback_modal_ignores_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FeedbackService()
    modal = _feedback_modal(monkeypatch, service)
    modal.text.value = ""
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert service.calls == []
    assert interaction.response.defer_calls == []
    assert interaction.followup.messages == []


async def test_feedback_modal_ignores_missing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FeedbackService()
    modal = _feedback_modal(monkeypatch, service)
    modal.text.value = "hello"
    interaction = FakeInteraction()
    interaction.user = None  # type: ignore[assignment]

    await modal.callback(as_interaction(interaction))

    assert service.calls == []
    assert interaction.response.defer_calls == []
    assert interaction.followup.messages == []


async def test_file_modal_uses_requested_extension() -> None:
    modal = FileModal()
    modal.text.value = "print('hi')"  # pyright: ignore[reportPrivateUsage]
    modal.extension.value = " py "  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    file = interaction.response.messages[0]["file"]
    assert isinstance(file, discord.File)
    assert file.filename == "file.py"
    assert interaction.response.messages[0]["allowed_mentions"].everyone is False


async def test_file_modal_defaults_to_txt() -> None:
    modal = FileModal()
    modal.text.value = "hello"  # pyright: ignore[reportPrivateUsage]
    modal.extension.value = ""  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    file = interaction.response.messages[0]["file"]
    assert isinstance(file, discord.File)
    assert file.filename == "file.txt"


class _Repo:
    def __init__(self, info: str | None = None, missing: bool = False) -> None:
        self.info = info
        self.missing = missing
        self.created: list[tuple[int, str]] = []
        self.updated: list[tuple[int, str]] = []

    async def get_user_info(self, _user_id: int) -> object:
        if self.missing:
            raise UserInfoNotFoundError()
        return type("_Info", (), {"user_info": self.info})()

    async def create_user_info(self, user_id: int, info: str) -> None:
        self.created.append((user_id, info))

    async def update_user_info(self, user_id: int, info: str) -> None:
        self.updated.append((user_id, info))


def _patch_info_session(monkeypatch: pytest.MonkeyPatch, repo: _Repo) -> None:
    @asynccontextmanager
    async def fake_session(_services: object) -> AsyncGenerator[object]:
        yield object()

    monkeypatch.setattr("songbird.ui.modals.info.get_session", fake_session)
    monkeypatch.setattr("songbird.ui.modals.info.get_user_info_repo", lambda _session: repo)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]


async def test_user_info_modal_create_loads_existing(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    repo = _Repo(info="likes tea")
    _patch_info_session(monkeypatch, repo)

    modal = await UserInfoModal.create(5, cast(ServiceContainer, settings))

    assert modal.info_text.value == "likes tea"  # pyright: ignore[reportPrivateUsage]
    assert repo.created == []


async def test_user_info_modal_create_initialises_missing_record(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    repo = _Repo(missing=True)
    _patch_info_session(monkeypatch, repo)

    modal = await UserInfoModal.create(5, cast(ServiceContainer, settings))

    assert modal.info_text.value is None  # pyright: ignore[reportPrivateUsage]
    assert repo.created == [(5, "")]


async def test_user_info_modal_callback_saves(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    repo = _Repo()
    _patch_info_session(monkeypatch, repo)
    modal = UserInfoModal(cast(ServiceContainer, settings))
    modal.info_text.value = "new info"  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction(user_id=3)

    await modal.callback(as_interaction(interaction))

    assert repo.updated == [(3, "new info")]
    assert interaction.response.messages == [{"args": ("Information saved successfully!",), "ephemeral": True}]


async def test_user_info_modal_callback_requires_user(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    repo = _Repo()
    _patch_info_session(monkeypatch, repo)
    modal = UserInfoModal(cast(ServiceContainer, settings))
    interaction = FakeInteraction()
    interaction.user = None  # type: ignore[assignment]

    await modal.callback(as_interaction(interaction))

    assert repo.updated == []
    assert interaction.response.messages == [{"args": ("Error: user not found",), "ephemeral": True}]


async def test_translate_modal_passes_trimmed_values() -> None:
    calls: list[tuple[str, str, str | None]] = []

    async def translate(text: str, target: str, source: str | None) -> tuple[str, str, str]:
        calls.append((text, target, source))
        return ("English", "Spanish", "Hola")

    modal = TranslateModal(translate)
    modal.source_language.value = " English "  # pyright: ignore[reportPrivateUsage]
    modal.target_language.value = " Spanish "  # pyright: ignore[reportPrivateUsage]
    modal.text.value = " Hello "  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert calls == [("Hello", "Spanish", "English")]
    assert interaction.response.defer_calls == [{}]
    view = interaction.followup.messages[0]["view"]
    assert isinstance(view, TranslateView)


async def test_translate_modal_defaults_blank_fields() -> None:
    # Regression: InputText.value is None for an untouched optional field; `.strip()` raised AttributeError.
    calls: list[tuple[str, str, str | None]] = []

    async def translate(text: str, target: str, source: str | None) -> tuple[str, str, str]:
        calls.append((text, target, source))
        return ("English", "Spanish", "Hola")

    modal = TranslateModal(translate)
    modal.source_language.value = None  # pyright: ignore[reportPrivateUsage]
    modal.target_language.value = None  # pyright: ignore[reportPrivateUsage]
    modal.text.value = " Hello "  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert calls == [("Hello", "english", "auto")]


async def test_translate_message_modal_uses_message_content() -> None:
    calls: list[tuple[str, str]] = []

    async def translate(text: str, target: str) -> tuple[str, str, str]:
        calls.append((text, target))
        return ("English", "German", "Hallo")

    modal = TranslateMessageModal(_message("Hello"), translate)
    modal.target_language.value = " German "  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert calls == [("Hello", "German")]
    assert interaction.response.defer_calls == [{}]
    assert isinstance(interaction.followup.messages[0]["view"], TranslateView)


async def test_translate_message_modal_defaults_target_to_english() -> None:
    calls: list[tuple[str, str]] = []

    async def translate(text: str, target: str) -> tuple[str, str, str]:
        calls.append((text, target))
        return ("German", "English", "Hello")

    modal = TranslateMessageModal(_message("Hallo"), translate)
    modal.target_language.value = None  # pyright: ignore[reportPrivateUsage]
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert calls == [("Hallo", "english")]


async def test_translate_message_modal_rejects_empty_text() -> None:
    calls: list[tuple[str, str]] = []

    async def translate(text: str, target: str) -> tuple[str, str, str]:
        calls.append((text, target))
        return ("English", "German", "Hallo")

    modal = TranslateMessageModal(cast(discord.Message, SimpleNamespace(content="")), translate)
    interaction = FakeInteraction()

    await modal.callback(as_interaction(interaction))

    assert calls == []
    assert interaction.response.defer_calls == []
    assert interaction.respond_calls[0]["args"] == ("Nothing to translate.",)


async def test_modals_expose_expected_inputs() -> None:
    modal = FileModal()

    assert modal.title == "Upload Text as a File"
    assert [item.label for item in modal.children] == ["Text to send", "File extension (e.g., txt, md, py)"]


async def test_translate_modal_title() -> None:
    async def translate(_text: str, _target: str, _source: str | None) -> tuple[str, str, str]:
        return ("a", "b", "c")

    modal = TranslateModal(translate)

    assert modal.title == "Translate Text"
    assert len(modal.children) == 3
