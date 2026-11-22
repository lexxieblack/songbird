"""The extension registry stays flat and importable."""

from songbird.cogs import EXTENSIONS


def test_extensions_are_unique_songbird_cogs() -> None:
    assert len(EXTENSIONS) == len(set(EXTENSIONS))
    assert all(extension.startswith("songbird.cogs.") for extension in EXTENSIONS)
