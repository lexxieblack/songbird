"""Order-dependent on purpose: pytest keeps definition order within a file.

``test_populates_caches`` dirties the module-level caches, and
``test_caches_are_empty_at_start`` is the assertion that the autouse
``_reset_module_state`` teardown cleared them again.
"""

from songbird.listeners import blackwall, link_fixer
from songbird.utils import prompts


def test_populates_caches() -> None:
    prompts._prompt_cache["sentinel"] = "value"
    link_fixer.CACHED_MESSAGES.add(1)
    blackwall._warn_cooldown[(1, 2)] = True

    assert prompts._prompt_cache
    assert link_fixer.CACHED_MESSAGES
    assert blackwall._warn_cooldown


def test_caches_are_empty_at_start() -> None:
    assert not prompts._prompt_cache
    assert not link_fixer.CACHED_MESSAGES
    assert not blackwall._warn_cooldown
