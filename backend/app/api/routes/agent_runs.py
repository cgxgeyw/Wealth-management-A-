from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent import AgentRun
from app.schemas.agent_run import AgentRunCreateRequest, AgentRunListResponse, AgentRunRead
from app.services.agent_orchestrator import agent_run_read, create_agent_run

router = APIRouter()


@router.post("", response_model=AgentRunRead)
def create_run(payload: AgentRunCreateRequest, db: Session = Depends(get_db)) -> AgentRunRead:
    return create_agent_run(db, payload)


@router.get("", response_model=AgentRunListResponse)
def list_runs(limit: int = 20, db: Session = Depends(get_db)) -> AgentRunListResponse:
    runs = db.scalars(select(AgentRun).order_by(desc(AgentRun.id)).limit(min(max(limit, 1), 100))).all()
    return AgentRunListResponse(items=[agent_run_read(run) for run in runs])


@router.get("/{run_key}", response_model=AgentRunRead)
def get_run(run_key: str, db: Session = Depends(get_db)) -> AgentRunRead:
    run = db.scalar(select(AgentRun).where(AgentRun.run_key == run_key))
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return agent_run_read(run)
