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


class AgentSkillUsageAudit(Base):
    __tablename__ = "agent_skill_usage_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_key: Mapped[str] = mapped_column(String(80), index=True)
    skill_key: Mapped[str] = mapped_column(String(80), index=True)
    run_key: Mapped[str] = mapped_column(String(100), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
