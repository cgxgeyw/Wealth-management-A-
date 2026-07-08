from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeEmbedding
from app.schemas.knowledge import KnowledgeFaissStatus


def rebuild_faiss_index(db: Session) -> KnowledgeFaissStatus:
    faiss, np, message = _load_runtime()
    index_path, mapping_path = _index_paths()
    if not settings.faiss_enabled:
        return _status(False, False, "FAISS is disabled.")
    if faiss is None or np is None:
        return _status(True, False, message)

    embeddings = db.scalars(
        select(KnowledgeEmbedding)
        .where(KnowledgeEmbedding.model == settings.embedding_model)
        .order_by(KnowledgeEmbedding.id)
    ).all()
    vectors: list[list[float]] = []
    chunk_ids: list[int] = []
    dimension = 0
    for embedding in embeddings:
        vector = _json_float_list(embedding.vector_json)
        if not vector:
            continue
        if dimension == 0:
            dimension = len(vector)
        if len(vector) != dimension:
            continue
        vectors.append(vector)
        chunk_ids.append(embedding.chunk_id)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    if not vectors:
        _remove_if_exists(index_path)
        _remove_if_exists(mapping_path)
        return _status(True, True, "No embeddings to index.")

    matrix = np.asarray(vectors, dtype="float32")
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(dimension)
    index.add(matrix)
    faiss.write_index(index, str(index_path))
    mapping_path.write_text(
        json.dumps(
            {
                "model": settings.embedding_model,
                "dimension": dimension,
                "chunk_ids": chunk_ids,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return _status(True, True, "FAISS index rebuilt.")


def faiss_status() -> KnowledgeFaissStatus:
    _, _, message = _load_runtime()
    available = message == "available"
    return _status(settings.faiss_enabled, available, message)


def search_faiss(query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
    faiss, np, _ = _load_runtime()
    index_path, mapping_path = _index_paths()
    if not settings.faiss_enabled or faiss is None or np is None:
        return []
    if not index_path.exists() or not mapping_path.exists():
        return []
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if mapping.get("model") != settings.embedding_model:
        return []
    chunk_ids = mapping.get("chunk_ids", [])
    dimension = int(mapping.get("dimension") or 0)
    if len(query_vector) != dimension:
        return []

    try:
        index = faiss.read_index(str(index_path))
        query = np.asarray([query_vector], dtype="float32")
        faiss.normalize_L2(query)
        scores, positions = index.search(query, min(max(top_k, 1), max(len(chunk_ids), 1)))
    except Exception:
        return []
    hits: list[dict[str, Any]] = []
    for score, position in zip(scores[0].tolist(), positions[0].tolist()):
        if position < 0 or position >= len(chunk_ids):
            continue
        hits.append({"chunk_id": int(chunk_ids[position]), "vector_score": float(score)})
    return hits


def _status(enabled: bool, available: bool, message: str) -> KnowledgeFaissStatus:
    index_path, mapping_path = _index_paths()
    dimension = 0
    vector_count = 0
    if mapping_path.exists():
        try:
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            dimension = int(mapping.get("dimension") or 0)
            vector_count = len(mapping.get("chunk_ids") or [])
        except json.JSONDecodeError:
            message = "FAISS mapping file is invalid."
    return KnowledgeFaissStatus(
        enabled=enabled,
        available=available,
        indexed=index_path.exists() and mapping_path.exists(),
        model=settings.embedding_model,
        dimension=dimension,
        vector_count=vector_count,
        index_path=str(index_path),
        mapping_path=str(mapping_path),
        message=message,
    )


def _load_runtime():
    try:
        faiss = importlib.import_module("faiss")
        np = importlib.import_module("numpy")
    except ImportError as exc:
        return None, None, f"FAISS runtime unavailable: {exc.name}"
    return faiss, np, "available"


def _index_paths() -> tuple[Path, Path]:
    root = Path(settings.faiss_index_dir)
    suffix = hashlib.sha1(settings.embedding_model.encode("utf-8")).hexdigest()[:12]
    return root / f"knowledge-{suffix}.faiss", root / f"knowledge-{suffix}.mapping.json"


def _json_float_list(value: str) -> list[float]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [float(item) for item in parsed]


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()
