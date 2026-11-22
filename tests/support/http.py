"""Autouse guard that fails loudly on real outbound network access."""

from typing import NoReturn

import aiohttp
import httpx
import pytest
from tldextract.tldextract import TLDExtract

MESSAGE = "Outbound network access attempted in a test. Use respx or monkeypatch the service."


def _blocked(*_args: object, **_kwargs: object) -> NoReturn:
    raise RuntimeError(MESSAGE)


async def _blocked_async(*_args: object, **_kwargs: object) -> NoReturn:
    raise RuntimeError(MESSAGE)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # respx defaults to the httpcore mocker, which patches *below* the httpx transports guarded here.
    # The httpx mocker swaps the client transport instead, so mocked requests never touch these patches.
    monkeypatch.setattr("respx.mocks.DEFAULT_MOCKER", "httpx")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _blocked_async)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", _blocked_async)
    monkeypatch.setattr(TLDExtract, "__call__", _blocked)
