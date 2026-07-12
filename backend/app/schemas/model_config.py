from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModelCapability = Literal["chat", "embedding", "rerank"]


class ModelConfigRead(BaseModel):
    id: int
    key: str
    name: str
    capability: ModelCapability
    model: str
    base_url: str
    api_key_configured: bool
    api_key_masked: str = ""
    timeout_seconds: int
    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelConfigListResponse(BaseModel):
    items: list[ModelConfigRead]


class ModelConfigCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=120)
    capability: ModelCapability
    model: str = Field(min_length=1, max_length=160)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = ""
    timeout_seconds: int = Field(default=45, ge=5, le=600)
    enabled: bool = True
    is_default: bool = False


class ModelConfigUpdateRequest(BaseModel):
    name: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=5, le=600)
    enabled: bool | None = None
    is_default: bool | None = None
