from pydantic import BaseModel


class CategoryDef(BaseModel):
    label: str
    emoji: str
    description: str
