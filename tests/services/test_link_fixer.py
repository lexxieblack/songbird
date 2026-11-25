from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import httpx
import pytest

from songbird.config import Settings
from songbird.services import link_fixer as link_fixer_module
from songbird.services.link_fixer import LinkFixerService


def _settings(links: dict[str, Any]) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "DISCORD_TOKEN": "test-token",
        "bot": {},
        "blackwall": {},
        "db": {"url": "postgresql+psycopg://test:test@localhost:5432/test"},
        "llm": {"api_key": "test-llm-key"},
        "wolfram": {"api_key": "test-wolfram-key"},
        "links": links,
    }
    return Settings(**values)


def _fake_extract(url: str) -> SimpleNamespace:
    host = urlparse(url).hostname or ""
    domain, _, suffix = host.rpartition(".")
    domain = domain.rpartition(".")[2]
    return SimpleNamespace(domain=domain, suffix=suffix)


@pytest.fixture(autouse=True)
def _offline_tldextract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(link_fixer_module, "_EXTRACT", _fake_extract)


class _Response:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        data: Any = None,
        error: Exception | None = None,
    ) -> None:
        self.headers = httpx.Headers(headers or {})
        self._data = data
        self._error = error

    def json(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._data


class _Client:
    def __init__(
        self,
        *,
        location: str | None = None,
        head_error: Exception | None = None,
        media: Any = None,
        media_error: Exception | None = None,
    ) -> None:
        self.location = location
        self.head_error = head_error
        self.media = media
        self.media_error = media_error
        self.head_calls: list[str] = []
        self.get_calls: list[str] = []
        self.closed = False

    async def head(self, url: str, **_kwargs: Any) -> _Response:
        self.head_calls.append(url)
        if self.head_error is not None:
            raise self.head_error
        return _Response(headers={"Location": self.location} if self.location else {})

    async def get(self, url: str, **_kwargs: Any) -> _Response:
        self.get_calls.append(url)
        return _Response(data=self.media, error=self.media_error)

    async def aclose(self) -> None:
        self.closed = True


def _install_client(monkeypatch: pytest.MonkeyPatch, client: _Client) -> _Client:
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: client)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    return client


async def test_text_without_url_is_returned_unchanged() -> None:
    service = LinkFixerService(_settings({}))

    assert await service.fix("no links here") == ["no links here"]


async def test_every_url_in_the_text_is_fixed() -> None:
    # Regression: only the first URL was extracted, so /fix silently ignored the rest.
    service = LinkFixerService(_settings({"twitter.com": {"swap": "fxtwitter.com"}}))

    assert await service.fix("a https://twitter.com/u/status/1 b https://twitter.com/u/status/2") == [
        "https://fxtwitter.com/u/status/1",
        "https://fxtwitter.com/u/status/2",
    ]


async def test_unknown_domain_without_wildcard_returns_url() -> None:
    service = LinkFixerService(_settings({}))

    assert await service.fix("look https://unknown.example/abc") == ["https://unknown.example/abc"]


async def test_wildcard_clean_keeps_only_exceptions() -> None:
    service = LinkFixerService(_settings({"*": {"clean": True, "clean_exceptions": ["id"]}}))

    assert await service.fix("https://unknown.example/abc?utm=1&id=7") == ["https://unknown.example/abc?id=7"]


async def test_clean_without_exceptions_strips_query() -> None:
    service = LinkFixerService(_settings({"example.com": {"clean": True}}))

    assert await service.fix("https://example.com/abc?utm=1&id=7") == ["https://example.com/abc"]


async def test_swap_replaces_domain() -> None:
    service = LinkFixerService(_settings({"twitter.com": {"swap": "fxtwitter.com"}}))

    assert await service.fix("https://twitter.com/user/status/1") == ["https://fxtwitter.com/user/status/1"]


async def test_swap_with_multi_dot_target_drops_www() -> None:
    service = LinkFixerService(_settings({"twitter.com": {"swap": "www.fxtwitter.com"}}))

    assert await service.fix("https://www.twitter.com/user/status/1") == ["https://www.fxtwitter.com/user/status/1"]


async def test_follow_uses_redirect_location(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_client(monkeypatch, _Client(location="https://example.com/final"))
    service = LinkFixerService(_settings({"example.com": {"follow": True}}))

    assert await service.fix("https://example.com/start") == ["https://example.com/final"]
    assert client.head_calls == ["https://example.com/start"]


async def test_close_closes_the_shared_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_client(monkeypatch, _Client())
    service = LinkFixerService(_settings({}))

    await service.close()

    assert client.closed


async def test_follow_failure_keeps_original_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_client(monkeypatch, _Client(head_error=httpx.ConnectError("blocked")))
    service = LinkFixerService(_settings({"example.com": {"follow": True}}))

    assert await service.fix("https://example.com/start") == ["https://example.com/start"]


async def test_pagination_builds_page_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _install_client(monkeypatch, _Client(media={"media_extended": [1, 2, 3, 4, 5]}))
    service = LinkFixerService(_settings({"example.com": {"pagination": {"per_page": 2, "format": "{url}?page={page}"}}}))

    assert await service.fix("https://example.com/gallery") == [
        "https://example.com/gallery",
        "https://example.com/gallery?page=2",
        "https://example.com/gallery?page=3",
    ]
    assert session.get_calls == ["https://api.example.com/gallery"]


async def test_pagination_under_one_page_returns_single_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_client(monkeypatch, _Client(media={"mediaURLs": [1]}))
    service = LinkFixerService(_settings({"example.com": {"pagination": {"per_page": 10}}}))

    assert await service.fix("https://example.com/gallery") == ["https://example.com/gallery"]


async def test_pagination_caps_at_ten_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_client(monkeypatch, _Client(media={"media_extended": list(range(100))}))
    service = LinkFixerService(_settings({"example.com": {"pagination": {"per_page": 10, "format": "{url}/{page}"}}}))

    urls = await service.fix("https://example.com/gallery")

    assert len(urls) == 10
    assert urls[-1] == "https://example.com/gallery/10"


async def test_pagination_skips_fetch_when_page_suffix_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _install_client(monkeypatch, _Client(media={"media_extended": [1, 2, 3]}))
    service = LinkFixerService(_settings({"example.com": {"pagination": {"per_page": 1}}}))
    url = "https://example.com/status/123/2"

    assert await service.fix(url) == [url]
    assert session.get_calls == []


@pytest.mark.parametrize(
    "session",
    [
        _Client(media=["not", "a", "dict"]),
        _Client(media_error=httpx.ConnectError("down")),
    ],
)
async def test_media_count_failure_returns_single_url(monkeypatch: pytest.MonkeyPatch, session: _Client) -> None:
    _install_client(monkeypatch, session)
    service = LinkFixerService(_settings({"example.com": {"pagination": {"per_page": 1}}}))

    assert await service.fix("https://example.com/gallery") == ["https://example.com/gallery"]
