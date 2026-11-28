import asyncio
import contextlib

from discord import AllowedMentions, Forbidden, HTTPException, Message, TextChannel, Thread

from songbird.bot import SongbirdBot
from songbird.config import LinksSettings
from songbird.ui.views.link_fixer import RestoreLinkView
from songbird.utils.logging import get_logger
from songbird.utils.text import link
from songbird.utils.urls import domain_of, extract_urls

logger = get_logger(__name__)


CACHED_MESSAGES: set[int] = set()


def load_fix(bot: SongbirdBot) -> None:
    settings = bot.settings
    services = bot.services

    @bot.listen()
    async def on_message_edit(before: Message, after: Message) -> None:
        # suppress_embeds edits do not change the content; only real user edits get handled.
        if before.content == after.content or before.id not in CACHED_MESSAGES:
            return

        CACHED_MESSAGES.discard(before.id)
        with contextlib.suppress(HTTPException):
            await after.edit(suppress_embeds=True)

    @bot.listen()
    async def on_message(message: Message) -> None:
        if message.author.bot or not message.content:
            return

        is_valid_type = isinstance(message.channel, (TextChannel, Thread))

        if not is_valid_type:
            return

        urls = extract_urls(message.content)

        if not urls:
            return

        fixed_urls: list[str] = []
        links_settings = settings.links
        fixable = [url for url in urls if _check_domain_setting(url, links_settings)]
        for fixed in await asyncio.gather(*(services.link_fixer.fix(url) for url in fixable)):
            fixed_urls.extend(fixed)

        if not fixed_urls:
            return

        CACHED_MESSAGES.add(message.id)
        try:
            await message.edit(suppress_embeds=True)
        except Forbidden:
            with contextlib.suppress(HTTPException):
                await message.channel.send(
                    (
                        "I couldn't remove the original message's link embed due to a missing permission.\n"
                        "Missing 'Manage Messages' permission or my role isn't above the message's author's role.\n"
                        "-# *This message will be deleted after 10 seconds.*"
                    ),
                    delete_after=10,
                    reference=message,
                    allowed_mentions=AllowedMentions.none(),
                )
        except HTTPException:
            pass

        sent_messages: list[Message] = []
        first_url, *rest_urls = fixed_urls
        sent_messages.append(
            await message.channel.send(
                link(domain_of(first_url), first_url),
                reference=message,
                view=RestoreLinkView(message, CACHED_MESSAGES, sent_messages),
                allowed_mentions=AllowedMentions.none(),
            )
        )

        for url in rest_urls:
            sent_messages.append(
                await message.channel.send(
                    link(domain_of(url), url),
                    reference=message,
                    allowed_mentions=AllowedMentions.none(),
                )
            )


def unload_fix() -> None:
    CACHED_MESSAGES.clear()
    logger.info("Link fixer unloaded")


def _check_domain_setting(url: str, links_settings: LinksSettings) -> bool:
    domain = domain_of(url)
    mapping = links_settings.root.get(domain)
    if mapping is None:
        return False
    return mapping.chat is True
