from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.model_config import ModelConfig


@dataclass(frozen=True)
class ModelRuntime:
    key: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: int


def get_model_runtime(db: Session, capability: str, preferred_model: str = "") -> ModelRuntime:
    rows = db.scalars(
        select(ModelConfig).where(ModelConfig.capability == capability, ModelConfig.enabled.is_(True))
    ).all()
    selected = next((item for item in rows if preferred_model and item.key == preferred_model), None)
    selected = selected or next((item for item in rows if preferred_model and item.model == preferred_model), None)
    selected = selected or next((item for item in rows if item.is_default), None)
    selected = selected or (rows[0] if rows else None)
    if selected:
        fallback_key = settings.embedding_api_key if capability == "embedding" else settings.llm_api_key if capability == "chat" else ""
        return ModelRuntime(selected.key, selected.model, selected.base_url, selected.api_key or fallback_key, selected.timeout_seconds)
    if capability == "embedding":
        return ModelRuntime("env.embedding", settings.embedding_model, settings.embedding_base_url, settings.embedding_api_key, int(settings.embedding_timeout_seconds))
    if capability == "rerank":
        return ModelRuntime("", "", "", "", 30)
    return ModelRuntime("env.chat", settings.llm_model, settings.llm_base_url, settings.llm_api_key, int(settings.llm_timeout_seconds))
