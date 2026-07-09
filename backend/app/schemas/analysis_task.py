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
    run_key: str
    snapshot_id: int
    report_path: str
    report_format: str
    error_message: str
    created_at: datetime
    updated_at: datetime


class AnalysisTaskListResponse(BaseModel):
    items: list[AnalysisTaskRead]


class AnalysisTaskReportResponse(BaseModel):
    task_key: str
    report_path: str
    content: str = Field(default="")
