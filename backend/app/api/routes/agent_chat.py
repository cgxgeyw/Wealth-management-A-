from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.agent_chat import AgentChatRequest, AgentChatResponse
from app.services.agent_chat import create_agent_chat_response
from app.services.agent_tools import AgentToolError

router = APIRouter()


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
