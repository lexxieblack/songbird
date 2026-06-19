import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import tldextract
from aiohttp import ClientError, ClientSession, ClientTimeout
from structlog import BoundLogger

from songbird.config import Settings
from songbird.utils.logging import get_logger


class LinkFixerService:
    def __init__(
        self,
        settings: Settings,
        logger: BoundLogger | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logger or get_logger(__name__)
        self.domain_mapping = self.settings.links

    async def fix(self, text: str) -> str:
        url = self._extract_url(text)
        if not url:
            return text

        domain = self._get_domain_suffix(url)
        rules = self.domain_mapping.root.get(domain)
        if not rules:
            if not self._wildcard_exists():
                return url
            rules = self.domain_mapping.root.get("*")

        if not rules:
            return url

        if rules.follow:
            url = await self._follow_url(url)

        if rules.swap:
            url = self._swap_url(url, domain, rules.swap)

        if rules.clean:
            url = self._clean_url(url, rules.clean_exceptions)

        return url

    def _get_domain_suffix(self, url: str) -> str:
        ext = tldextract.extract(url)
        return f"{ext.domain}.{ext.suffix}"

    async def _follow_url(self, url: str) -> str:
        session = ClientSession(timeout=ClientTimeout(total=5))
        try:
            async with session.head(url, allow_redirects=False) as response:
                return response.headers.get("Location", url)
        except (TimeoutError, ClientError) as e:
            self.logger.error("Failed to follow link", url=url, error=e)
            return url
        finally:
            await session.close()

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

    def _extract_url(self, text: str) -> str | None:
        url_pattern = r"https?://[^\s]+"
        match = re.search(url_pattern, text)
        return match.group(0) if match else None
