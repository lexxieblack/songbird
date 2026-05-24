from pydantic import BaseModel


class BaseDBModel(BaseModel):
    class Config:
        from_attributes = True
