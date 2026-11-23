# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

"""`/help`: registry-derived docs and Lawliet-style navigation."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from discord.commands import MessageCommand, SlashCommand
from discord.ui import MediaGallery

from songbird.cogs.bot import BotCog
from songbird.config import BotSettings
from songbird.ui.views.help import (
    CategoryMenuView,
    CommandMenuView,
    HelpView,
    build_docs,
    group_by_category,
    resolve,
)
from tests.cogs._support import invoke
from tests.support.discord import FakeCtx
from tests.ui.fakes import FakeInteraction, as_interaction

pytestmark = pytest.mark.discord


class _FakeCog:
    def _get_overridden_method(self, _method: Any) -> None:
        return None

    async def cog_check(self, _ctx: Any) -> bool:
        return True


class ToolsCog(_FakeCog):
    pass


class LLMCog(_FakeCog):
    pass


class ManagementCog(_FakeCog):
    pass


def _with_cog[C: (SlashCommand, MessageCommand)](cmd: C, cog: Any) -> C:
    # SlashCommand validates through the cog property setter; context menus hold a plain attribute.
    if isinstance(cmd, SlashCommand):
        cmd._cog = cog
    else:
        cmd.cog = cog
    return cmd


def _slash(
    cog: object, name: str = "convert", description: str = "Convert between currencies", options: bool = True
) -> SlashCommand:
    if options:

        async def with_options(ctx: Any, amount: float, target: str) -> None:
            pass

        cmd = SlashCommand(with_options, name=name, description=description)
    else:

        async def without_options(ctx: Any) -> None:
            pass

        cmd = SlashCommand(without_options, name=name, description=description)
    return _with_cog(cmd, cog)


def _message_command(cog: object) -> MessageCommand:
    async def callback(ctx: Any, message: Any) -> None:
        pass

    cmd = MessageCommand(callback, name="Translate")
    return _with_cog(cmd, cog)


def _items(view: Any) -> Any:
    return view.children[0].items


def _bot(banner: str | None = "https://example.com/banner.png") -> Any:
    return SimpleNamespace(
        user=SimpleNamespace(id=123),
        app_info=SimpleNamespace(bot_public=True),
        settings=SimpleNamespace(
            bot=BotSettings(source_code_url="https://github.com/lexxieblack/songbird", help_banner_url=banner)
        ),
    )


def test_build_docs_derives_usage_and_options_from_registry() -> None:
    docs = build_docs([_slash(ToolsCog())])

    doc = docs[0]
    assert doc.label == "/convert"
    assert doc.emoji == "💱"
    assert doc.category.label == "Tools"
    assert doc.usage == "`/convert <amount> <target>`"
    assert doc.options == [
        "- `amount` (number, required) — No description provided",
        "- `target` (string, required) — No description provided",
    ]


def test_build_docs_marks_optional_options() -> None:
    async def callback(ctx: Any, amount: float, target: str = "en") -> None:
        pass

    cmd = SlashCommand(callback, name="convert", description="Convert")
    _with_cog(cmd, ToolsCog())

    assert build_docs([cmd])[0].usage == "`/convert <amount> [target]`"


def test_build_docs_describes_message_commands() -> None:
    doc = build_docs([_message_command(ToolsCog())])[0]

    assert doc.label == "Translate (message menu)"
    assert doc.emoji == "🌍"
    assert doc.usage == "Right-click a message → **Apps** → **Translate**"
    assert doc.category.label == "Tools"


def test_build_docs_adds_notes_examples_and_falls_back_to_category_emoji() -> None:
    docs = build_docs([_slash(ToolsCog(), name="wolfram", description="Query Wolfram Alpha", options=False)])
    doc = docs[0]

    assert doc.emoji == "🐺"
    assert doc.examples == ["/wolfram query:integrate x^2 dx"]


def test_group_by_category_keeps_registry_order() -> None:
    docs = build_docs(
        [
            _slash(ToolsCog(), name="ping", description="Ping", options=False),
            _slash(LLMCog(), name="chat", description="Chat", options=False),
        ]
    )

    groups = group_by_category(docs)

    assert [group.category.label for group in groups] == ["Tools", "LLM"]
    assert [len(group.docs) for group in groups] == [1, 1]


def test_build_docs_omits_owner_only_cogs() -> None:
    docs = build_docs(
        [
            _slash(ManagementCog(), name="ban-user", description="Ban a user", options=False),
            _slash(ToolsCog(), name="ping", description="Ping", options=False),
        ]
    )

    assert [doc.name for doc in docs] == ["ping"]


async def test_root_view_lists_one_section_per_category() -> None:
    docs = build_docs(
        [
            _slash(ToolsCog(), name="ping", description="Ping", options=False),
            _slash(LLMCog(), name="chat", description="Chat", options=False),
        ]
    )

    view = HelpView(_bot(), docs)
    items = _items(view)

    assert "2 commands" in items[0].items[1].content
    assert isinstance(items[2], MediaGallery)
    assert [button.label for button in items[4].children] == ["Invite", "Source", "Issues", "Privacy", "Terms"]
    categories = items[6:]
    assert [section.items[0].content.split("\n")[0] for section in categories] == ["🛠️ **Tools**", "🤖 **LLM**"]
    assert isinstance(categories[0].accessory, type(categories[1].accessory))


async def test_root_view_skips_the_banner_when_unset() -> None:
    view = HelpView(_bot(banner=None), build_docs([_slash(ToolsCog(), name="ping", description="Ping", options=False)]))

    items = _items(view)
    assert not any(isinstance(item, MediaGallery) for item in items)
    assert [button.label for button in items[2].children] == ["Invite", "Source", "Issues", "Privacy", "Terms"]


async def test_root_forward_button_opens_category_view() -> None:
    view = HelpView(_bot(), build_docs([_slash(ToolsCog(), name="ping", description="Ping", options=False)]))
    interaction = FakeInteraction()

    await _items(view)[6].accessory.callback(as_interaction(interaction))

    edited = interaction.response.edits[0]["view"]
    assert isinstance(edited, CategoryMenuView)
    assert "🛠️ Tools" in _items(edited)[0].items[1].content


async def test_category_view_lists_commands_and_jump_select() -> None:
    docs = build_docs(
        [
            _slash(ToolsCog(), name="ping", description="Ping the bot", options=False),
            _slash(LLMCog(), name="chat", description="Chat with Songbird", options=False),
        ]
    )
    view = HelpView(_bot(), docs)

    tools = view.category_views["Tools"]
    rows = _items(tools)[2:-2]
    assert [row.items[0].content for row in rows] == ["🏓 **/ping** — Ping the bot"]

    select_row = _items(tools)[-1]
    options = select_row.children[0].options
    assert [option.label for option in options] == ["Tools", "LLM"]
    assert [option.default for option in options] == [True, False]


async def test_category_select_jumps_to_another_category() -> None:
    docs = build_docs(
        [
            _slash(ToolsCog(), name="ping", description="Ping", options=False),
            _slash(LLMCog(), name="chat", description="Chat", options=False),
        ]
    )
    root = HelpView(_bot(), docs)
    select = _items(root.category_views["Tools"])[-1].children[0]
    interaction = FakeInteraction()

    select._selected_values = ["LLM"]
    select._interaction = SimpleNamespace(data={"values": ["LLM"]})
    await select.callback(as_interaction(interaction))

    edited = interaction.response.edits[0]["view"]
    assert isinstance(edited, CategoryMenuView)
    assert "🤖 LLM" in _items(edited)[0].items[1].content


async def test_category_back_button_returns_to_root() -> None:
    root = HelpView(_bot(), build_docs([_slash(ToolsCog(), name="ping", description="Ping", options=False)]))
    interaction = FakeInteraction()

    await _items(root.category_views["Tools"])[0].accessory.callback(as_interaction(interaction))

    assert interaction.response.edits[0]["view"] is root


async def test_command_detail_renders_usage_options_examples_and_notes() -> None:
    docs = build_docs([_slash(ToolsCog(), name="convert", description="Convert currencies")])
    doc = docs[0]

    view = CommandMenuView(doc, HelpView(_bot(), docs))
    body = _items(view)[2].content

    assert body.startswith("## 💱 /convert")
    assert "### Usage\n`/convert <amount> <target>`" in body
    assert "### Options" in body
    assert "### Examples\n- /convert amount:100 from:USD to:EUR" in body


async def test_command_back_button_returns_to_category() -> None:
    docs = build_docs([_slash(ToolsCog(), name="ping", description="Ping", options=False)])
    root = HelpView(_bot(), docs)
    category = root.category_views["Tools"]
    detail = CommandMenuView(docs[0], category)
    interaction = FakeInteraction()

    await _items(detail)[0].accessory.callback(as_interaction(interaction))

    assert interaction.response.edits[0]["view"] is category


async def test_resolve_accepts_commands_labels_and_categories() -> None:
    docs = build_docs(
        [
            _slash(ToolsCog(), name="ping", description="Ping", options=False),
            _slash(LLMCog(), name="chat", description="Chat", options=False),
        ]
    )

    assert isinstance(resolve(_bot(), docs, "ping"), CommandMenuView)
    assert isinstance(resolve(_bot(), docs, "/ping"), CommandMenuView)
    assert isinstance(resolve(_bot(), docs, "tools"), CategoryMenuView)
    assert resolve(_bot(), docs, "nope") is None


async def test_resolve_disambiguates_slash_and_message_menu() -> None:
    docs = build_docs(
        [
            _slash(ToolsCog(), name="translate", description="Translate", options=False),
            _message_command(ToolsCog()),
        ]
    )

    slash = resolve(_bot(), docs, "translate")
    message = resolve(_bot(), docs, "Translate")
    label = resolve(_bot(), docs, "/translate")

    assert isinstance(slash, CommandMenuView) and slash.doc.label == "/translate"
    assert isinstance(message, CommandMenuView) and "message menu" in message.doc.label
    assert isinstance(label, CommandMenuView) and label.doc.label == "/translate"


async def test_category_select_ignores_other_users() -> None:
    root = HelpView(_bot(), build_docs([_slash(ToolsCog(), name="ping", description="Ping", options=False)]))
    select = _items(root.category_views["Tools"])[-1].children[0]
    interaction = FakeInteraction(permitted=False)

    select._selected_values = ["Tools"]
    select._interaction = SimpleNamespace(data={"values": ["Tools"]})
    await select.callback(as_interaction(interaction))

    assert interaction.response.edits == []


def _populate(bot: Any, command: SlashCommand) -> None:
    bot.application_commands = [command]


async def test_help_responds_ephemerally_with_root_menu(fake_bot: Any, fake_ctx: Any) -> None:
    _populate(fake_bot, _slash(ToolsCog(), name="ping", description="Ping", options=False))
    cog = BotCog(fake_bot)
    ctx = cast(FakeCtx, fake_ctx)

    await invoke(cog, "help", fake_ctx, query=None)

    call = ctx.respond_calls[0]
    assert isinstance(call["view"], HelpView)
    assert call["ephemeral"] is True


async def test_help_opens_a_command_directly(fake_bot: Any, fake_ctx: Any) -> None:
    _populate(fake_bot, _slash(ToolsCog(), name="ping", description="Ping", options=False))
    cog = BotCog(fake_bot)

    await invoke(cog, "help", fake_ctx, query="ping")

    assert isinstance(cast(FakeCtx, fake_ctx).respond_calls[0]["view"], CommandMenuView)


async def test_help_rejects_unknown_query(fake_bot: Any, fake_ctx: Any) -> None:
    _populate(fake_bot, _slash(ToolsCog(), name="ping", description="Ping", options=False))
    cog = BotCog(fake_bot)
    ctx = cast(FakeCtx, fake_ctx)

    await invoke(cog, "help", fake_ctx, query="nope")

    call = ctx.respond_calls[0]
    assert call["args"] == ("No command or category matches that.",)
    assert call["ephemeral"] is True
