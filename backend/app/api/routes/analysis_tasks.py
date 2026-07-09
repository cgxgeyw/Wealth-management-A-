import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.schemas.analysis_task import (
    AnalysisTaskCreateRequest,
    AnalysisTaskListResponse,
    AnalysisTaskRead,
    AnalysisTaskReportResponse,
    AnalysisTaskTemplateListResponse,
)
from app.services.analysis_tasks import (
    create_analysis_task,
    get_analysis_task,
    get_analysis_task_model,
    list_analysis_tasks,
    read_task_report,
    run_analysis_task,
)
from app.services.analysis_task_templates import list_task_templates

router = APIRouter()


@router.post("", response_model=AnalysisTaskRead)
def create_task(
    payload: AnalysisTaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalysisTaskRead:
    task = create_analysis_task(db, payload)
    background_tasks.add_task(run_analysis_task, task.task_key, payload.model_dump(mode="json"))
    return task


@router.get("", response_model=AnalysisTaskListResponse)
def list_tasks(limit: int = 30, db: Session = Depends(get_db)) -> AnalysisTaskListResponse:
    return AnalysisTaskListResponse(items=list_analysis_tasks(db, limit=limit))


@router.get("/templates", response_model=AnalysisTaskTemplateListResponse)
def list_templates() -> AnalysisTaskTemplateListResponse:
    return AnalysisTaskTemplateListResponse(items=list_task_templates())


@router.get("/{task_key}", response_model=AnalysisTaskRead)
def get_task(task_key: str, db: Session = Depends(get_db)) -> AnalysisTaskRead:
    task = get_analysis_task(db, task_key)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis task not found.")
    return task


@router.get("/{task_key}/events")
async def stream_task_events(task_key: str, db: Session = Depends(get_db)) -> StreamingResponse:
    if not get_analysis_task(db, task_key):
        raise HTTPException(status_code=404, detail="Analysis task not found.")

    async def event_stream():
        last_payload = ""
        for _ in range(300):
            with SessionLocal() as event_db:
                task = get_analysis_task(event_db, task_key)
            if not task:
                yield "event: error\ndata: {\"detail\":\"Analysis task not found.\"}\n\n"
                return
            payload = task.model_dump_json()
            if payload != last_payload:
                yield f"event: task\ndata: {payload}\n\n"
                last_payload = payload
            if task.status in {"completed", "failed", "cancelled"}:
                yield f"event: done\ndata: {json.dumps({'status': task.status}, ensure_ascii=False)}\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{task_key}/report", response_model=AnalysisTaskReportResponse)
def get_task_report(task_key: str, db: Session = Depends(get_db)) -> AnalysisTaskReportResponse:
    task = get_analysis_task_model(db, task_key)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis task not found.")
    try:
        content = read_task_report(task)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AnalysisTaskReportResponse(task_key=task.task_key, report_path=task.report_path, content=content)


@router.get("/{task_key}/report/download")
def download_task_report(task_key: str, db: Session = Depends(get_db)) -> FileResponse:
    task = get_analysis_task_model(db, task_key)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis task not found.")
    if not task.report_path:
        raise HTTPException(status_code=404, detail="Report is not generated.")
    path = Path(task.report_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found.")
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=path.name)
