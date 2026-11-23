"""The `/help` menu.

Structure mirrors Lawliet's help: category overview -> command list -> command detail,
with breadcrumbs, a back button and a category jump select. Everything is derived from
the live command registry, so names, usage and options cannot drift; only the tips,
per-command emoji and examples are hand-written.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import discord
from discord import MediaGalleryItem
from discord.commands import MessageCommand, SlashCommand, UserCommand
from discord.ui import ActionRow, BaseView, DesignerView, MediaGallery, Section, Select, Separator, TextDisplay
from pydantic import BaseModel

from songbird.models.help import CategoryDef
from songbird.ui.custom_components import BotLinkRow, ForwardButton, generate_back_container, generate_container
from songbird.utils.permissions import can_interact

if TYPE_CHECKING:
    from songbird.bot import SongbirdBot

_CATEGORY_BY_COG: dict[str, CategoryDef] = {
    "ToolsCog": CategoryDef(label="Tools", emoji="🛠️", description="Utility and tool commands"),
    "LLMCog": CategoryDef(label="LLM", emoji="🤖", description="AI-powered language model commands"),
    "BotCog": CategoryDef(label="Bot", emoji="ℹ️", description="General bot information and feedback"),
    "BlackwallCog": CategoryDef(label="Moderation", emoji="🛡️", description="Server configuration and moderation commands"),
}
# Owner-only cogs are never listed, not even for the owner: there is nothing to browse.
_HIDDEN_COGS = frozenset({"ManagementCog"})
_DEFAULT_CATEGORY = CategoryDef(label="Other", emoji="📦", description="Other commands")

# Cosmetic only: a command missing from this map falls back to its category emoji.
_EMOJI: dict[str, str] = {
    "chat": "💬",
    "file": "📄",
    "fix": "🔧",
    "blackwall": "🛡️",
    "manage": "⚙️",
    "ping": "🏓",
    "quickchat": "⚡",
    "summary": "📝",
    "translate": "🌍",
    "wolfram": "🐺",
    "about": "📋",
    "feedback": "💌",
    "help": "❓",
    "convert": "💱",
    "export": "📤",
}

# Hints the registry cannot know. Usage, options and descriptions are generated.
_NOTES: dict[str, str] = {
    "chat": (
        "Conversation stays private to you. DMs to Songbird join the same conversation. "
        "Use `/manage` to reset history or edit what the AI knows about you."
    ),
    "quickchat": "One-off answer, not saved to your conversation history.",
    "translate": ("Leave `text` out to get a form instead. You can also right-click a message → **Apps** → **Translate**."),
    "file": "Opens a form: paste the content, optionally set a file extension.",
    "fix": "Strips trackers and rewrites links (X/Twitter, TikTok, Reddit and more) so they embed properly.",
    "blackwall": (
        "Server admins only. Anyone else posting in the configured channel gets banned, "
        "so whitelist roles that need legitimate access."
    ),
    "summary": "Paste long text or a URL and get a short version back.",
    "export": "Sends your conversation as a JSON file, visible only to you.",
}

_EXAMPLES: dict[str, list[str]] = {
    "chat": ["/chat message:How do I get started with Python?"],
    "quickchat": ["/quickchat question:What is the capital of Norway?"],
    "convert": ["/convert amount:100 from:USD to:EUR"],
    "translate": ["/translate text:Good morning to_lang:ja"],
    "fix": ["/fix link:https://x.com/Songbird/status/123"],
    "wolfram": ["/wolfram query:integrate x^2 dx"],
}


class CommandDoc(BaseModel):
    name: str
    label: str
    emoji: str
    summary: str
    usage: str
    options: list[str]
    examples: list[str]
    notes: str | None = None
    category: CategoryDef


class CategoryGroup(BaseModel):
    category: CategoryDef
    docs: list[CommandDoc]


def _category(cmd: discord.ApplicationCommand[Any, Any, Any]) -> CategoryDef:
    return _CATEGORY_BY_COG.get(type(cmd.cog).__name__, _DEFAULT_CATEGORY)


def _slash_usage(cmd: SlashCommand) -> str:
    args = " ".join(f"<{option.name}>" if option.required else f"[{option.name}]" for option in cmd.options)
    return f"`/{cmd.qualified_name}{f' {args}' if args else ''}`"


def _slash_options(cmd: SlashCommand) -> list[str]:
    return [
        f"- `{option.name}` ({option.input_type.name}, {'required' if option.required else 'optional'}) — {option.description}"
        for option in cmd.options
    ]


def build_docs(commands: Iterable[discord.ApplicationCommand[Any, Any, Any]]) -> list[CommandDoc]:
    docs: list[CommandDoc] = []
    for cmd in commands:
        if type(cmd.cog).__name__ in _HIDDEN_COGS:
            continue
        category = _category(cmd)
        key = cmd.name.lower()
        if isinstance(cmd, SlashCommand):
            docs.append(
                CommandDoc(
                    name=cmd.qualified_name,
                    label=f"/{cmd.qualified_name}",
                    emoji=_EMOJI.get(key, category.emoji),
                    summary=cmd.description,
                    usage=_slash_usage(cmd),
                    options=_slash_options(cmd),
                    examples=_EXAMPLES.get(key, []),
                    notes=_NOTES.get(key),
                    category=category,
                )
            )
        elif isinstance(cmd, (MessageCommand, UserCommand)):
            target = "message" if isinstance(cmd, MessageCommand) else "user"
            docs.append(
                CommandDoc(
                    name=cmd.name,
                    label=f"{cmd.name} ({target} menu)",
                    emoji=_EMOJI.get(key, category.emoji),
                    summary=f"Right-click a {target} → Apps → {cmd.name}",
                    usage=f"Right-click a {target} → **Apps** → **{cmd.name}**",
                    options=[],
                    examples=_EXAMPLES.get(key, []),
                    notes=_NOTES.get(key),
                    category=category,
                )
            )
    return docs


def group_by_category(docs: list[CommandDoc]) -> list[CategoryGroup]:
    groups: dict[str, CategoryGroup] = {}
    for doc in docs:
        group = groups.get(doc.category.label)
        if group is None:
            group = groups[doc.category.label] = CategoryGroup(category=doc.category, docs=[])
        group.docs.append(doc)
    return list(groups.values())


def _render_detail(doc: CommandDoc) -> str:
    parts = [f"## {doc.emoji} {doc.label}", doc.summary, f"### Usage\n{doc.usage}"]
    if doc.options:
        parts.append("### Options\n" + "\n".join(doc.options))
    if doc.examples:
        parts.append("### Examples\n" + "\n".join(f"- {example}" for example in doc.examples))
    if doc.notes:
        parts.append(f"### Notes\n{doc.notes}")
    return "\n\n".join(parts)


class _CategorySelect(Select):
    def __init__(self, groups: list[CategoryGroup], current: str, back_view: BaseView, author_id: int | None) -> None:
        super().__init__(
            placeholder="Jump to another category",
            options=[
                discord.SelectOption(
                    label=group.category.label,
                    value=group.category.label,
                    description=f"{len(group.docs)} commands",
                    emoji=group.category.emoji,
                    default=group.category.label == current,
                )
                for group in groups
            ],
        )
        self.groups = groups
        self.back_view = back_view
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction) -> None:
        # The author is passed explicitly so ephemeral messages work even without interaction metadata.
        if not await can_interact(interaction, self.author_id):
            return
        values = self.values or []
        group = next((group for group in self.groups if group.category.label == (values[0] if values else None)), None)
        if group is not None:
            await interaction.response.edit_message(view=CategoryMenuView(self.groups, group, self.back_view, self.author_id))


class CommandMenuView(DesignerView):
    def __init__(self, doc: CommandDoc, back_view: BaseView) -> None:
        super().__init__()
        self.doc = doc
        self.add_item(
            generate_back_container(
                title="## Help",
                view=back_view,
                subtitle=f"-# {doc.category.emoji} {doc.category.label}",
                components=[TextDisplay(_render_detail(doc))],
            )
        )


class CategoryMenuView(DesignerView):
    def __init__(
        self, groups: list[CategoryGroup], group: CategoryGroup, back_view: BaseView, author_id: int | None = None
    ) -> None:
        super().__init__()
        # shortcut: one page per category; paginate if a category passes ~10 rows (Discord caps 40 components).
        components: list[Any] = [
            Section(
                TextDisplay(f"{doc.emoji} **{doc.label}** — {doc.summary}"),
                accessory=ForwardButton(CommandMenuView(doc, self)),
            )
            for doc in group.docs
        ]
        components += [
            Separator(),
            ActionRow(_CategorySelect(groups, group.category.label, back_view, author_id)),
        ]
        self.add_item(
            generate_back_container(
                title="## Help",
                view=back_view,
                subtitle=f"-# {group.category.emoji} {group.category.label} · {len(group.docs)} commands",
                components=components,
            )
        )


class HelpView(DesignerView):
    def __init__(self, bot: "SongbirdBot", docs: list[CommandDoc], author_id: int | None = None) -> None:
        super().__init__()
        self.groups = group_by_category(docs)
        self.category_views: dict[str, CategoryMenuView] = {}
        sections: list[Section[Any]] = []
        for group in self.groups:
            view = CategoryMenuView(self.groups, group, self, author_id)
            self.category_views[group.category.label] = view
            sections.append(
                Section(
                    TextDisplay(f"{group.category.emoji} **{group.category.label}**\n{group.category.description}"),
                    accessory=ForwardButton(view),
                )
            )
        components: list[Any] = []
        if banner_url := bot.settings.bot.help_banner_url:
            components += [
                MediaGallery(MediaGalleryItem(url=banner_url)),  # type: ignore[no-untyped-call]
                Separator(divider=False, spacing=discord.SeparatorSpacingSize.small),
            ]
        components += [BotLinkRow(bot), Separator(), *sections]
        self.add_item(
            generate_container(
                title="## Help",
                subtitle=f"-# {len(docs)} commands · pick a category",
                components=components,
            )
        )


def resolve(bot: "SongbirdBot", docs: list[CommandDoc], query: str, author_id: int | None = None) -> DesignerView | None:
    """Root, category or command view for a `/help` query, or None when nothing matches."""
    root = HelpView(bot, docs, author_id)
    needle = query.strip().lower()
    doc = next((doc for doc in docs if doc.label.lower() == needle), None)
    if doc is None:
        # Exact case first: "/translate" and the "Translate" message menu share a lowercase name.
        doc = next((doc for doc in docs if doc.name == query.strip()), None) or next(
            (doc for doc in docs if doc.name.lower() == needle), None
        )
    if doc is not None:
        return CommandMenuView(doc, root.category_views[doc.category.label])
    group = next((group for group in root.groups if group.category.label.lower() == needle), None)
    if group is not None:
        return root.category_views[group.category.label]
    return None
