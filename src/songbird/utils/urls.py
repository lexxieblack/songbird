import re

import tldextract

# Empty suffix_list_urls: use the bundled snapshot and never fetch the list on the event loop.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())

# Links wrapped in <> are intentionally embed-suppressed by the author.
_URL_PATTERN = r"(?<!<)https?://[^<>\s]+"


def extract_urls(text: str) -> list[str]:
    # Trailing sentence punctuation belongs to the prose, not the URL.
    return [url.rstrip(".,;:!?'\")]}") for url in re.findall(_URL_PATTERN, text)]


def domain_of(url: str) -> str:
    ext = _EXTRACT(url)
    return f"{ext.domain}.{ext.suffix}"
