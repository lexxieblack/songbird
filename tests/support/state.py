from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _reset_module_state() -> Iterator[None]:
    yield
    from songbird.listeners import blackwall, link_fixer
    from songbird.utils import prompts

    prompts._prompt_cache.clear()  # pyright: ignore[reportPrivateUsage]
    link_fixer.CACHED_MESSAGES.clear()
    link_fixer.unload_fix()
    blackwall._warn_cooldown.clear()  # pyright: ignore[reportPrivateUsage]
