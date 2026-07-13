from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentChatMessage(BaseModel):
    role: str
    content: str


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str = Field(default="", max_length=80)
    symbol: str = ""
    variables: dict[str, str] = Field(default_factory=dict)
    history: list[AgentChatMessage] = Field(default_factory=list)
    max_tool_calls: int = Field(default=3, ge=0, le=8)


class AgentChatToolCall(BaseModel):
    tool_key: str
    status: str
    params: dict[str, Any] = Field(default_factory=dict)
    output_preview: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class AgentChatKnowledgeHit(BaseModel):
    citation: str
    title: str
    snippet: str
    score: float
    source: str = ""
    tags: list[str] = Field(default_factory=list)


class AgentChatTraceEvent(BaseModel):
    conversation_id: str
    turn_id: str
    agent_key: str
    event_type: str
    sequence: int
    status: str
    model: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    created_at: datetime


class AgentChatTraceResponse(BaseModel):
    conversation_id: str
    turn_id: str = ""
    items: list[AgentChatTraceEvent] = Field(default_factory=list)


class AgentChatResponse(BaseModel):
    conversation_id: str
    turn_id: str
    agent_key: str
    agent_name: str
    content: str
    model_status: str
    model: str = ""
    tool_calls: list[AgentChatToolCall] = Field(default_factory=list)
    knowledge_hits: list[AgentChatKnowledgeHit] = Field(default_factory=list)
    created_at: datetime
