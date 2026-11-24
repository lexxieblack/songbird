# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""About and translate views: structure and button wiring."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from discord.ui import ActionRow

from songbird.bot import SongbirdBot
from songbird.config import Settings
from songbird.ui.views.about import AboutView
from songbird.ui.views.translate import TranslateView

pytestmark = pytest.mark.discord


def _container(view: object) -> Any:
    return cast(Any, view).children[0]


def _bot(settings: Settings, *, user: bool = True, public: bool = True) -> SongbirdBot:
    fake = SimpleNamespace(
        user=SimpleNamespace(id=123, name="Songbird", display_avatar=SimpleNamespace(url="https://avatar")) if user else None,
        app_info=SimpleNamespace(bot_public=public),
        settings=settings,
    )
    return cast(SongbirdBot, fake)


async def test_about_view_without_user_is_empty(settings: Settings) -> None:
    view = AboutView(_bot(settings, user=False))

    assert len(view.children) == 0


async def test_about_view_builds_container_and_links(settings: Settings) -> None:
    view = AboutView(_bot(settings))

    container = _container(view)
    assert len(container.items) == 7  # header, separator, section, pitch, love text, separator, button row
    button_row = cast(ActionRow[Any], container.items[6])
    labels = [cast(Any, button).label for button in button_row.children]
    assert labels == ["Add App", "Source", "Issues", "Privacy", "Terms"]
    # No source URL in the fixture, so install stays enabled but the rest are disabled.
    assert [cast(Any, button).disabled for button in button_row.children] == [False, True, True, True, True]


async def test_about_view_disables_install_for_private_bot(settings: Settings) -> None:
    view = AboutView(_bot(settings, public=False))

    button_row = cast(ActionRow[Any], _container(view).items[6])
    assert cast(Any, button_row.children[0]).disabled is True


async def test_about_view_enables_source_links(settings: Settings) -> None:
    configured = settings.model_copy(
        update={"bot": settings.bot.model_copy(update={"source_code_url": "https://github.com/example/songbird"})}
    )

    view = AboutView(_bot(configured))

    button_row = cast(ActionRow[Any], _container(view).items[6])
    assert [cast(Any, button).disabled for button in button_row.children] == [False, False, False, False, False]
    assert cast(Any, button_row.children[1]).url == "https://github.com/example/songbird"
    assert cast(Any, button_row.children[2]).url == "https://github.com/example/songbird/issues"


async def test_translate_view_shows_heading_and_text() -> None:
    view = TranslateView("English", "Spanish", "Hola")

    items = _container(view).items
    assert items[0].items[0].content == "## English > Spanish"
    assert items[2].content == "Hola"


async def test_translate_view_has_timeout() -> None:
    view = TranslateView("a", "b", "c")

    assert view.timeout == 180
