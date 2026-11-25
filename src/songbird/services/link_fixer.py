import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import tldextract
from structlog import BoundLogger

from songbird.config import PaginationSettings, Settings
from songbird.utils.logging import get_logger

# Empty suffix_list_urls: use the bundled snapshot and never fetch the list on the event loop.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


class LinkFixerService:
    def __init__(
        self,
        settings: Settings,
        logger: BoundLogger | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger or get_logger(__name__)
        self.domain_mapping = self.settings.links
        # One client for the process: a session per URL paid a fresh TLS handshake every time.
        self._client = httpx.AsyncClient(timeout=5.0, follow_redirects=False)

    async def close(self) -> None:
        await self._client.aclose()

    async def fix(self, text: str) -> list[str]:
        urls = self._extract_urls(text)
        if not urls:
            return [text]

        fixed: list[str] = []
        for url in urls:
            fixed.extend(await self._fix_url(url))
        return fixed

    async def _fix_url(self, url: str) -> list[str]:
        domain = self._get_domain_suffix(url)
        rules = self.domain_mapping.root.get(domain)
        if not rules:
            if not self._wildcard_exists():
                return [url]
            rules = self.domain_mapping.root.get("*")

        if not rules:
            return [url]

        if rules.follow:
            url = await self._follow_url(url)

        if rules.swap:
            url = self._swap_url(url, domain, rules.swap)

        if rules.clean:
            url = self._clean_url(url, rules.clean_exceptions)

        if rules.pagination and not self._has_page_suffix(url):
            count = await self._media_count(url, rules.pagination)
            return self._page_urls(url, count, rules.pagination)

        return [url]

    def _get_domain_suffix(self, url: str) -> str:
        ext = _EXTRACT(url)
        return f"{ext.domain}.{ext.suffix}"

    async def _follow_url(self, url: str) -> str:
        try:
            response = await self._client.head(url)
            location = response.headers.get("location")
            return location if isinstance(location, str) else url
        except httpx.HTTPError as e:
            self.logger.error("Failed to follow link", url=url, error=e)
            return url

    async def _media_count(self, url: str, pagination: PaginationSettings) -> int:
        parsed = urlparse(url)
        # shortcut: assumes the fixer service exposes an api.<host> media endpoint; add an explicit `api` key when a second provider needs one
        api = pagination.api or f"https://api.{parsed.hostname}{parsed.path}"
        try:
            response = await self._client.get(api)
            data = response.json()
            if not isinstance(data, dict):
                return 0
            return len(data.get("media_extended") or data.get("mediaURLs") or [])
        except (httpx.HTTPError, ValueError) as e:
            self.logger.error("Failed to fetch media count", url=url, error=e)
            return 0

    def _page_urls(self, url: str, count: int, pagination: PaginationSettings) -> list[str]:
        if count <= pagination.per_page:
            return [url]
        # cap keeps a huge gallery from flooding the channel with messages
        pages = min(-(-count // pagination.per_page), 10)
        return [url] + [pagination.format.format(url=url, page=page) for page in range(2, pages + 1)]

    def _has_page_suffix(self, url: str) -> bool:
        segments = urlparse(url).path.strip("/").split("/")
        return "status" in segments and segments.index("status") + 2 < len(segments)

    def _swap_url(self, url: str, domain: str, swap: str) -> str:
        if swap.count(".") > 1:
            url = url.replace("www.", "")
        return url.replace(domain, swap, 1)

    def _clean_url(self, url: str, query_exceptions: list[str] | None = None) -> str:
        if not query_exceptions:
            query_exceptions = []

        parsed = urlparse(url)
        query_pairs = parse_qsl(parsed.query)
        cleaned_pairs = [(k, v) for k, v in query_pairs if k in query_exceptions]
        new_query = urlencode(cleaned_pairs)
        cleaned_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

        return cleaned_url

    def _wildcard_exists(self) -> bool:
        return self.domain_mapping.root.get("*") is not None

    def _extract_urls(self, text: str) -> list[str]:
        return re.findall(r"https?://[^\s]+", text)
