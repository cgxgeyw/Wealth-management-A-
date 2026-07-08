from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.data_source import SectorSnapshotResponse
from app.services.data_fetcher import DataFetchError, get_sector_snapshots

router = APIRouter()


@router.get("/snapshots", response_model=SectorSnapshotResponse)
def snapshots(
    sector_type: str = "industry",
    limit: int = 20,
    db: Session = Depends(get_db),
) -> SectorSnapshotResponse:
    try:
        return get_sector_snapshots(db, sector_type=sector_type, limit=limit)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type == "invalid_sector_type" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
