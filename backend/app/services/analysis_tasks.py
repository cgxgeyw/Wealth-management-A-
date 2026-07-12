from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, desc, func, select, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.agent import AgentConfig, AgentRun
from app.services.agent_skills import assigned_skill_catalog
from app.models.analysis_task import AnalysisTask, AnalysisTaskExecutionEvent
from app.schemas.agent_run import AgentRunRead, AgentRunStep
from app.schemas.analysis_task import AnalysisTaskCreateRequest, AnalysisTaskExecutionEventRead, AnalysisTaskRead
from app.services.agent_orchestrator import agent_run_read, create_agent_run
from app.services.agent_tools import execute_tool
from app.services.analysis_task_templates import get_task_template_for_db


def ensure_analysis_task_schema(db: Session) -> None:
    AnalysisTask.__table__.create(bind=db.get_bind(), checkfirst=True)
    AnalysisTaskExecutionEvent.__table__.create(bind=db.get_bind(), checkfirst=True)
    if db.get_bind().dialect.name != "sqlite":
        return
    existing = {row[1] for row in db.execute(text("PRAGMA table_info(analysis_tasks)")).all()}
    if "report_format" not in existing:
        db.execute(text("ALTER TABLE analysis_tasks ADD COLUMN report_format VARCHAR(40) DEFAULT ''"))
        db.commit()
    if "workflow_json" not in existing:
        db.execute(text("ALTER TABLE analysis_tasks ADD COLUMN workflow_json TEXT DEFAULT '{}'"))
        db.commit()


