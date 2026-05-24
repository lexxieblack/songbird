from discord.ui import BaseView, DesignerView, Section, TextDisplay

from songbird.models.help import HelpCommandEntry
from songbird.ui.custom_components import ForwardButton, generate_back_container, generate_container

commands: list[HelpCommandEntry] = [
    HelpCommandEntry(
        key="chat",
        label="Chat",
        emoji="💬",
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
    # HelpCommand(
    #     key="feedback",
    #     label="Feedback",
    #     emoji="💬",
    #     description=(
    #         "**Send feedback**\n\n"
    #         "Send a message to the bot developer with your feedback.\n\n"
    #         "**Usage:** `/feedback`\n\n"
    #         "**What it does:**\n"
    #         "- Opens a window for feedback submission.\n"
    #         "- Forwards your message to the bot developer.\n"
    #         "- The developer will be able to reply to your feedback.\n"
    #         "- Your message is private and will not be shared."
    #     ),
    #     short_description="Provide feedback",
    # ),
    HelpCommandEntry(
        key="file",
        label="File",
        emoji="📄",
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
    # HelpCommand(
    #     key="manage",
    #     label="Manage",
    #     emoji="🛠️",
    #     description=(
    #         "**Conversation & data controls**\n\n"
    #         "Used to control conversation history, deletion, and other settings for your conversation with Songbird.\n\n"
    #         "**Usage:** `/manage`\n\n"
    #         "**What it does:**\n"
    #         "- Sends an ephemeral embed with buttons to control conversation settings.\n"
    #         "- Features:\n"
    #         "  - Reset the conversation\n"
    #         "  - Delete the last interaction\n"
    #         "  - Show conversation stats\n"
    #         "  - View the most recent messages\n"
    #         "  - Add information about yourself"
    #     ),
    #     short_description="Manage Songbird's conversations",
    # ),
    HelpCommandEntry(
        key="ping",
        label="Ping",
        emoji="🏓",
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
]


# TODO: add actual categories, not a list of all commands


def _generate_entry_view(entry: HelpCommandEntry, back_view: BaseView) -> DesignerView:
    view = DesignerView()
    components: list[TextDisplay] = []
    components.append(TextDisplay(entry.description))

    title = f"{(entry.emoji + ' ') if entry.emoji else ''} {entry.label}"
    container = generate_back_container(title=title, view=back_view, components=components)

    view.add_item(container)
    return view


def _generate_category_list(commands: list[HelpCommandEntry], main_view: BaseView) -> list[Section]:
    sections: list[Section] = []

    for entry in commands:
        title = f"{(entry.emoji + ' ') if entry.emoji else ''} {entry.label}"
        sections.append(
            Section(
                TextDisplay(title),
                TextDisplay(entry.short_description),
                accessory=ForwardButton(_generate_entry_view(entry, main_view)),
            )
        )

    return sections


class HelpView(DesignerView):
    def __init__(self):
        super().__init__()
        container = generate_container(
            title="Help",
            components=_generate_category_list(commands, self),
        )

        self.add_item(container)
