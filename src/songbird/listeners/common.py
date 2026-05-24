from discord import AllowedMentions, Webhook
from discord.abc import Messageable

from songbird.utils.text import split_message


async def send_messages(channel: Messageable | Webhook, message: str) -> None:
    messages = split_message(message)
    for msg in messages:
        if isinstance(msg, str):
            await channel.send(msg, allowed_mentions=AllowedMentions.none())
        else:
            await channel.send(file=msg, allowed_mentions=AllowedMentions.none())
