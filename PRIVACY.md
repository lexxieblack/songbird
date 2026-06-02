# Privacy Policy

**Last updated:** 2026-06-02
**Bot:** Songbird
**Contact:** Join the [support server](https://discord.gg/your-invite-here) or message the bot owner on Discord.

---

## 1. What data we collect

### 1.1 Data you actively provide

| Data | Where it's stored | Purpose |
|---|---|---|
| Message content sent to the bot (DMs and @mentions) | PostgreSQL (`chat.message`, `chat.guild_message` tables) | To power AI conversations with memory |
| Optional biographical info (name, age, bio, gender) set via `/manage` | PostgreSQL (`chat.user_info` table) | To let you provide context the AI can reference |
| Feedback you submit via `/feedback` | Discord forum threads (not in our database beyond the thread mapping) | To receive and respond to user feedback |
| Slash command inputs | Not stored long-term; processed in memory | To execute the command you requested |

### 1.2 Data collected automatically

| Data | Where it's stored | Purpose |
|---|---|---|
| Discord User ID | PostgreSQL (all chat/user_info tables) | To associate conversations with your account |
| Discord Guild ID | PostgreSQL (`chat.guild_message` table) | To associate server conversations with that guild |
| Discord username and display name | Sent to the LLM provider as context; not stored separately | To give the AI awareness of who it's talking to |
| Message timestamps | PostgreSQL (all chat tables) | To maintain conversation ordering |

### 1.3 Data we do NOT collect

- Your IP address
- Your email address
- Your Discord password or token
- Your direct messages with other users (only messages sent to the bot)
- Voice or video data
- Files or images you attach (unless explicitly processed by a command)

---

## 2. How we use your data

- To generate AI responses in conversations
- To maintain conversation history across sessions
- To improve the bot's responses by providing the LLM with relevant context
- To respond to feedback and support requests
- To debug and fix issues (via structured logs)

---

## 3. Data shared with third parties

### 3.1 Google Gemini API

When you chat with Songbird, your messages (including conversation history) are sent to **Google's Gemini API** for AI processing. This includes:
- The conversation history (up to 30 prior messages)
- Your current message
- Your Discord username and display name
- Any user info you've provided via `/manage`

Google's processing is governed by [Google's Privacy Policy](https://policies.google.com/privacy) and [Google's AI Terms](https://ai.google.dev/terms). Songbird does not control how Google handles data sent to their API.

### 3.2 Wolfram Alpha

When you use `/wolfram`, your query text is sent to Wolfram Alpha for processing. See [Wolfram's Privacy Policy](https://www.wolfram.com/legal/privacy/).

### 3.3 Google Translate

When you use `/translate`, your text is sent to Google Translate. See [Google's Privacy Policy](https://policies.google.com/privacy).

### 3.4 Link resolution

When you use `/fix` or the auto link-fixer processes a message, HEAD requests may be sent to the URL's host to resolve redirects. No identifying information beyond standard HTTP headers is sent.

---

## 4. Data storage and security

- **Database:** PostgreSQL, hosted on the bot operator's infrastructure
- **Encryption:** Standard database-level security practices are followed
- **Logs:** Message content may appear in application logs (stdout) for debugging. Logs are not publicly accessible.
- **In-memory caches:** Suppressed message IDs are cached ephemerally (cleared on restart)
- **No third-party analytics:** We do not use Google Analytics, Sentry, or similar services

### Security measures

- Database access is restricted to the bot application only
- API keys are stored in environment variables, never in code
- The bot token is kept confidential and not shared

---

## 5. Data retention

- **Conversation messages:** Stored indefinitely until you delete them
- **User info:** Stored indefinitely until overwritten
- **Feedback threads:** Retained in Discord indefinitely
- **Logs:** Retained according to the hosting environment's log rotation

We do not automatically delete old conversation data. You control your data (see section 6).

---

## 6. Your rights and control

### 6.1 Export your data

Use `/export` to download your DM conversation history as a JSON file. This includes every message you and the bot have exchanged in DMs, ordered by timestamp.

**What's included:** All messages from `chat.message` for your user ID (role, content, timestamp).
**What's not included:** Guild/server conversations (these are associated with the guild, not your user ID), user info biographical data.

### 6.2 Delete your data

| Action | Command | What it does |
|---|---|---|
| Reset all conversations | `/manage` → "Reset Conversation" | Deletes all your DM messages from the database |
| Delete last message | `/manage` → "Delete Last Message" | Deletes only your most recent DM message |
| Overwrite user info | `/manage` → "Edit User Info" | Replaces your stored biographical info |

### 6.3 Request manual deletion

If you need data deleted that isn't covered by the commands above, contact us via the support server.

### 6.4 Object to processing

If you do not want your data processed by the LLM, do not use the chat features.

---

## 7. AI-generated content disclaimer

AI responses are generated by Google's Gemini model and may be inaccurate, misleading, or inappropriate. Songbird is an entertainment bot that roleplays a fictional character — AI output should not be taken as factual. No AI output constitutes advice (legal, medical, financial, or otherwise).

---

## 8. Children's privacy

Songbird is not directed at children under 13. If you are under 13, do not use the bot. If we learn that we have collected data from a user under 13, we will delete it.

---

## 9. Changes to this policy

If this policy changes, the "Last updated" date at the top will be revised. Continued use after changes constitutes acceptance of the updated policy.

---

## 10. Contact

For privacy-related inquiries, join the support server or DM the bot owner on Discord.
