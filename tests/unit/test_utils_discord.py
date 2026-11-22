from songbird.utils.discord import create_file_text


def test_create_file_text_uses_the_default_name() -> None:
    file = create_file_text("hello")

    assert file.filename == "file.txt"


def test_create_file_text_uses_a_custom_name_and_utf8_content() -> None:
    file = create_file_text("héllo ❌", "note.md")
    fp = file.fp

    assert file.filename == "note.md"
    assert fp is not None
    assert fp.read() == "héllo ❌".encode()
