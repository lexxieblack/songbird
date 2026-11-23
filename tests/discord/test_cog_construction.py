"""Each registered extension imports and its cog constructs against a fake bot."""

import importlib

import pytest
from discord.ext import commands

from songbird.bot import SongbirdBot
from songbird.cogs import EXTENSIONS
from songbird.cogs.base import BaseCog

pytestmark = pytest.mark.discord


def _cogs(bot: SongbirdBot) -> list[object]:
    # FakeBot stores cogs in a list; SongbirdBot annotates a dict.
    cogs: list[object] = vars(bot)["cogs"]
    return cogs


@pytest.mark.parametrize("extension", EXTENSIONS)
def test_extension_setup_constructs_one_cog(extension: str, fake_bot: SongbirdBot) -> None:
    module = importlib.import_module(extension)
    module.setup(fake_bot)

    cogs = _cogs(fake_bot)
    assert len(cogs) == 1
    assert isinstance(cogs[0], BaseCog)


def test_extension_list_is_not_empty() -> None:
    assert EXTENSIONS


@pytest.mark.parametrize("extension", EXTENSIONS)
def test_cogs_are_cog_subclasses(extension: str, fake_bot: SongbirdBot) -> None:
    module = importlib.import_module(extension)
    module.setup(fake_bot)

    assert isinstance(_cogs(fake_bot)[0], commands.Cog)


@pytest.mark.parametrize("extension", EXTENSIONS)
def test_every_command_runs_under_the_ban_hook(extension: str, fake_bot: SongbirdBot) -> None:
    module = importlib.import_module(extension)
    module.setup(fake_bot)

    cog = _cogs(fake_bot)[0]
    assert isinstance(cog, BaseCog)
    assert list(cog.get_commands())  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType] # every extension registers something
    # No cog may shadow the base hook, or its commands would skip the ban check.
    assert type(cog).cog_before_invoke is BaseCog.cog_before_invoke
