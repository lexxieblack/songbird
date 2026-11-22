# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""About, help and translate views: structure and button wiring."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from discord.ui import ActionRow

from songbird.bot import SongbirdBot
from songbird.config import Settings
from songbird.models.help import CategoryDef, HelpCommandEntry
from songbird.ui.views.about import AboutView
from songbird.ui.views.help import CATEGORIES, CategoryView, CommandDetailView, HelpView
from songbird.ui.views.translate import TranslateView
from tests.ui.fakes import FakeInteraction, as_interaction

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
    assert len(container.items) == 6  # header, separator, section, love text, separator, button row
    button_row = cast(ActionRow[Any], container.items[5])
    labels = [cast(Any, button).label for button in button_row.children]
    assert labels == ["Invite", "Source", "Privacy", "Terms"]
    # No source URL in the fixture, so invite stays enabled but the rest are disabled.
    assert [cast(Any, button).disabled for button in button_row.children] == [False, True, True, True]


async def test_about_view_disables_invite_for_private_bot(settings: Settings) -> None:
    view = AboutView(_bot(settings, public=False))

    button_row = cast(ActionRow[Any], _container(view).items[5])
    assert cast(Any, button_row.children[0]).disabled is True


async def test_about_view_enables_source_links(settings: Settings) -> None:
    configured = settings.model_copy(
        update={"bot": settings.bot.model_copy(update={"source_code_url": "https://github.com/example/songbird"})}
    )

    view = AboutView(_bot(configured))

    button_row = cast(ActionRow[Any], _container(view).items[5])
    assert [cast(Any, button).disabled for button in button_row.children] == [False, False, False, False]
    assert cast(Any, button_row.children[1]).url == "https://github.com/example/songbird"


async def test_help_view_has_one_section_per_category() -> None:
    view = HelpView()

    sections = _container(view).items[2:]
    assert len(sections) == len(CATEGORIES)
    assert [section.items[0].content for section in sections] == [f"{cat.emoji} {cat.label}" for cat in CATEGORIES.values()]


async def test_category_view_lists_commands() -> None:
    entry = HelpCommandEntry(
        key="ping", label="Ping", emoji="🏓", category="tools", description="latency", short_description="Check"
    )
    category = CategoryDef(label="Tools", emoji="🛠️", description="Utility")
    back = HelpView()

    view = CategoryView(category, [entry], back)

    sections = _container(view).items[2:]  # skip header and separator
    assert len(sections) == 1
    assert sections[0].items[0].content == "🏓  Ping"
    assert sections[0].items[1].content == "Check"


async def test_category_view_without_commands() -> None:
    category = CategoryDef(label="Empty", emoji="❓", description="nothing")
    view = CategoryView(category, [], HelpView())

    section = _container(view).items[2]
    assert section.items[0].content == "No commands available in this category"


async def test_command_detail_view_renders_description() -> None:
    entry = HelpCommandEntry(
        key="ping", label="Ping", emoji=None, category="tools", description="latency", short_description="Check"
    )
    view = CommandDetailView(entry, HelpView())

    body = _container(view).items[2]
    assert body.content == "latency"


async def test_category_forward_button_opens_detail() -> None:
    entry = HelpCommandEntry(
        key="ping", label="Ping", emoji="🏓", category="tools", description="latency", short_description="Check"
    )
    view = CategoryView(CategoryDef(label="Tools", emoji="🛠️", description="Utility"), [entry], HelpView())
    button = _container(view).items[2].accessory
    interaction = FakeInteraction()

    await button.callback(as_interaction(interaction))

    detail = interaction.response.edits[0]["view"]
    assert isinstance(detail, CommandDetailView)


async def test_translate_view_shows_heading_and_text() -> None:
    view = TranslateView("English", "Spanish", "Hola")

    items = _container(view).items
    assert items[0].items[0].content == "## English > Spanish"
    assert items[2].content == "Hola"


async def test_translate_view_has_timeout() -> None:
    view = TranslateView("a", "b", "c")

    assert view.timeout == 180
