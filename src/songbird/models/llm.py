from pydantic import BaseModel

from songbird.models.chat.guild_message import GuildMessage
from songbird.models.chat.message import Message


class LLMRequest(BaseModel):
    system_prompt: str | None = None
    user_prompt: str
    context_messages: list[Message] | list[GuildMessage] | None = None
