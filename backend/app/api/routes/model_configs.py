from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.model_config import ModelConfig
from app.schemas.model_config import ModelConfigCreateRequest, ModelConfigListResponse, ModelConfigRead, ModelConfigUpdateRequest

router = APIRouter()


def _mask(value: str) -> str:
    return "" if not value else ("*" * len(value) if len(value) <= 6 else f"{value[:3]}***{value[-3:]}")


def _read(row: ModelConfig) -> ModelConfigRead:
    return ModelConfigRead(
        id=row.id, key=row.key, name=row.name, capability=row.capability, model=row.model, base_url=row.base_url,
        api_key_configured=bool(row.api_key), api_key_masked=_mask(row.api_key), timeout_seconds=row.timeout_seconds,
        enabled=row.enabled, is_default=row.is_default, created_at=row.created_at, updated_at=row.updated_at,
    )


def _ensure_single_default(db: Session, capability: str, selected: ModelConfig) -> None:
    for row in db.scalars(select(ModelConfig).where(ModelConfig.capability == capability, ModelConfig.id != selected.id)).all():
        row.is_default = False
        db.add(row)


@router.get("", response_model=ModelConfigListResponse)
def list_configs(db: Session = Depends(get_db)) -> ModelConfigListResponse:
    rows = db.scalars(select(ModelConfig).order_by(ModelConfig.capability, ModelConfig.id)).all()
    return ModelConfigListResponse(items=[_read(row) for row in rows])


@router.post("", response_model=ModelConfigRead)
def create_config(payload: ModelConfigCreateRequest, db: Session = Depends(get_db)) -> ModelConfigRead:
    if db.scalar(select(ModelConfig).where(ModelConfig.key == payload.key)):
        raise HTTPException(status_code=409, detail="Model config key already exists.")
    row = ModelConfig(**payload.model_dump())
    db.add(row)
    db.flush()
    if row.is_default:
        _ensure_single_default(db, row.capability, row)
    db.commit()
    db.refresh(row)
    return _read(row)


@router.patch("/{config_key}", response_model=ModelConfigRead)
def update_config(config_key: str, payload: ModelConfigUpdateRequest, db: Session = Depends(get_db)) -> ModelConfigRead:
    row = db.scalar(select(ModelConfig).where(ModelConfig.key == config_key))
    if not row:
        raise HTTPException(status_code=404, detail="Model config not found.")
    for field in ("name", "model", "base_url", "api_key", "timeout_seconds", "enabled", "is_default"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value.strip() if isinstance(value, str) else value)
    if row.is_default:
        _ensure_single_default(db, row.capability, row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _read(row)


@router.delete("/{config_key}", status_code=204)
def delete_config(config_key: str, db: Session = Depends(get_db)) -> None:
    row = db.scalar(select(ModelConfig).where(ModelConfig.key == config_key))
    if not row:
        raise HTTPException(status_code=404, detail="Model config not found.")
    db.delete(row)
    db.commit()
