from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.agent_run import AgentRunCreateRequest


class AnalysisTaskCreateRequest(AgentRunCreateRequest):
    include_report: bool = True


class AnalysisTaskRead(BaseModel):
    id: int
    task_key: str
    symbol: str
    query: str
    mode: str
    status: str
    stage: str
    progress: int
    agent_keys: list[str]
    workflow: dict = Field(default_factory=dict)
    run_key: str
    snapshot_id: int
    report_path: str
    report_format: str
    error_message: str
    created_at: datetime
    updated_at: datetime


class AnalysisTaskListResponse(BaseModel):
    items: list[AnalysisTaskRead]


class AnalysisTaskExecutionEventRead(BaseModel):
    id: int
    task_key: str
    run_key: str
    sequence: int
    event_type: str
    agent_key: str
    agent_name: str
    tool_key: str
    status: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime


class AnalysisTaskExecutionEventListResponse(BaseModel):
    items: list[AnalysisTaskExecutionEventRead]


class AnalysisTaskTemplateRead(BaseModel):
    key: str
    group: str
    group_name: str
    name: str
    description: str
    agent_keys: list[str]
    include_report: bool
    default_prompt: str
    reference: str
    focus: list[str]
    required_output: list[str]
    is_customized: bool = False


class AnalysisTaskTemplateListResponse(BaseModel):
    items: list[AnalysisTaskTemplateRead]


class AnalysisTaskTemplateUpdateRequest(BaseModel):
    default_prompt: str | None = Field(default=None, max_length=20000)
    agent_keys: list[str] | None = None
    include_report: bool | None = None


class AnalysisTaskReportResponse(BaseModel):
    task_key: str
    report_path: str
    content: str = Field(default="")
