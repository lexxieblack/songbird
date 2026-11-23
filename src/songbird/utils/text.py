import re
from datetime import timedelta

from discord import File

from songbird.utils.discord import create_file_text


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    if not text:
        return text

    if max_length < len(suffix):
        raise ValueError(f"max_length ({max_length}) must be at least the length of suffix ({len(suffix)})")

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def sanitize_mentions(text: str) -> str:
    if not text:
        return text

    # Replace @everyone and @here with zero-width space to prevent pings
    text = text.replace("@everyone", "@\u200beveryone")
    text = text.replace("@here", "@\u200bhere")

    # Escape user mention patterns <@userid> and <@!userid>
    text = re.sub(r"<@(!?)(\d+)>", lambda match: f"<@\u200b{match.group(1)}{match.group(2)}>", text)

    return text


def format_code_block(code: str, language: str = "") -> str:
    if not code:
        return f"```{language}\n\n```"

    return f"```{language}\n{code}\n```"


def escape_markdown(text: str) -> str:
    if not text:
        return text

    # Characters that need to be escaped in Discord markdown
    markdown_chars = ["*", "_", "~", "`", "|", ">", "#"]

    for char in markdown_chars:
        text = text.replace(char, f"\\{char}")

    return text


def link(text: str, url: str) -> str:
    return f"[{text}]({url})"


def is_codeblock(text: str) -> bool:
    return text.startswith("```") and text.endswith("```")


def get_codeblock_language(text: str) -> str:
    if not is_codeblock(text):
        return ""

    return text[3 : text.find("\n")].strip()


_CODEBLOCK_RE = re.compile(r"(?s)(```[\s\S]*?```)")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# Real file extensions, so the attached code gets syntax highlighting.
_CODE_FILE_EXTENSIONS = {
    "python": "py",
    "py": "py",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "ts": "ts",
    "tsx": "tsx",
    "jsx": "jsx",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "sql": "sql",
    "bash": "sh",
    "sh": "sh",
    "zsh": "sh",
    "html": "html",
    "css": "css",
    "rust": "rs",
    "go": "go",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "csharp": "cs",
    "cs": "cs",
    "ruby": "rb",
    "rb": "rb",
    "php": "php",
    "markdown": "md",
    "md": "md",
    "diff": "diff",
    "xml": "xml",
}


def _hard_split(text: str, limit: int) -> list[str]:
    """Cut text longer than `limit`, preferring a newline break, then a space, then a hard cut."""
    pieces: list[str] = []
    while len(text) > limit:
        cut = max(text.rfind("\n", 0, limit + 1), text.rfind(" ", 0, limit + 1))
        cut = cut if cut > 0 else limit
        piece = text[:cut].rstrip()
        if piece:
            pieces.append(piece)
        text = text[cut:].lstrip()
    if text:
        pieces.append(text)
    return pieces


def _pack(units: list[str], limit: int, separator: str) -> list[str]:
    """Greedily join units into chunks of at most `limit` chars, splitting over-long units."""
    chunks: list[str] = []
    current = ""
    for unit in units:
        for piece in _hard_split(unit, limit):
            candidate = f"{current}{separator}{piece}" if current else piece
            if len(candidate) > limit:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def split_sentence(text: str, max_length: int = 2000) -> list[str]:
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    return _pack(text.split(), max_length, " ")


def split_paragraph_to_sentences(text: str, max_length: int = 2000) -> list[str]:
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    return _pack(_SENTENCE_END_RE.split(text), max_length, " ")


def split_text_to_paragraphs(text: str, max_length: int = 2000) -> list[str]:
    chunks: list[str] = []
    current_chunk = ""

    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            chunks.extend(split_paragraph_to_sentences(paragraph, max_length))
            continue

        candidate = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph
        if len(candidate) > max_length:
            chunks.append(current_chunk)
            current_chunk = paragraph
        else:
            current_chunk = candidate

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def split_message(
    text: str,
    max_text_length: int = 2000,
    max_codeblock_length: int = 200,
    max_codeblock_lines: int = 5,
) -> list[str | File]:
    if not text or not text.strip():
        return []

    final_chunks: list[str | File] = []

    # Code blocks are sent on their own: as a message when small, as a file when large.
    for raw_chunk in _CODEBLOCK_RE.split(text):
        raw_chunk = raw_chunk.strip()
        if not raw_chunk:
            continue

        if is_codeblock(raw_chunk):
            if raw_chunk.count("\n") > max_codeblock_lines or len(raw_chunk) > max_codeblock_length:
                language = get_codeblock_language(raw_chunk).lower()
                extension = _CODE_FILE_EXTENSIONS.get(language, language or "txt")
                final_chunks.append(create_file_text(raw_chunk, f"codeblock.{extension}"))
            else:
                final_chunks.append(raw_chunk)
        else:
            final_chunks.extend(split_text_to_paragraphs(raw_chunk, max_length=max_text_length))

    return final_chunks


def humanize_timedelta(td: timedelta) -> str:
    """Convert a timedelta into a short human-readable string like '5 years, 3 days'."""
    total_seconds = int(td.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)

    days, seconds = divmod(total_seconds, 86400)
    years, days = divmod(days, 365)
    months, days = divmod(days, 30)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts: list[str] = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds and not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return sign + ", ".join(parts) if parts else "just now"
