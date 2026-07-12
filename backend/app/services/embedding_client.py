from __future__ import annotations

from typing import Any

import httpx

from app.db.session import SessionLocal
from app.services.model_runtime import get_model_runtime


class EmbeddingError(RuntimeError):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    with SessionLocal() as db:
        runtime = get_model_runtime(db, "embedding")
    endpoint = _embedding_endpoint(runtime.base_url)
    headers = {"Content-Type": "application/json"}
    if runtime.api_key:
        headers["Authorization"] = f"Bearer {runtime.api_key}"
    try:
        with httpx.Client(timeout=runtime.timeout_seconds) as client:
            response = client.post(
                endpoint,
                headers=headers,
                json={"model": runtime.model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise EmbeddingError(str(exc)) from exc
    vectors = _parse_embedding_response(data)
    if len(vectors) != len(texts):
        raise EmbeddingError("Embedding response count does not match input count.")
    return vectors


def _embedding_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/embeddings"
    return f"{base}/v1/embeddings"


def _parse_embedding_response(data: dict[str, Any]) -> list[list[float]]:
    rows = data.get("data")
    if not isinstance(rows, list):
        raise EmbeddingError("Embedding response missing data list.")
    rows = sorted(rows, key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0)
    vectors: list[list[float]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("embedding"), list):
            raise EmbeddingError("Embedding row missing vector.")
        vectors.append([float(value) for value in row["embedding"]])
    return vectors
