from datetime import timedelta

import pytest
from discord import File

from songbird.utils.text import (
    escape_markdown,
    format_code_block,
    get_codeblock_language,
    humanize_timedelta,
    is_codeblock,
    link,
    sanitize_mentions,
    split_message,
    split_paragraph_to_sentences,
    split_sentence,
    split_text_to_paragraphs,
    truncate_text,
)


@pytest.mark.parametrize(
    ("text", "max_length", "suffix", "expected"),
    [
        ("", 5, "...", ""),
        ("abc", 3, "...", "abc"),
        ("abcdef", 6, "...", "abcdef"),
        ("abcdefg", 6, "...", "abc..."),
        ("abcdefg", 3, "...", "..."),
        ("abcdef", 4, "…", "abc…"),
    ],
)
def test_truncate_text(text: str, max_length: int, suffix: str, expected: str) -> None:
    assert truncate_text(text, max_length, suffix) == expected


def test_truncate_text_rejects_max_shorter_than_suffix() -> None:
    with pytest.raises(ValueError, match=r"max_length \(2\) must be at least"):
        truncate_text("abc", 2)


def test_truncate_text_short_circuits_empty_before_validating_suffix() -> None:
    assert truncate_text("", 0) == ""


def test_sanitize_mentions_leaves_empty_text() -> None:
    assert sanitize_mentions("") == ""


def test_sanitize_mentions_neutralizes_pings() -> None:
    assert sanitize_mentions("@everyone @here <@123> <@!456>") == "@\u200beveryone @\u200bhere <@\u200b123> <@\u200b!456>"


@pytest.mark.parametrize(
    ("code", "language", "expected"),
    [
        ("", "", "```\n\n```"),
        ("", "python", "```python\n\n```"),
        ("print(1)", "", "```\nprint(1)\n```"),
        ("print(1)", "python", "```python\nprint(1)\n```"),
    ],
)
def test_format_code_block(code: str, language: str, expected: str) -> None:
    assert format_code_block(code, language) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("plain text", "plain text"),
        ("*bold*", r"\*bold\*"),
        ("_italic_", r"\_italic\_"),
        ("~~strike~~", r"\~\~strike\~\~"),
        ("`code`", r"\`code\`"),
        ("a|b", r"a\|b"),
        ("> quote", r"\> quote"),
        ("# heading", r"\# heading"),
    ],
)
def test_escape_markdown(text: str, expected: str) -> None:
    assert escape_markdown(text) == expected


def test_link() -> None:
    assert link("Songbird", "https://example.com") == "[Songbird](https://example.com)"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("```", True),
        ("```python\nx = 1\n```", True),
        ("```python\nx = 1", False),
        ("before ```\nafter", False),
        ("", False),
    ],
)
def test_is_codeblock(text: str, expected: bool) -> None:
    assert is_codeblock(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("```python\nx = 1\n```", "python"),
        ("```py\nx = 1\n```", "py"),
        ("```\nx = 1\n```", ""),
        ("```", ""),
        ("not a codeblock", ""),
    ],
)
def test_get_codeblock_language(text: str, expected: str) -> None:
    assert get_codeblock_language(text) == expected


def test_split_sentence_returns_short_text_whole() -> None:
    assert split_sentence("hello world", 100) == ["hello world"]


def test_split_sentence_splits_on_word_boundaries_and_keeps_words() -> None:
    chunks = split_sentence("hello world this is a test", 10)

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)
    assert all(len(chunk.strip()) <= 10 for chunk in chunks)
    assert "".join(chunks).split() == ["hello", "world", "this", "is", "a", "test"]


def test_split_paragraph_to_sentences_preserves_the_sentence_text() -> None:
    chunks = split_paragraph_to_sentences("First sentence. Second sentence!", max_length=200)

    assert len(chunks) == 1
    assert chunks[0].split() == ["First", "sentence", ".", "Second", "sentence!"]


def test_split_text_to_paragraphs_returns_empty_list_for_empty_text() -> None:
    assert split_text_to_paragraphs("") == []


def test_split_text_to_paragraphs_keeps_short_paragraphs_together() -> None:
    assert split_text_to_paragraphs("one\n\ntwo\n\nthree", max_length=50) == ["one\n\ntwo\n\nthree"]


def test_split_text_to_paragraphs_splits_when_over_the_limit() -> None:
    assert split_text_to_paragraphs("one\n\ntwo", max_length=5) == ["one", "two"]


def test_split_message_empty_text() -> None:
    assert split_message("") == [""]


def test_split_message_keeps_short_plain_text_whole() -> None:
    assert split_message("hello world") == ["hello world"]


def test_split_message_keeps_paragraphs_that_fit() -> None:
    assert split_message("one\n\ntwo\n\nthree") == ["one\n\ntwo\n\nthree"]


def test_split_message_keeps_small_codeblock_once() -> None:
    assert split_message("```python\nx = 1\n```") == ["```python\nx = 1\n```"]


def test_split_message_attaches_large_codeblocks_as_files() -> None:
    code = "\n".join(str(number) for number in range(10))

    chunks = split_message(f"```\n{code}\n```")
    files = [chunk for chunk in chunks if isinstance(chunk, File)]

    assert files
    for file in files:
        filename = file.filename
        assert filename is not None
        assert filename.startswith("codeblock.")


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(0), "just now"),
        (timedelta(seconds=1), "1 second"),
        (timedelta(seconds=59, microseconds=900_000), "59 seconds"),
        (timedelta(minutes=1), "1 minute"),
        (timedelta(seconds=61), "1 minute"),
        (timedelta(hours=1, minutes=2, seconds=3), "1 hour, 2 minutes"),
        (timedelta(days=1), "1 day"),
        (timedelta(days=31), "1 month, 1 day"),
        (timedelta(days=365), "1 year"),
        (timedelta(days=400), "1 year, 1 month, 5 days"),
        (timedelta(days=730), "2 years"),
        (timedelta(days=-1), "-1 day"),
        (timedelta(days=-2, seconds=86_395), "-1 day"),
    ],
)
def test_humanize_timedelta(delta: timedelta, expected: str) -> None:
    assert humanize_timedelta(delta) == expected
