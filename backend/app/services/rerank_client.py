from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.services.model_runtime import get_model_runtime


def rerank_rows(db: Session, query: str, rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    runtime = get_model_runtime(db, "rerank")
    if not runtime.model or not rows:
        return rows
    endpoint = runtime.base_url.rstrip("/")
    endpoint = endpoint if endpoint.endswith("/rerank") else f"{endpoint}/v1/rerank"
    headers = {"Content-Type": "application/json"}
    if runtime.api_key:
        headers["Authorization"] = f"Bearer {runtime.api_key}"
    documents = [f"{row.get('title', '')}\n{row.get('content', '')}" for row in rows]
    try:
        with httpx.Client(timeout=runtime.timeout_seconds) as client:
            response = client.post(endpoint, headers=headers, json={"model": runtime.model, "query": query, "documents": documents, "top_n": top_k})
            response.raise_for_status()
            result = response.json().get("results") or []
    except (httpx.HTTPError, ValueError, AttributeError):
        return rows
    ranked: list[dict[str, Any]] = []
    for item in result:
        if isinstance(item, dict) and isinstance(item.get("index"), int) and 0 <= item["index"] < len(rows):
            ranked.append(rows[item["index"]] | {"rerank_score": float(item.get("relevance_score") or 0)})
    return ranked or rows
