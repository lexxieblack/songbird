from songbird.bot import SongbirdBot
from songbird.listeners.chat import load_chat
from songbird.listeners.link_fixer import load_fix, unload_fix
from songbird.listeners.management import load_guild_ban_listener


def load_listeners(bot: SongbirdBot) -> None:
    load_chat(bot)
    load_fix(bot)
    load_guild_ban_listener(bot)


def unload_listeners() -> None:
    unload_fix()
