from types import SimpleNamespace
from typing import Any

import pytest

from songbird.bot import SongbirdBot
from songbird.config import Settings


@pytest.fixture
def bot(settings: Settings) -> SongbirdBot:
    services: Any = SimpleNamespace(management=None)
    return SongbirdBot(settings, services)
