from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(40), default="", index=True)
    query: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(80), default="analysis")
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    stage: Mapped[str] = mapped_column(String(80), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    agent_keys_json: Mapped[str] = mapped_column(Text, default="[]")
    run_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    snapshot_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    report_path: Mapped[str] = mapped_column(Text, default="")
    report_format: Mapped[str] = mapped_column(String(40), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
