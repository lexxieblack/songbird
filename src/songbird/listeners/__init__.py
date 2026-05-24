from songbird.bot import SongbirdBot
from songbird.listeners.chat import load_chat
from songbird.listeners.link_fixer import load_fix, unload_fix


def load_listeners(bot: SongbirdBot) -> None:
    load_chat(bot)
    load_fix(bot)


def unload_listeners() -> None:
    unload_fix()
