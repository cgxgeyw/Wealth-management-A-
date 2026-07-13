import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent_audit import AgentChatTrace
from app.schemas.agent_chat import AgentChatRequest, AgentChatResponse, AgentChatTraceEvent, AgentChatTraceResponse
from app.services.agent_chat import create_agent_chat_response
from app.services.agent_tools import AgentToolError

router = APIRouter()


@router.get("/conversations/{conversation_id}", response_model=AgentChatTraceResponse)
def get_conversation_trace(
    conversation_id: str,
    turn_id: str = "",
    db: Session = Depends(get_db),
) -> AgentChatTraceResponse:
    statement = select(AgentChatTrace).where(AgentChatTrace.conversation_id == conversation_id)
    if turn_id:
        statement = statement.where(AgentChatTrace.turn_id == turn_id)
    rows = db.scalars(statement.order_by(AgentChatTrace.turn_id, AgentChatTrace.sequence, AgentChatTrace.id)).all()
    return AgentChatTraceResponse(
        conversation_id=conversation_id,
        turn_id=turn_id,
        items=[
            AgentChatTraceEvent(
                conversation_id=row.conversation_id,
                turn_id=row.turn_id,
                agent_key=row.agent_key,
                event_type=row.event_type,
                sequence=row.sequence,
                status=row.status,
                model=row.model,
                detail=json.loads(row.detail_json or "{}"),
                error=row.error,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.post("/{agent_key}", response_model=AgentChatResponse)
def chat_with_agent(
    agent_key: str,
    payload: AgentChatRequest,
    db: Session = Depends(get_db),
) -> AgentChatResponse:
    try:
        return create_agent_chat_response(db, agent_key, payload)
    except AgentToolError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
