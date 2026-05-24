from pydantic import BaseModel


class ConversationContext(BaseModel):
    username: str
    display_name: str
    guild_name: str | None = None
    channel_name: str | None = None
