from typing import Any

from discord.ui import BaseView, DesignerView, Section, TextDisplay

from songbird.models.help import CategoryDef, HelpCommandEntry
from songbird.ui.custom_components import ForwardButton, generate_back_container, generate_container

CATEGORIES: dict[str, CategoryDef] = {
    "tools": CategoryDef(label="Tools", emoji="🛠️", description="Utility and tool commands"),
    "llm": CategoryDef(label="LLM", emoji="🤖", description="AI-powered language model commands"),
    "bot": CategoryDef(label="Bot", emoji="ℹ️", description="General bot information and feedback"),
}

_COMMAND_ENTRIES: list[HelpCommandEntry] = [
    HelpCommandEntry(
        key="chat",
        label="Chat",
        emoji="💬",
        category="llm",
        description="\n".join(
            [
                "**Talk with Songbird**\n",
                "Talk with Songbird (AI persona). The command can enrich replies by looking up URLs and web results.\n",
                "**Usage:** `/chat message:<your message>`\n",
                "**What it does:**",
                "- Maintains conversation context.",
                "- Uses web/URL lookups to add detail when relevant.\n",
                "**Tips:**",
                "- Messages are private between you and the bot.",
                "- You can DM Songbird for one-on-one chats — messages there are added to your conversation.",
                "- Use `/manage` to control conversation history and settings.",
            ]
        ),
        short_description="Chat with Songbird",
    ),
    HelpCommandEntry(
        key="file",
        label="File",
        emoji="📄",
        category="tools",
        description=(
            "**Send text as a file**\n\n"
            "Sends a text file with the given content and an optional file extension.\n\n"
            "**Usage:** `/file` (opens a modal)\n\n"
            "**What it does:**\n"
            "- Prompts for file content and an optional extension.\n"
            "- Creates and sends a text file to the channel.\n\n"
            "**Example:** Use to share code snippets or long text passages."
        ),
        short_description="Send text as a file",
    ),
    HelpCommandEntry(
        key="fix",
        label="Fix",
        emoji="🔧",
        category="tools",
        description=(
            "**Auto-fix links**\n\n"
            "Attempt to automatically fix links for better embeds.\n\n"
            "**Usage:** `/fix link:<url>`\n\n"
            "**What it does:**\n"
            "- Fixes links for websites like Twitter, Tiktok, Reddit, and more for better embeds and removes trackers.\n\n"
            "**Example:** `/fix link:http//example.com`"
        ),
        short_description="Fix links",
    ),
    HelpCommandEntry(
        key="manage",
        label="Manage",
        emoji="⚙️",
        category="llm",
        description=(
            "**Manage your conversation settings**\n\n"
            "Control your AI conversation history and personal context.\n\n"
            "**Usage:** `/manage`\n\n"
            "**What it does:**\n"
            "- Opens a management panel with these options:\n"
            "  - **Reset Conversation**: Deletes all your conversation history.\n"
            "  - **Delete Last Message**: Removes the most recent message.\n"
            "  - **Edit User Info**: Update context information the AI knows about you.\n\n"
            "**Tips:**\n"
            "- Use this to start fresh or correct the AI's understanding of you."
        ),
        short_description="Manage your conversation settings",
    ),
    HelpCommandEntry(
        key="ping",
        label="Ping",
        emoji="🏓",
        category="tools",
        description=(
            "**Check latency**\n\n"
            "Quickly measure bot latency.\n\n"
            "**Usage:** `/ping`\n\n"
            "**What it does:**\n"
            "- Shows the bot's current latency between the bot and the server."
        ),
        short_description="Check bot latency",
    ),
    HelpCommandEntry(
        key="quickchat",
        label="Quick Chat",
        emoji="⚡",
        category="llm",
        description=(
            "**Quick AI chat without memory**\n\n"
            "Engage with Songbird (AI persona) for a single exchange without affecting conversation history.\n\n"
            "**Usage:** `/quickchat message:<your message>`\n\n"
            "**What it does:**\n"
            "- Uses Google Gemini AI for a response.\n"
            "- Includes web/URL lookups for enriched replies.\n"
            "- Does NOT save to conversation history.\n\n"
            "**Tips:**\n"
            "- Ideal for one-off questions or requests that don't require context.\n"
            "- All messages are private."
        ),
        short_description="Quick AI chat without saving history",
    ),
    HelpCommandEntry(
        key="summary",
        label="Summary",
        emoji="📝",
        category="llm",
        description=(
            "**Summarize text**\n\n"
            "Create a short summary of the provided text or message.\n\n"
            "**Usage:** `/summary text:<text to summarize>`\n\n"
            "**What it does:**\n"
            "- Produces a concise summary suitable for quick reading or previews.\n"
            "- Can be used as an option on a message instead of a command.\n\n"
            "**Example:** `/summary text:Paste long article here...`"
        ),
        short_description="Summarize a message or text",
    ),
    HelpCommandEntry(
        key="translate",
        label="Translate",
        emoji="🌍",
        category="tools",
        description=(
            "**Translate text**\n\n"
            "Translate text between languages using Google Translate.\n\n"
            "**Usage:** `/translate text:<text> language:<language code>`\n\n"
            "**What it does:**\n"
            "- Returns a translation in the target language.\n"
            "- Can be used as an option on a message instead of a command.\n\n"
            "**Example:** `/translate text:Hello world language:es`"
        ),
        short_description="Translate a message or text",
    ),
    HelpCommandEntry(
        key="wolfram",
        label="Wolfram Alpha",
        emoji="🐺",
        category="tools",
        description=(
            "**Wolfram Alpha query**\n\n"
            "Run computational or factual queries via Wolfram Alpha (requires API key).\n\n"
            "**Usage:** `/wolfram query:<math or question>`\n\n"
            "**What it does:**\n"
            "- Forwards your query to Wolfram Alpha and returns a short result or link.\n\n"
            "**Example:** `/wolfram query:x^2 + 2x + 1 = 0`"
        ),
        short_description="Query Wolfram Alpha",
    ),
    HelpCommandEntry(
        key="about",
        label="About",
        emoji="📋",
        category="bot",
        description=(
            "**About Songbird**\n\n"
            "Displays general information about the bot, including invite and source code links.\n\n"
            "**Usage:** `/about`\n\n"
            "**What it does:**\n"
            "- Shows the bot's name, avatar, and short description.\n"
            "- Provides buttons to invite the bot to other servers and view its source code."
        ),
        short_description="Get information about the bot",
    ),
    HelpCommandEntry(
        key="feedback",
        label="Feedback",
        emoji="💌",
        category="bot",
        description=(
            "**Send feedback**\n\n"
            "Send a message directly to the bot owner.\n\n"
            "**Usage:** `/feedback` (opens a modal)\n\n"
            "**What it does:**\n"
            "- Opens a form where you can type your message.\n"
            "- Your message is forwarded to the bot owner's feedback channel.\n\n"
            "**Tips:**\n"
            "- Use this to report bugs, suggest features, or share your thoughts."
        ),
        short_description="Send feedback to the bot owner",
    ),
    HelpCommandEntry(
        key="help",
        label="Help",
        emoji="❓",
        category="bot",
        description=(
            "**Get help with Songbird**\n\n"
            "Browse all available commands organized by category.\n\n"
            "**Usage:** `/help`\n\n"
            "**What it does:**\n"
            "- Opens an interactive help menu with three categories:\n"
            "  - **Tools**: Utility commands like Translate, Fix, and Ping.\n"
            "  - **LLM**: AI-powered chat and summary commands.\n"
            "  - **Bot**: General bot information and feedback.\n"
            "- Navigate through categories to see commands and their details."
        ),
        short_description="Browse available commands",
    ),
]


