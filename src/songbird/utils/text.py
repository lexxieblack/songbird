import re

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

    for paragraph in paragraphs:
        if len(paragraph) < max_length:
            chunks.append(paragraph)
        else:
            paragraphs = split_paragraph_to_sentences(paragraph, max_length)
            chunks.extend(paragraphs)

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
                lang = get_codeblock_language(raw_chunk)
                final_chunks.append(create_file_text(raw_chunk, f"codeblock.{lang}"))
            else:
                final_chunks.append(raw_chunk)
        else:
            paragraphs = split_text_to_paragraphs(raw_chunk, max_length=max_text_length)
            final_chunks.extend(paragraphs)

    return final_chunks
