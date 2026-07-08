from datetime import datetime

from pydantic import BaseModel, Field


class AgentRead(BaseModel):
    id: int
    key: str
    name: str
    role: str
    description: str
    model: str
    temperature: float
    max_tokens: int
    enabled: bool
    system_prompt: str
    task_prompt: str
    output_schema: str
    variables: list[str]
    tools: list[str]
    current_version: int
    updated_at: datetime


class AgentListResponse(BaseModel):
    items: list[AgentRead]


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    description: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=256, le=128000)
    enabled: bool | None = None
    system_prompt: str | None = None
    task_prompt: str | None = None
    output_schema: str | None = None
    variables: list[str] | None = None
    tools: list[str] | None = None
    change_note: str = ""


class AgentPromptVersionRead(BaseModel):
    id: int
    agent_key: str
    version: int
    system_prompt: str
    task_prompt: str
    output_schema: str
    variables: list[str]
    tools: list[str]
    change_note: str
    created_at: datetime


class AgentPromptVersionListResponse(BaseModel):
    items: list[AgentPromptVersionRead]


class AgentRollbackRequest(BaseModel):
    version: int
    change_note: str = "回滚提示词版本"


class AgentRenderRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


class AgentRenderResponse(BaseModel):
    agent_key: str
    rendered_system_prompt: str
    rendered_task_prompt: str
    output_schema: str
    missing_variables: list[str]
    tools: list[str]


class AgentTestRunRequest(BaseModel):
    input_text: str = ""
    variables: dict[str, str] = Field(default_factory=dict)


class AgentTestRunResponse(BaseModel):
    agent_key: str
    status: str
    rendered_prompt: AgentRenderResponse
    model: str
    estimated_tokens: int
    output: str
