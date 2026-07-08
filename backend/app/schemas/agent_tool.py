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
