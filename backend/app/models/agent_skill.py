from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    instruction: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentSkillAssignment(Base):
    __tablename__ = "agent_skill_assignments"
    __table_args__ = (UniqueConstraint("agent_key", "skill_key", name="uq_agent_skill_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_key: Mapped[str] = mapped_column(String(80), index=True)
    skill_key: Mapped[str] = mapped_column(String(80), index=True)
