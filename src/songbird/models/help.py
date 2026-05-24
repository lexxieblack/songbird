from pydantic import BaseModel


class HelpCommandEntry(BaseModel):
    key: str
    label: str
    emoji: str | None = None
    description: str
    short_description: str
