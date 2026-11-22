"""structlog setup, level filtering, error enrichment and the logger helper."""

import io
import logging
import sys
from collections.abc import Iterator

import pytest
import structlog

from songbird.utils.logging import _enrich_error, get_logger, setup_logging  # pyright: ignore[reportPrivateUsage]


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()
    logging.getLogger().setLevel(logging.WARNING)


def _capture(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    return stream


def test_setup_logging_configures_structlog(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture(monkeypatch)

    setup_logging("INFO")

    assert structlog.is_configured()


def test_info_level_filters_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _capture(monkeypatch)
    logger = setup_logging("INFO")

    logger.debug("hidden-debug-event")
    logger.info("visible-info-event")

    output = stream.getvalue()
    assert "visible-info-event" in output
    assert "hidden-debug-event" not in output


def test_debug_level_emits_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _capture(monkeypatch)
    logger = setup_logging("debug")

    logger.debug("visible-debug-event")

    assert "visible-debug-event" in stream.getvalue()


def test_unknown_level_falls_back_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _capture(monkeypatch)
    logger = setup_logging("NOT-A-LEVEL")

    logger.debug("hidden-debug-event")
    logger.info("visible-info-event")

    output = stream.getvalue()
    assert "visible-info-event" in output
    assert "hidden-debug-event" not in output


def test_repeated_setup_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _capture(monkeypatch)

    setup_logging("INFO")
    logger = setup_logging("INFO")

    logger.info("one-event")

    assert stream.getvalue().count("one-event") == 1
    assert structlog.is_configured()


def test_get_logger_does_not_change_configuration() -> None:
    before = structlog.get_config()

    logger = get_logger("songbird.tests")

    assert logger is not None
    assert structlog.get_config() == before


def test_error_is_enriched_with_type_and_transport_fields() -> None:
    class _Error(Exception):
        status = 500
        code = 40001
        text = "boom"

    event = _enrich_error(None, "error", {"error": _Error("bad")})

    assert event["error"] == "bad"
    assert event["error_type"] == "_Error"
    assert event["error_status"] == 500
    assert event["error_code"] == 40001
    assert event["error_text"] == "boom"


def test_non_exception_error_is_untouched() -> None:
    event = _enrich_error(None, "error", {"error": "already text"})

    assert event == {"error": "already text"}


def test_plain_exception_only_gets_type() -> None:
    event = _enrich_error(None, "error", {"error": RuntimeError("plain")})

    assert event == {"error": "plain", "error_type": "RuntimeError"}
