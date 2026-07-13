from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentToolCallAudit(Base):
    __tablename__ = "agent_tool_call_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_key: Mapped[str] = mapped_column(String(80), index=True)
    tool_key: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(24), default="success")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentChatTrace(Base):
    __tablename__ = "agent_chat_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[str] = mapped_column(String(80), index=True)
    turn_id: Mapped[str] = mapped_column(String(80), index=True)
    agent_key: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="info")
    model: Mapped[str] = mapped_column(String(160), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentSkillUsageAudit(Base):
    __tablename__ = "agent_skill_usage_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_key: Mapped[str] = mapped_column(String(80), index=True)
    skill_key: Mapped[str] = mapped_column(String(80), index=True)
    run_key: Mapped[str] = mapped_column(String(100), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
