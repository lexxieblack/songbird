from pydantic import BaseModel


class CategoryDef(BaseModel):
    label: str
    emoji: str
    description: str


class HelpCommandEntry(BaseModel):
    key: str
    label: str
    emoji: str | None = None
    description: str
    short_description: str
    category: str
