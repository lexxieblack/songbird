# Songbird

A Discord bot that embodies the persona of **Song So Mi (Songbird)** from Cyberpunk 2077, post-canon (after Phantom Liberty). Features AI-powered conversations with memory, social media link fixing, translation, and computational knowledge queries.

![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?style=for-the-badge&logo=python)
![Pycord](https://img.shields.io/badge/Pycord-2.8.0-5865f2?style=for-the-badge&logo=python&logoColor=5865f2)
![Gemini](https://img.shields.io/badge/Model-Gemma_4-8E75B2?style=for-the-badge&logo=googlegemini)

---

## Features

### AI Chat (`/chat`)
Conversational AI driven by Google Gemini, with per-user conversation memory stored in PostgreSQL. The bot roleplays Songbird's personality — dry, sarcastic, intelligent, and refreshingly unfiltered. Chat via slash commands, DMs, or @mention the bot in any server.

### Quick Chat (`/quickchat`)
One-off AI queries with Google Search grounding — no context, no history saved.

### Summary (`/summary`)
Summarize text or URL content using AI.

### Link Fixing (`/fix`)
Fix social media embeds automatically or on demand:
- Twitter/X → fxtwitter
- Instagram → kkinstagram
- Reddit → rxddit
- TikTok → d.tiktokez
Also strips tracking parameters from all URLs (YouTube, etc.)

### Translation (`/translate`)
Translate text between languages via Google Translate. Supports a message context-menu command for quick translations.

### Wolfram Alpha (`/wolfram`)
Query Wolfram Alpha for computational knowledge, math, and factual answers — returns a GIF result.

### Manage (`/manage`)
Reset your conversation history, delete the last message, or edit your user info that the AI references.

### Export (`/export`)
Download your DM conversation history as JSON (12-hour cooldown).

### Feedback (`/feedback`)
Send feedback through a modal — creates a forum thread for follow-up discussion.

---

## Commands

| Command | Description |
|---|---|
| `/chat` | Conversational AI with memory |
| `/quickchat` | One-off AI query (no history) |
| `/summary` | Summarize text or a URL |
| `/manage` | Reset/delete/edit your conversation data |
| `/export` | Export conversation history as JSON |
| `/translate` | Translate text between languages |
| Translate (context menu) | Quick-translate any message |
| `/wolfram` | Query Wolfram Alpha |
| `/fix` | Fix social media links for better embeds |
| `/file` | Send text as a file attachment |
| `/ping` | Bot latency check |
| `/help` | Interactive help menu |
| `/about` | Bot info with invite and source links |
| `/feedback` | Send feedback |

---

## Prerequisites

- **Python 3.13+** ([website](https://www.python.org/))
- **PostgreSQL** ([website](https://www.postgresql.org/))
- **Google Gemini API key** ([get one here](https://aistudio.google.com/apikey))
- **Wolfram Alpha API key** ([get one here](https://developer.wolframalpha.com/))
- **Discord Bot Token** ([create an app](https://discord.com/developers/applications))

---

## Setup

```bash
# Clone the repository
git clone https://github.com/lexxieblack/songbird.git
cd songbird

# Create a virtual environment and install dependencies
uv sync
```

### Configuration

Songbird loads settings from `config.toml`, environment variables, and `.env` (in that order; TOML wins conflicts).

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `DB__URL` | PostgreSQL connection string (e.g. `postgresql+psycopg://user:pass@localhost:5432/songbird`) |
| `LLM__API_KEY` | Google Gemini API key |
| `WOLFRAM__API_KEY` | Wolfram Alpha API key |
| `BOT__OWNER_ID` | Your Discord user ID |
| `BOT__FEEDBACK_CHANNEL_ID` | Forum channel ID for feedback |
| `BOT__MANAGEMENT_GUILD_ID` | Optional server ID where owner-only management commands are visible |
| `BOT__DEBUG_GUILD_ID` | Optional server ID for development |

### Database Migrations

Migrations live in `database/chat/`, `database/feedback/`, and `database/management/`. Apply them manually in numeric order across all directories:

```bash
psql -U your_user -d your_db -f database/chat/01.schema.sql
psql -U your_user -d your_db -f database/chat/02.types.sql
psql -U your_user -d your_db -f database/chat/03.message.sql
psql -U your_user -d your_db -f database/management/01.schema.sql
psql -U your_user -d your_db -f database/management/02.user_ban.sql
psql -U your_user -d your_db -f database/management/03.guild_ban.sql
# ... etc
```

### Run

```bash
uv run -m songbird
```

---

## Development

```bash
uv run ruff check src/          # Lint
uv run ruff format src/         # Format
uv run mypy src/                # Type check (strict)
```

---

## Tech Stack

- **[py-cord](https://github.com/pycord-development/pycord)** — Discord API library
- **[Google Gemini](https://ai.google.dev/)** — LLM provider
- **[SQLAlchemy](https://www.sqlalchemy.org/)** — Async ORM (2.0 style)
- **[PostgreSQL](https://www.postgresql.org/)** — Database
- **[httpx](https://pypi.org/project/httpx/)** — Async HTTP client
- **[structlog](https://pypi.org/project/structlog/)** — Structured logging
- **[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)** — Configuration management

---

## Links

- [Invite Songbird](https://discord.com/oauth2/authorize?client_id=1407440417758122165)
- [Source Code](https://github.com/lexxieblack/songbird)
- [Privacy Policy](./PRIVACY.md)
- [Terms of Service](./TERMS.md)
