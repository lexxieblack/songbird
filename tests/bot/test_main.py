"""Import-level checks for the module entry point; the bot is never started."""

import inspect

from songbird import __main__ as entrypoint


def test_main_is_callable() -> None:
    assert callable(entrypoint.main)


def test_async_main_is_a_coroutine_function() -> None:
    assert inspect.iscoroutinefunction(entrypoint.async_main)


def test_module_does_not_run_main_on_import() -> None:
    # If importing ran main(), the process would have tried to configure and start the bot.
    assert entrypoint.__name__ == "songbird.__main__"
