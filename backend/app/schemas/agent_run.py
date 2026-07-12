from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunCreateRequest(BaseModel):
    # A task may analyze a market, sector, or research question without a single-stock target.
    symbol: str = Field(default="", max_length=40)
    query: str = ""
    mode: str = "analysis"
    agent_keys: list[str] = Field(default_factory=list)
    variables: dict[str, str] = Field(default_factory=dict)
    period: str = "daily"
    limit: int = Field(default=60, ge=1, le=800)
    include_report: bool = False


class AgentRunStep(BaseModel):
    agent_key: str
    agent_name: str
    tool_key: str
    status: str
    params: dict[str, Any] = Field(default_factory=dict)
    output_preview: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class AgentRunRead(BaseModel):
    id: int
    run_key: str
    symbol: str
    query: str
    mode: str
    status: str
    snapshot_id: int = 0
    agent_keys: list[str]
    steps: list[AgentRunStep]
    result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentRunListResponse(BaseModel):
    items: list[AgentRunRead]
