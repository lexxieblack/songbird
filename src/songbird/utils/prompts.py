from datetime import datetime
from pathlib import Path

_prompt_cache: dict[str, str] = {}

DEFAULT_SYSTEM_PROMPT = """You are Songbird, a helpful and friendly Discord bot assistant.
You are talking over Discord messages.

You engage in natural conversations, answer questions, and help users with various tasks.
Be concise, accurate, and respectful in all interactions.

Guidelines:
- Keep responses clear and well-formatted for Discord
- Use markdown formatting where appropriate
- Be helpful and engaging without being overly verbose
- If you don't know something, say so honestly
"""


class SafeDict(dict[str, str]):
    """A way to safely add formatting if the key exists in the string."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_prompt(file_path: str | Path) -> str:
    path_str = str(Path(file_path).resolve())

    if path_str in _prompt_cache:
        return _prompt_cache[path_str]

    prompt_file = Path(file_path)
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")

    with open(prompt_file, encoding="utf-8") as f:
        prompt_text = f.read()

    _prompt_cache[path_str] = prompt_text
    return prompt_text


def get_system_prompt(config_path: str | None = None) -> str:
    now = datetime.now()
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    if config_path:
        try:
            base_prompt = load_prompt(config_path)
        except FileNotFoundError:
            base_prompt = DEFAULT_SYSTEM_PROMPT
    else:
        base_prompt = DEFAULT_SYSTEM_PROMPT

    format_data = {"datetime": datetime_str}

    formatted_prompt = base_prompt.format_map(SafeDict(format_data))
    return formatted_prompt


def build_user_context(
    user_id: int,
    username: str,
    guild_name: str | None = None,
    channel_name: str | None = None,
) -> str:
    context_parts = [
        f"User: {username} (ID: {user_id})",
    ]

    if guild_name:
        context_parts.append(f"Server: {guild_name}")
        if channel_name:
            context_parts.append(f"Server channel: {channel_name}")
        context_parts.append("Context: Guild/server conversation")
    else:
        context_parts.append("Context: Direct message (DM)")

    return "\n".join(context_parts)
