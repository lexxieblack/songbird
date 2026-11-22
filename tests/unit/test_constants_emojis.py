from discord import Color

from songbird.utils.constants import SColor, Text
from songbird.utils.emojis import ARROW_LEFT, ARROW_RIGHT, WARNING_ONE, WARNING_TWO


def test_text_constants() -> None:
    assert Text.ZERO_WIDTH_SPACE == "\u200e"
    assert Text.EMOJI_X == "\N{CROSS MARK}"
    assert Text.EMOJI_CHECK == "\N{CHECK MARK}"


def test_brand_colors() -> None:
    assert SColor.SONGBIRD.value == 0xED1E79
    assert SColor.BLACKWALL.value == 0xFF0033
    assert Color(0xED1E79) == SColor.SONGBIRD
    assert Color(0xFF0033) == SColor.BLACKWALL


def test_custom_emojis() -> None:
    assert (ARROW_RIGHT.name, ARROW_RIGHT.id) == ("arrow_right", 1506347098843648120)
    assert (ARROW_LEFT.name, ARROW_LEFT.id) == ("arrow_left", 1506347097387958373)
    assert (WARNING_ONE.name, WARNING_ONE.id) == ("warning_1", 1542967885700399196)
    assert (WARNING_TWO.name, WARNING_TWO.id) == ("warning_2", 1542967871246696489)


def test_custom_emojis_render_and_are_not_animated() -> None:
    assert str(ARROW_RIGHT) == "<:arrow_right:1506347098843648120>"
    assert str(WARNING_ONE) == "<:warning_1:1542967885700399196>"
    assert ARROW_RIGHT.animated is False
