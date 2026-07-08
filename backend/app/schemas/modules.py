from pydantic import BaseModel


class ModuleItem(BaseModel):
    key: str
    name: str
    status: str


class ModuleListResponse(BaseModel):
    items: list[ModuleItem]

