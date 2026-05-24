import contextlib
import re

from discord import AllowedMentions, HTTPException, Message, TextChannel, Thread
from tldextract import tldextract

from songbird.bot import SongbirdBot
from songbird.config import LinksSettings
from songbird.ui.views.link_fixer import RestoreLinkView
from songbird.utils.logging import get_logger
from songbird.utils.text import link

logger = get_logger(__name__)


CACHED_MESSAGES = set()


def load_fix(bot: SongbirdBot) -> None:
    settings = bot.settings
    services = bot.services

    @bot.event
    async def on_message_edit(before: Message, after: Message) -> None:
        if before.id not in CACHED_MESSAGES:
            return

        CACHED_MESSAGES.discard(before.id)
        with contextlib.suppress(HTTPException):
            await after.edit(suppress=True)

    @bot.event
    async def on_message(message: Message) -> None:
        if message.author.bot or not message.content:
            return

        is_valid_type = isinstance(message.channel, (TextChannel, Thread))

        if not is_valid_type:
            return

        urls = _get_urls(message.content)

        if not urls:
            return

        fixed_urls = []
        links_settings = settings.links
        for url in urls:
            if not _check_domain_setting(url, links_settings):
                continue

            fixed_url = await services.link_fixer.fix(url)
            fixed_urls.append(fixed_url)

        if not fixed_urls:
            return

        CACHED_MESSAGES.add(message.id)
        with contextlib.suppress(HTTPException):
            await message.edit(suppress=True)

        links_to_send = []
        for url in fixed_urls:
            domain = _get_domain_with_suffix(url)
            links_to_send.append(link(domain, url))

        await message.reply(
            ", ".join(links_to_send), view=RestoreLinkView(message, CACHED_MESSAGES), allowed_mentions=AllowedMentions.none()
        )


def unload_fix() -> None:
    CACHED_MESSAGES.clear()
    logger.info("Link fixer unloaded")


def _get_urls(text: str) -> list[str]:
    url_pattern = r"https?://[^\s]+"
    return re.findall(url_pattern, text)


def _check_domain_setting(url: str, links_settings: LinksSettings) -> bool:
    domain = _get_domain_with_suffix(url)
    return links_settings.root.get(domain) is not None


def _get_domain_with_suffix(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"
