from pydantic import BaseModel


class ConversationContext(BaseModel):
    user_id: int
    username: str
    display_name: str
    guild_name: str | None = None
    channel_name: str | None = None
