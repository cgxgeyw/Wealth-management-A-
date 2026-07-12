from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentToolSpec(BaseModel):
    key: str
    name: str
    description: str
    category: str
    enabled: bool = True
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class AgentToolListResponse(BaseModel):
    items: list[AgentToolSpec]


class AgentToolRunRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class AgentToolRunResponse(BaseModel):
    agent_key: str
    tool_key: str
    status: str
    output: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentToolAuditRead(BaseModel):
    tool_key: str
    total: int
    failures: int
    last_status: str
    last_error: str
    last_called_at: datetime | None


class AgentToolAuditListResponse(BaseModel):
    items: list[AgentToolAuditRead]
