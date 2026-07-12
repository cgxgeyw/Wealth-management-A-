from datetime import datetime

from pydantic import BaseModel, Field


class AgentSkillRead(BaseModel):
    id: int
    key: str
    name: str
    description: str
    instruction: str
    enabled: bool
    agent_keys: list[str] = Field(default_factory=list)
    usage_count: int = 0
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentSkillListResponse(BaseModel):
    items: list[AgentSkillRead]


class AgentSkillCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    instruction: str = ""
    enabled: bool = True
    agent_keys: list[str] = Field(default_factory=list)


class AgentSkillUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    instruction: str | None = None
    enabled: bool | None = None
    agent_keys: list[str] | None = None
