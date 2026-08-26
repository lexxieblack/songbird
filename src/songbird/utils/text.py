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
    text = re.sub(r"<@(!?)(\d+)>", r"<@\u200b\1\2>", text)

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


def split_sentence(text: str, max_length: int = 2000) -> list[str]:
    if len(text) < max_length:
        return [text]

    words = text.split()
    chunks: list[str] = []
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) > max_length:
            chunks.append(current_chunk)
            current_chunk = ""
        current_chunk += word + " "

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def split_paragraph_to_sentences(text: str, max_length: int = 2000) -> list[str]:
    sentences = re.split(r"([.!?])\s+", text)
    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        if len(sentence) > max_length:
            split_sentences = split_sentence(sentence, max_length)
            for s_sentence in split_sentences:
                if len(current_chunk) + len(s_sentence) > max_length:
                    chunks.append(current_chunk)
                    current_chunk = ""
                current_chunk += s_sentence + " "
        else:
            if len(current_chunk) + len(sentence) > max_length:
                chunks.append(current_chunk)
                current_chunk = ""
            current_chunk += sentence + " "

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def split_text_to_paragraphs(text: str, max_length: int = 2000) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(paragraph) >= max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            sentence_chunks = split_paragraph_to_sentences(paragraph, max_length)
            chunks.extend(sentence_chunks)
        elif current_chunk and len(current_chunk) + 2 + len(paragraph) > max_length:
            chunks.append(current_chunk)
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def split_message(
    text: str,
    max_text_length: int = 2000,
    max_codeblock_length: int = 200,
    max_codeblock_lines: int = 5,
) -> list[str | File]:
    if not text:
        return [""]

    final_chunks: list[str | File] = []

    # Split by code blocks while preserving the code blocks
    split_pattern = r"(?s)((```[\s\S]*?```))"
    raw_chunks = re.split(pattern=split_pattern, string=text)
    raw_chunks = [chunk.strip() for chunk in raw_chunks if chunk.strip()]

    for raw_chunk in raw_chunks:
        if is_codeblock(raw_chunk):
            codeblock_lines = raw_chunk.count("\n")
            if codeblock_lines > max_codeblock_lines or len(raw_chunk) > max_codeblock_length:
                lang = get_codeblock_language(raw_chunk) or "md"
                final_chunks.append(create_file_text(raw_chunk, f"codeblock.{lang}"))
            else:
                final_chunks.append(raw_chunk)
        else:
            paragraphs = split_text_to_paragraphs(raw_chunk, max_length=max_text_length)
            final_chunks.extend(paragraphs)

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