def _get_commands_by_category() -> dict[str, list[HelpCommandEntry]]:
    result: dict[str, list[HelpCommandEntry]] = {}
    for entry in _COMMAND_ENTRIES:
        result.setdefault(entry.category, []).append(entry)
    return result


class CommandDetailView(DesignerView):
    def __init__(self, entry: HelpCommandEntry, back_view: BaseView):
        super().__init__()
        title = f"{(entry.emoji + ' ') if entry.emoji else ''} {entry.label}"
        container = generate_back_container(
            title=title,
            view=back_view,
            components=[TextDisplay(entry.description)],
        )
        self.add_item(container)


class CategoryView(DesignerView):
    def __init__(self, category: CategoryDef, commands: list[HelpCommandEntry], main_view: BaseView):
        super().__init__()
        title = f"{category.emoji} {category.label}"

        sections: list[Section[Any]] = []
        if commands:
            for entry in commands:
                entry_title = f"{(entry.emoji + ' ') if entry.emoji else ''} {entry.label}"
                sections.append(
                    Section(
                        TextDisplay(entry_title),
                        TextDisplay(entry.short_description),
                        accessory=ForwardButton(CommandDetailView(entry, self)),
                    )
                )
        else:
            sections.append(Section(TextDisplay("No commands available in this category")))

        container = generate_back_container(
            title=title,
            view=main_view,
            components=sections,
        )
        self.add_item(container)


class HelpView(DesignerView):
    def __init__(self) -> None:
        super().__init__()
        commands_by_category = _get_commands_by_category()
        sections: list[Section[Any]] = []
        for cat_key, cat_def in CATEGORIES.items():
            cat_commands = commands_by_category.get(cat_key, [])
            title = f"{cat_def.emoji} {cat_def.label}"
            sections.append(
                Section(
                    TextDisplay(title),
                    TextDisplay(cat_def.description),
                    accessory=ForwardButton(CategoryView(cat_def, cat_commands, self)),
                )
            )

        container = generate_container(title="Help", components=sections)
        self.add_item(container)
