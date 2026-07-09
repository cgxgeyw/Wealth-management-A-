from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis_task import (
    AnalysisTaskCreateRequest,
    AnalysisTaskListResponse,
    AnalysisTaskRead,
    AnalysisTaskReportResponse,
)
from app.services.analysis_tasks import (
    create_analysis_task,
    get_analysis_task,
    get_analysis_task_model,
    list_analysis_tasks,
    read_task_report,
)

router = APIRouter()


@router.post("", response_model=AnalysisTaskRead)
def create_task(payload: AnalysisTaskCreateRequest, db: Session = Depends(get_db)) -> AnalysisTaskRead:
    return create_analysis_task(db, payload)


@router.get("", response_model=AnalysisTaskListResponse)
def list_tasks(limit: int = 30, db: Session = Depends(get_db)) -> AnalysisTaskListResponse:
    return AnalysisTaskListResponse(items=list_analysis_tasks(db, limit=limit))


@router.get("/{task_key}", response_model=AnalysisTaskRead)
def get_task(task_key: str, db: Session = Depends(get_db)) -> AnalysisTaskRead:
    task = get_analysis_task(db, task_key)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis task not found.")
    return task


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
