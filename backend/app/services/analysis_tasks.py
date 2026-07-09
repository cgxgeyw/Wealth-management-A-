from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.analysis_task import AnalysisTask
from app.schemas.agent_run import AgentRunRead
from app.schemas.analysis_task import AnalysisTaskCreateRequest, AnalysisTaskRead
from app.services.agent_orchestrator import create_agent_run
from app.services.analysis_task_templates import get_task_template_for_db


def ensure_analysis_task_schema(db: Session) -> None:
    AnalysisTask.__table__.create(bind=db.get_bind(), checkfirst=True)
    if db.get_bind().dialect.name != "sqlite":
        return
    existing = {row[1] for row in db.execute(text("PRAGMA table_info(analysis_tasks)")).all()}
    if "report_format" not in existing:
        db.execute(text("ALTER TABLE analysis_tasks ADD COLUMN report_format VARCHAR(40) DEFAULT ''"))
        db.commit()


def create_analysis_task(db: Session, payload: AnalysisTaskCreateRequest) -> AnalysisTaskRead:
    ensure_analysis_task_schema(db)
    symbol = _normalize_symbol(payload.symbol)
    task = AnalysisTask(
        task_key=f"AT-{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}",
        symbol=symbol,
        query=payload.query,
        mode=payload.mode,
        status="pending",
        stage="queued",
        progress=5,
        agent_keys_json=json.dumps(payload.agent_keys, ensure_ascii=False),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return analysis_task_read(task)


def apply_task_template_defaults(db: Session, payload: AnalysisTaskCreateRequest) -> AnalysisTaskCreateRequest:
    template = get_task_template_for_db(db, payload.mode)
    if not template:
        return payload
    updates: dict[str, object] = {}
    if not payload.query.strip():
        updates["query"] = str(template["default_prompt"])
    if not payload.agent_keys:
        updates["agent_keys"] = [str(item) for item in template["agent_keys"]]
        updates["include_report"] = bool(template["include_report"])
    return payload.model_copy(update=updates) if updates else payload


def run_analysis_task(task_key: str, payload_data: dict) -> None:
    with SessionLocal() as db:
        ensure_analysis_task_schema(db)
        task = db.scalar(select(AnalysisTask).where(AnalysisTask.task_key == task_key))
        if not task:
            return
        payload = AnalysisTaskCreateRequest(**payload_data)
        _execute_analysis_task(db, task, payload)


def run_analysis_task_inline(db: Session, task_key: str, payload: AnalysisTaskCreateRequest) -> AnalysisTaskRead:
    task = db.scalar(select(AnalysisTask).where(AnalysisTask.task_key == task_key))
    if not task:
        raise ValueError("Analysis task not found.")
    _execute_analysis_task(db, task, payload)
    return analysis_task_read(task)


def _execute_analysis_task(db: Session, task: AnalysisTask, payload: AnalysisTaskCreateRequest) -> None:
    try:
        _set_task_state(db, task, "running", "fetching_data", 20)
        run = create_agent_run(db, payload)
        _set_task_state(db, task, "running", "running_agents", 70)
        task.run_key = run.run_key
        task.snapshot_id = run.snapshot_id
        task.report_path = _extract_report_path(run)
        task.report_format = "markdown" if task.report_path else ""
        status = "completed" if run.status in {"completed", "partial"} else "failed"
        stage = "completed" if status == "completed" else "failed"
        _set_task_state(db, task, status, stage, 100)
    except Exception as exc:
        task.error_message = str(exc)
        _set_task_state(db, task, "failed", "failed", 100)


def list_analysis_tasks(db: Session, limit: int = 30) -> list[AnalysisTaskRead]:
    ensure_analysis_task_schema(db)
    tasks = db.scalars(select(AnalysisTask).order_by(desc(AnalysisTask.id)).limit(min(max(limit, 1), 100))).all()
    return [analysis_task_read(task) for task in tasks]


def get_analysis_task(db: Session, task_key: str) -> AnalysisTaskRead | None:
    ensure_analysis_task_schema(db)
    task = db.scalar(select(AnalysisTask).where(AnalysisTask.task_key == task_key))
    return analysis_task_read(task) if task else None


def get_analysis_task_model(db: Session, task_key: str) -> AnalysisTask | None:
    ensure_analysis_task_schema(db)
    return db.scalar(select(AnalysisTask).where(AnalysisTask.task_key == task_key))


def read_task_report(task: AnalysisTask) -> str:
    if not task.report_path:
        raise FileNotFoundError("Report is not generated.")
    path = Path(task.report_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Report file not found.")
    return path.read_text(encoding="utf-8")


def analysis_task_read(task: AnalysisTask) -> AnalysisTaskRead:
    return AnalysisTaskRead(
        id=task.id,
        task_key=task.task_key,
        symbol=task.symbol,
        query=task.query,
        mode=task.mode,
        status=task.status,
        stage=task.stage,
        progress=task.progress,
        agent_keys=_json_list(task.agent_keys_json),
        run_key=task.run_key,
        snapshot_id=task.snapshot_id,
        report_path=task.report_path,
        report_format=task.report_format,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _set_task_state(db: Session, task: AnalysisTask, status: str, stage: str, progress: int) -> None:
    task.status = status
    task.stage = stage
    task.progress = min(max(progress, 0), 100)
    db.add(task)
    db.commit()
    db.refresh(task)


def _extract_report_path(run: AgentRunRead) -> str:
    for step in run.steps:
        if step.tool_key == "document.write" and step.status == "success":
            path = step.output_preview.get("path")
            return str(path) if path else ""
    return ""


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []
