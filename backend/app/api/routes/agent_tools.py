import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent import AgentConfig
from app.models.agent_audit import AgentToolCallAudit
from app.schemas.agent_tool import AgentToolAuditListResponse, AgentToolAuditRead, AgentToolListResponse, AgentToolRunRequest, AgentToolRunResponse, AgentToolSpec
from app.services.agent_tools import AgentToolError, execute_tool, list_tool_specs

router = APIRouter()


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _tool_spec_read(spec) -> AgentToolSpec:
    return AgentToolSpec(
        key=spec.key,
        name=spec.name,
        description=spec.description,
        category=spec.category,
        enabled=spec.enabled,
        input_schema=spec.input_schema,
        output_schema=spec.output_schema,
    )


@router.get("", response_model=AgentToolListResponse)
def list_agent_tools() -> AgentToolListResponse:
    return AgentToolListResponse(items=[_tool_spec_read(spec) for spec in list_tool_specs()])


@router.get("/audit", response_model=AgentToolAuditListResponse)
def tool_audit(db: Session = Depends(get_db)) -> AgentToolAuditListResponse:
    audits = db.scalars(select(AgentToolCallAudit).order_by(AgentToolCallAudit.id.desc()).limit(1000)).all()
    grouped: dict[str, list[AgentToolCallAudit]] = {}
    for audit in audits:
        grouped.setdefault(audit.tool_key, []).append(audit)
    return AgentToolAuditListResponse(items=[
        AgentToolAuditRead(tool_key=key, total=len(rows), failures=sum(item.status != "success" for item in rows), last_status=rows[0].status, last_error=rows[0].error, last_called_at=rows[0].created_at)
        for key, rows in grouped.items()
    ])


@router.post("/{agent_key}/{tool_key:path}/run", response_model=AgentToolRunResponse)
def run_agent_tool(
    agent_key: str,
    tool_key: str,
    payload: AgentToolRunRequest,
    db: Session = Depends(get_db),
) -> AgentToolRunResponse:
    agent = db.scalar(select(AgentConfig).where(AgentConfig.key == agent_key))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    allowed_tools = set(_json_list(agent.tools_json))
    if tool_key not in allowed_tools:
        raise HTTPException(status_code=403, detail="Tool is not allowed for this agent.")
    try:
        output = execute_tool(db, tool_key, payload.params)
    except AgentToolError as exc:
        db.add(
            AgentToolCallAudit(
                agent_key=agent.key,
                tool_key=tool_key,
                status="failed",
                error=str(exc),
            )
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    db.add(AgentToolCallAudit(agent_key=agent.key, tool_key=tool_key, status="success"))
    db.commit()
    return AgentToolRunResponse(
        agent_key=agent.key,
        tool_key=tool_key,
        status="success",
        output=output,
        metadata={"permission_source": "agent.tools"},
    )
