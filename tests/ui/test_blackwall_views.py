"""Blackwall views: panel rendering, action buttons and log output."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from songbird.config import Settings
from songbird.models.management.blackwall import BlackwallPunishment
from songbird.ui.views.blackwall import buttons
from songbird.ui.views.blackwall.__main__ import BlackwallView
from songbird.ui.views.blackwall.default_warning import BlackwallDefaultWarningView
from songbird.ui.views.blackwall.edit_punishment import BlackwallEditPunishmentView
from songbird.ui.views.blackwall.edit_roles import BlackwallEditRolesView
from songbird.ui.views.blackwall.log import BlackwallLogView
from tests.ui.fakes import FakeInteraction, as_interaction

pytestmark = pytest.mark.discord


def _container(view: object) -> Any:
    return cast(Any, view).children[0]


async def _noop(_interaction: discord.Interaction) -> None:
    return None


def _blackwall_view(settings: Settings, **overrides: Any) -> BlackwallView:
    values: dict[str, Any] = {
        "channel_id": None,
        "log_channel_id": None,
        "roles": [],
        "banned_count": 0,
        "punishment": BlackwallPunishment.BAN,
        "on_set_channel": _noop,
        "on_remove_channel": _noop,
        "on_set_log_channel": _noop,
        "on_remove_log_channel": _noop,
        "on_edit_roles": _noop,
        "on_edit_punishment": _noop,
        "settings": settings,
    }
    return BlackwallView(**{**values, **overrides})


async def test_panel_shows_unset_state(settings: Settings) -> None:
    items = _container(_blackwall_view(settings)).items[2:]

    assert items[0].items[0].content == "**Channel:** *Not Set*"
    assert items[0].accessory.label == "Set"
    assert items[1].items[0].content == "**Log Channel:** *Not Set*"
    assert items[2].items[0].content == "**Allowed Roles:** *Admins only*"
    assert items[3].items[0].content == "**Punishment:** Ban"
    assert items[4].content == "**Trigger Count:** 0"
    default_button = items[6].children[0]
    assert default_button.label == "Default Message"
    assert default_button.disabled is True


async def test_panel_shows_configured_state(settings: Settings) -> None:
    items = _container(_blackwall_view(settings, channel_id=5, log_channel_id=6, roles=[1, 2], banned_count=None)).items[2:]

    assert items[0].items[0].content == "**Channel:** <#5>"
    assert items[0].accessory.label == "Remove"
    assert items[1].items[0].content == "**Log Channel:** <#6>"
    assert items[2].items[0].content == "**Allowed Roles:** <@&1> <@&2>"
    assert items[4].content == "**Trigger Count:** 0"
    assert items[6].children[0].disabled is False


async def test_panel_includes_gallery_when_configured(settings: Settings) -> None:
    configured = settings.model_copy(
        update={"blackwall": settings.blackwall.model_copy(update={"image_url": "https://example.com/image.png"})}
    )

    items = _container(_blackwall_view(configured)).items

    assert type(items[2]).__name__ == "MediaGallery"
    assert type(items[3]).__name__ == "Separator"


async def test_default_warning_without_image() -> None:
    container = _container(BlackwallDefaultWarningView(None))

    assert len(container.items) == 6
    assert container.items[0].content == "### [WARNING] UNAUTHORIZED DATA STREAM DETECTED."


async def test_default_warning_with_image() -> None:
    container = _container(BlackwallDefaultWarningView("https://example.com/warning.png"))

    assert type(container.items[0]).__name__ == "MediaGallery"
    assert len(container.items) == 8


async def test_edit_punishment_lists_all_options_and_current(settings: Settings) -> None:
    view = BlackwallEditPunishmentView(BlackwallPunishment.WARN, _noop, _noop, settings)

    assert [option.value for option in view.punishment_select.options] == [p.value for p in BlackwallPunishment]
    text = _container(view).items[2].content
    assert "Current: **warn**" in text


async def test_punishment_select_defers_for_author() -> None:
    interaction = FakeInteraction()

    await BlackwallEditPunishmentView._on_punishment_select(as_interaction(interaction))  # pyright: ignore[reportPrivateUsage]

    assert interaction.response.defer_calls == [{}]


async def test_punishment_select_ignores_others() -> None:
    interaction = FakeInteraction(permitted=False)

    await BlackwallEditPunishmentView._on_punishment_select(as_interaction(interaction))  # pyright: ignore[reportPrivateUsage]

    assert interaction.response.defer_calls == []


async def test_edit_roles_preselects_current(settings: Settings) -> None:
    view = BlackwallEditRolesView([10, 20], _noop, _noop, settings)

    values = view.role_select.default_values
    assert [value.id for value in values] == [10, 20]


async def test_role_select_defers_for_author() -> None:
    interaction = FakeInteraction()

    await BlackwallEditRolesView._on_role_select(as_interaction(interaction))  # pyright: ignore[reportPrivateUsage]

    assert interaction.response.defer_calls == [{}]


async def test_action_button_runs_action_for_author() -> None:
    calls: list[int] = []

    async def action(_interaction: discord.Interaction) -> None:
        calls.append(1)

    button = buttons.ActionButton("Do", discord.ButtonStyle.primary, action)

    await button.callback(as_interaction(FakeInteraction()))

    assert calls == [1]


async def test_action_button_ignores_others() -> None:
    calls: list[int] = []

    async def action(_interaction: discord.Interaction) -> None:
        calls.append(1)

    button = buttons.ActionButton("Do", discord.ButtonStyle.primary, action)

    await button.callback(as_interaction(FakeInteraction(permitted=False)))

    assert calls == []


async def test_default_message_requires_channel() -> None:
    row = buttons.ButtonRow(None, None)
    interaction = FakeInteraction()

    await row.children[0].callback(as_interaction(interaction))  # pyright: ignore[reportUnknownMemberType]

    assert interaction.followup.messages == [{"args": ("No blackwall channel is set.",), "ephemeral": True}]


async def test_default_message_reports_missing_channel_object() -> None:
    row = buttons.ButtonRow(None, 5)
    interaction = FakeInteraction()

    await row.children[0].callback(as_interaction(interaction))  # pyright: ignore[reportUnknownMemberType]

    assert interaction.followup.messages == [{"args": ("The configured blackwall channel is unavailable.",), "ephemeral": True}]


async def test_default_message_posts_warning_to_channel() -> None:
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    interaction = FakeInteraction()
    interaction.client = SimpleNamespace(get_channel=lambda _channel_id: channel)  # pyright: ignore[reportUnknownLambdaType]
    row = buttons.ButtonRow("https://example.com/warning.png", 5)

    await row.children[0].callback(as_interaction(interaction))  # pyright: ignore[reportUnknownMemberType]

    channel.send.assert_awaited_once()
    send_call = channel.send.await_args
    assert send_call is not None
    sent = send_call.kwargs
    assert isinstance(sent["view"], BlackwallDefaultWarningView)
    assert sent["allowed_mentions"].everyone is False
    assert interaction.followup.messages == [{"args": ("Warning posted to <#5>.",), "ephemeral": True}]


def _member() -> discord.Member:
    now = datetime.now(UTC)
    roles = [SimpleNamespace(id=1, mention="<@&1>"), SimpleNamespace(id=2, mention="<@&2>")]
    fake = SimpleNamespace(
        mention="<@99>",
        name="tester",
        display_avatar=SimpleNamespace(url="https://example.com/avatar.png"),
        created_at=now - timedelta(days=3),
        joined_at=now - timedelta(days=2),
        roles=roles,
        guild=SimpleNamespace(id=99),
    )
    return cast(discord.Member, fake)


def _log_message(content: str = "hello", attachments: list[Any] | None = None) -> discord.Message:
    return cast(discord.Message, SimpleNamespace(content=content, attachments=attachments or []))


async def test_log_view_includes_member_details_and_message() -> None:
    attachment = SimpleNamespace(filename="a*b.txt")
    items = _container(BlackwallLogView(_member(), _log_message("hi there", [attachment]))).items

    assert items[0].items[0].content == "## Blackwall Trigger"
    assert items[0].items[1].content == "**User:** <@99>"
    assert items[1].content.startswith("**Account Age:** ")
    assert items[2].content.startswith("**Joined Server:** ")
    assert items[3].content == "**Roles:** <@&1>, <@&2>"
    assert "**Message:**" in items[5].content
    assert items[6].content == "**Attachments:**\n- a\\*b.txt"


async def test_log_view_truncates_long_message() -> None:
    items = _container(BlackwallLogView(_member(), _log_message("x" * 5000))).items

    message_item = next(item for item in items if "**Message:**" in getattr(item, "content", ""))
    assert len(message_item.content) < 4000
    assert message_item.content.endswith("```")


async def test_log_view_skips_empty_message_and_missing_join_date() -> None:
    member = _member()
    member = cast(discord.Member, SimpleNamespace(**{**vars(member), "joined_at": None, "roles": [SimpleNamespace(id=2)]}))
    items = _container(BlackwallLogView(member, _log_message("   "))).items

    contents = [getattr(item, "content", "") for item in items]
    assert not any("**Message:**" in content for content in contents)
    assert not any("**Joined Server:**" in content for content in contents)
    assert not any("**Roles:**" in content for content in contents)
