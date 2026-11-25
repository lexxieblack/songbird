"""The autouse guard blocks real traffic without breaking respx mocks."""

import httpx
import pytest
import respx
import tldextract

BLOCKED = "Outbound network access"


def test_sync_httpx_is_blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        httpx.get("https://example.com")


async def test_async_httpx_is_blocked() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match=BLOCKED):
            await client.get("https://example.com")


def test_tldextract_is_blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        tldextract.extract("https://example.com")


def test_respx_still_works(respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://example.com").mock(return_value=httpx.Response(200, text="ok"))

    assert httpx.get("https://example.com").text == "ok"