def create_analysis_task(db: Session, payload: AnalysisTaskCreateRequest) -> AnalysisTaskRead:
    ensure_analysis_task_schema(db)
    symbol = _normalize_symbol(payload.symbol)
    workflow = _freeze_workflow(
        db,
        payload.agent_keys,
        workflow_instruction=str(payload.variables.get("workflow_instruction") or ""),
    )
    task = AnalysisTask(
        task_key=f"AT-{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}",
        symbol=symbol,
        query=payload.query,
        mode=payload.mode,
        status="pending",
        stage="queued",
        progress=5,
        agent_keys_json=json.dumps(payload.agent_keys, ensure_ascii=False),
        workflow_json=json.dumps(workflow, ensure_ascii=False),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return analysis_task_read(task)


def apply_task_template_defaults(db: Session, payload: AnalysisTaskCreateRequest) -> AnalysisTaskCreateRequest:
    template = get_task_template_for_db(db, payload.mode)
    if not template:
        agent_keys = [key for key in payload.agent_keys if key != "research_director"]
        agent_keys.append("research_director")
        return payload.model_copy(update={"agent_keys": agent_keys})
    updates: dict[str, object] = {}
    variables = dict(payload.variables)
    variables["workflow_instruction"] = str(template["default_prompt"])
    updates["variables"] = variables
    agent_keys = [str(item) for item in template["agent_keys"] if str(item) != "research_director"]
    agent_keys.append("research_director")
    updates["agent_keys"] = agent_keys
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
        _set_task_state(db, task, "running", "running_agents", 20)
        record_execution_event(db, task.task_key, "task_started", status="running", payload={"mode": payload.mode})
        agent_order = {key: index for index, key in enumerate(payload.agent_keys)}
        agent_total = max(len(payload.agent_keys), 1)

        def handle_agent_event(event: dict) -> None:
            record_execution_event(db, task.task_key, **event)
            agent_key = str(event.get("agent_key") or "")
            index = agent_order.get(agent_key, 0)
            if event.get("event_type") == "agent_started":
                _set_task_state(db, task, "running", f"agent:{agent_key}", 20 + int(60 * index / agent_total))
            elif event.get("event_type") == "agent_completed":
                _set_task_state(db, task, "running", f"agent_completed:{agent_key}", 20 + int(60 * (index + 1) / agent_total))

        run = create_agent_run(
            db,
            payload,
            agent_snapshots=list(_json_dict(task.workflow_json).get("agents") or []),
            on_event=handle_agent_event,
        )
        task.run_key = run.run_key
        task.snapshot_id = run.snapshot_id
        quality_gate = run.result.get("quality_gate", {}) if isinstance(run.result, dict) else {}
        if run.status == "failed":
            failed_agents = [
                item.get("agent_name") or item.get("agent_key")
                for item in run.result.get("agent_summaries", [])
                if item.get("status") == "failed"
            ]
            raise RuntimeError(f"工作流阶段失败：{', '.join(failed_agents) or '未知阶段'}。")
        if not quality_gate.get("passed"):
            errors = quality_gate.get("errors") if isinstance(quality_gate.get("errors"), list) else []
            raise RuntimeError("最终报告质量校验失败：" + "；".join(str(item) for item in errors))
        _set_task_state(db, task, "running", "validating_report", 88)
        record_execution_event(db, task.task_key, "report_validated", run_key=run.run_key, status="completed", payload=quality_gate)
        if payload.include_report:
            _ensure_task_report(db, task, run)
        task.report_path = _extract_report_path(run) if payload.include_report else ""
        if payload.include_report and not task.report_path:
            raise RuntimeError("投研总监已完成，但最终报告未能保存。")
        if task.report_path:
            _set_task_state(db, task, "running", "report_saved", 95)
            record_execution_event(db, task.task_key, "report_saved", run_key=run.run_key, status="completed", payload={"report_path": task.report_path})
        task.report_format = "markdown" if task.report_path else ""
        status = "completed" if run.status in {"completed", "partial"} else "failed"
        stage = "completed" if status == "completed" else "failed"
        _set_task_state(db, task, status, stage, 100)
        record_execution_event(db, task.task_key, "task_completed", run_key=run.run_key, status=status, payload={"step_count": len(run.steps)})
    except Exception as exc:
        task.error_message = str(exc)
        _set_task_state(db, task, "failed", "failed", 100)
        record_execution_event(db, task.task_key, "task_failed", status="failed", payload={"error": str(exc)})


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


def generate_analysis_task_report(db: Session, task_key: str) -> AnalysisTaskRead | None:
    """Generate a report for a completed task that predates automatic report creation."""
    task = db.scalar(select(AnalysisTask).where(AnalysisTask.task_key == task_key))
    if not task:
        return None
    if task.status not in {"completed", "partial"}:
        raise ValueError("任务尚未完成，暂不能生成报告。")
    if not task.run_key:
        raise ValueError("任务没有可用的运行结果。")
    run_model = db.scalar(select(AgentRun).where(AgentRun.run_key == task.run_key))
    if not run_model:
        raise ValueError("任务运行结果不存在。")
    run = agent_run_read(run_model)
    _ensure_task_report(db, task, run)
    task.report_path = _extract_report_path(run)
    task.report_format = "markdown" if task.report_path else ""
    db.add(task)
    db.commit()
    db.refresh(task)
    return analysis_task_read(task)


def delete_analysis_task(db: Session, task_key: str) -> bool:
    """Remove a finished task and its task-owned artifacts without touching run evidence."""
    task = db.scalar(select(AnalysisTask).where(AnalysisTask.task_key == task_key))
    if not task:
        return False
    if task.status in {"pending", "running"}:
        raise ValueError("正在执行的任务不能删除。")
    _delete_task_artifacts(task)
    db.execute(delete(AnalysisTaskExecutionEvent).where(AnalysisTaskExecutionEvent.task_key == task_key))
    db.delete(task)
    db.commit()
    return True


def clear_finished_analysis_tasks(db: Session) -> int:
    """Clear historical task records while preserving tasks still being executed."""
    tasks = db.scalars(
        select(AnalysisTask).where(AnalysisTask.status.not_in(("pending", "running")))
    ).all()
    if not tasks:
        return 0
    task_keys = [task.task_key for task in tasks]
    for task in tasks:
        _delete_task_artifacts(task)
    db.execute(delete(AnalysisTaskExecutionEvent).where(AnalysisTaskExecutionEvent.task_key.in_(task_keys)))
    for task in tasks:
        db.delete(task)
    db.commit()
    return len(tasks)


def list_execution_events(db: Session, task_key: str) -> list[AnalysisTaskExecutionEventRead]:
    ensure_analysis_task_schema(db)
    rows = db.scalars(
        select(AnalysisTaskExecutionEvent)
        .where(AnalysisTaskExecutionEvent.task_key == task_key)
        .order_by(AnalysisTaskExecutionEvent.sequence)
    ).all()
    return [execution_event_read(row) for row in rows]


def record_execution_event(
    db: Session,
    task_key: str,
    event_type: str,
    *,
    run_key: str = "",
    agent_key: str = "",
    agent_name: str = "",
    tool_key: str = "",
    status: str = "",
    payload: dict | None = None,
) -> None:
    sequence = (db.scalar(select(func.max(AnalysisTaskExecutionEvent.sequence)).where(AnalysisTaskExecutionEvent.task_key == task_key)) or 0) + 1
    db.add(
        AnalysisTaskExecutionEvent(
            task_key=task_key,
            run_key=run_key,
            sequence=sequence,
            event_type=event_type,
            agent_key=agent_key,
            agent_name=agent_name,
            tool_key=tool_key,
            status=status,
            payload_json=json.dumps(_bounded_payload(payload or {}), ensure_ascii=False, default=str),
        )
    )
    db.commit()


def execution_event_read(row: AnalysisTaskExecutionEvent) -> AnalysisTaskExecutionEventRead:
    return AnalysisTaskExecutionEventRead(
        id=row.id,
        task_key=row.task_key,
        run_key=row.run_key,
        sequence=row.sequence,
        event_type=row.event_type,
        agent_key=row.agent_key,
        agent_name=row.agent_name,
        tool_key=row.tool_key,
        status=row.status,
        payload=_json_dict(row.payload_json),
        created_at=row.created_at,
    )


def read_task_report(task: AnalysisTask) -> str:
    if not task.report_path:
        raise FileNotFoundError("Report is not generated.")
    path = Path(task.report_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Report file not found.")
    return path.read_text(encoding="utf-8")


def _delete_task_artifacts(task: AnalysisTask) -> None:
    if not task.report_path:
        return
    path = Path(task.report_path)
    if path.exists() and path.is_file():
        path.unlink()


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
        workflow=_json_dict(task.workflow_json),
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


def _ensure_task_report(db: Session, task: AnalysisTask, run: AgentRunRead) -> None:
    if _extract_report_path(run):
        return
    result = run.result if isinstance(run.result, dict) else {}
    markdown_report = str(result.get("markdown_report") or "").strip()
    if not markdown_report:
        raise ValueError("投研总监没有生成 Markdown 报告。")
    subject = next((line.strip() for line in task.query.splitlines() if line.strip()), "分析任务")[:80]
    output = execute_tool(
        db,
        "document.write",
        {
            "title": str(result.get("title") or f"{subject}分析报告"),
            "topic": subject,
            "content": markdown_report,
            "references": [f"task:{task.task_key}", f"run:{run.run_key}"],
        },
    )
    run.steps.append(
        AgentRunStep(
            agent_key="system",
            agent_name="报告生成",
            tool_key="document.write",
            status="success",
            params={"task_key": task.task_key},
            output_preview={"path": output.get("path", ""), "summary": "系统报告已生成"},
        )
    )


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _json_dict(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bounded_payload(payload: dict) -> dict:
    rendered = json.dumps(payload, ensure_ascii=False, default=str)
    if len(rendered) <= 50000:
        return payload
    return {"truncated": True, "preview": rendered[:50000]}


def _freeze_workflow(db: Session, agent_keys: list[str], *, workflow_instruction: str) -> dict:
    rows = db.scalars(select(AgentConfig).where(AgentConfig.key.in_(agent_keys))).all()
    by_key = {agent.key: agent for agent in rows if agent.enabled}
    return {
        "version": 2,
        "execution_strategy": "sequential_evidence_pipeline",
        "final_agent_key": "research_director",
        "workflow_instruction": workflow_instruction,
        "steps": [
            {
                "order": index + 1,
                "agent_key": agent.key,
                "phase": "final_synthesis" if agent.key == "research_director" else "specialist_analysis",
                "depends_on": [item for item in agent_keys[:index] if item in by_key],
                "output_contract": "final_report" if agent.key == "research_director" else "stage_artifact",
            }
            for index, key in enumerate(agent_keys)
            if (agent := by_key.get(key))
        ],
        "agents": [
            {
                "key": agent.key,
                "name": agent.name,
                "role": agent.role,
                "model": agent.model,
                "temperature": agent.temperature,
                "prompt_version": agent.current_version,
                "system_prompt": agent.system_prompt,
                "task_prompt": agent.task_prompt,
                "tools": _json_list(agent.tools_json),
                "skills": assigned_skill_catalog(db, agent.key),
                "phase": "final_synthesis" if agent.key == "research_director" else "specialist_analysis",
                "output_contract": "final_report" if agent.key == "research_director" else "stage_artifact",
            }
            for key in agent_keys
            if (agent := by_key.get(key))
        ],
    }
