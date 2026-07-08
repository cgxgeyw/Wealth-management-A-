from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeEmbedding, KnowledgeRetrievalLog
from app.schemas.knowledge import (
    KnowledgeDocumentCreateRequest,
    KnowledgeDocumentDetail,
    KnowledgeDocumentRead,
    KnowledgeDocumentUpdateRequest,
    KnowledgeReindexAllResponse,
    KnowledgeSearchItem,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.embedding_client import EmbeddingError, embed_texts
from app.services.knowledge_faiss import rebuild_faiss_index
from app.services.knowledge_faiss import search_faiss


def ensure_knowledge_fts(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts
            USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, title, content, tags)
            """
        )
    )
    db.commit()


def create_document(db: Session, payload: KnowledgeDocumentCreateRequest) -> KnowledgeDocumentDetail:
    ensure_knowledge_fts(db)
    document = KnowledgeDocument(
        title=payload.title.strip(),
        doc_type=payload.doc_type.strip() or "note",
        source=payload.source.strip() or "manual",
        content=payload.content,
        summary=_summarize(payload.content),
        symbols_json=json.dumps(_normalize_list(payload.symbols), ensure_ascii=False),
        tags_json=json.dumps(_normalize_list(payload.tags), ensure_ascii=False),
        metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
        enabled=payload.enabled,
        published_at=payload.published_at,
        status="indexed",
    )
    db.add(document)
    db.flush()
    _replace_chunks(db, document)
    db.commit()
    db.refresh(document)
    rebuild_faiss_index(db)
    return document_detail(db, document)


def list_documents(db: Session, q: str = "", limit: int = 50) -> list[KnowledgeDocumentRead]:
    query = select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).limit(min(max(limit, 1), 200))
    documents = db.scalars(query).all()
    if q.strip():
        needle = q.strip().lower()
        documents = [
            item
            for item in documents
            if needle in f"{item.title} {item.source} {item.doc_type} {item.tags_json} {item.symbols_json}".lower()
        ]
    return [document_read(item) for item in documents]


def get_document(db: Session, document_id: int) -> KnowledgeDocumentDetail | None:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        return None
    return document_detail(db, document)


def update_document(
    db: Session,
    document_id: int,
    payload: KnowledgeDocumentUpdateRequest,
) -> KnowledgeDocumentDetail | None:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        return None
    for field in ("title", "doc_type", "source", "published_at"):
        value = getattr(payload, field)
        if value is not None:
            setattr(document, field, value)
    if payload.symbols is not None:
        document.symbols_json = json.dumps(_normalize_list(payload.symbols), ensure_ascii=False)
    if payload.tags is not None:
        document.tags_json = json.dumps(_normalize_list(payload.tags), ensure_ascii=False)
    if payload.metadata is not None:
        document.metadata_json = json.dumps(payload.metadata, ensure_ascii=False)
    if payload.enabled is not None:
        document.enabled = payload.enabled
    db.add(document)
    db.commit()
    db.refresh(document)
    return document_detail(db, document)


def delete_document(db: Session, document_id: int) -> bool:
    ensure_knowledge_fts(db)
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        return False
    db.execute(delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == document_id))
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    db.execute(text("DELETE FROM knowledge_chunks_fts WHERE document_id = :document_id"), {"document_id": document_id})
    db.delete(document)
    db.commit()
    rebuild_faiss_index(db)
    return True


def reindex_document(db: Session, document_id: int) -> KnowledgeDocumentDetail | None:
    ensure_knowledge_fts(db)
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        return None
    _replace_chunks(db, document)
    document.status = "indexed"
    db.add(document)
    db.commit()
    db.refresh(document)
    rebuild_faiss_index(db)
    return document_detail(db, document)


def reindex_all_documents(db: Session) -> KnowledgeReindexAllResponse:
    ensure_knowledge_fts(db)
    documents = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id)).all()
    reindexed = 0
    failed = 0
    for document in documents:
        try:
            _replace_chunks(db, document)
            document.status = "indexed"
            db.add(document)
            db.commit()
            db.refresh(document)
            reindexed += 1
        except Exception:
            db.rollback()
            failed += 1
            ensure_knowledge_fts(db)
    faiss = rebuild_faiss_index(db)
    return KnowledgeReindexAllResponse(
        total=len(documents),
        reindexed=reindexed,
        failed=failed,
        faiss=faiss,
    )


def search_knowledge(db: Session, payload: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    ensure_knowledge_fts(db)
    rows = _merge_search_rows(_fts_search(db, payload), _vector_search(db, payload))
    if not rows:
        rows = _fallback_search(db, payload)
    items = [_row_to_search_item(row) for row in rows[: payload.top_k]]
    db.add(
        KnowledgeRetrievalLog(
            query=payload.query,
            filters_json=json.dumps(
                {
                    "symbols": payload.symbols,
                    "doc_types": payload.doc_types,
                    "tags": payload.tags,
                    "top_k": payload.top_k,
                },
                ensure_ascii=False,
            ),
            result_json=json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False),
        )
    )
    db.commit()
    return KnowledgeSearchResponse(query=payload.query, items=items)


def document_read(document: KnowledgeDocument) -> KnowledgeDocumentRead:
    return KnowledgeDocumentRead(
        id=document.id,
        title=document.title,
        doc_type=document.doc_type,
        source=document.source,
        summary=document.summary,
        symbols=_json_list(document.symbols_json),
        tags=_json_list(document.tags_json),
        metadata=_json_dict(document.metadata_json),
        status=document.status,
        enabled=document.enabled,
        chunk_count=document.chunk_count,
        published_at=document.published_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def document_detail(db: Session, document: KnowledgeDocument) -> KnowledgeDocumentDetail:
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document.id)
        .order_by(KnowledgeChunk.chunk_index)
    ).all()
    base = document_read(document).model_dump()
    return KnowledgeDocumentDetail(
        **base,
        content=document.content,
        chunks=[
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "summary": chunk.summary,
                "token_count": chunk.token_count,
                "metadata": _json_dict(chunk.metadata_json),
            }
            for chunk in chunks
        ],
    )


def _replace_chunks(db: Session, document: KnowledgeDocument) -> None:
    db.execute(delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == document.id))
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    db.execute(text("DELETE FROM knowledge_chunks_fts WHERE document_id = :document_id"), {"document_id": document.id})
    chunks = _chunk_text(document.content)
    for index, chunk_text in enumerate(chunks):
        chunk = KnowledgeChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk_text,
            summary=_summarize(chunk_text, max_chars=120),
            token_count=max(len(chunk_text) // 2, 1),
            content_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            metadata_json=json.dumps({"chunking": "paragraph_window_v1"}, ensure_ascii=False),
        )
        db.add(chunk)
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO knowledge_chunks_fts(chunk_id, document_id, title, content, tags)
                VALUES (:chunk_id, :document_id, :title, :content, :tags)
                """
            ),
            {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "title": document.title,
                "content": chunk.content,
                "tags": " ".join(_json_list(document.tags_json) + _json_list(document.symbols_json)),
            },
        )
    document.chunk_count = len(chunks)
    document.summary = _summarize(document.content)
    db.add(document)
    db.flush()
    _index_embeddings(db, document.id)


def _index_embeddings(db: Session, document_id: int) -> None:
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document_id)
        .order_by(KnowledgeChunk.chunk_index)
    ).all()
    if not chunks:
        return
    try:
        vectors = embed_texts([chunk.content for chunk in chunks])
    except EmbeddingError:
        return
    for chunk, vector in zip(chunks, vectors):
        db.add(
            KnowledgeEmbedding(
                chunk_id=chunk.id,
                document_id=document_id,
                model=settings.embedding_model,
                dimension=len(vector),
                vector_json=json.dumps(vector),
            )
        )


def _fts_search(db: Session, payload: KnowledgeSearchRequest) -> list[dict[str, Any]]:
    terms = _fts_query(payload.query)
    if not terms:
        return []
    try:
        rows = db.execute(
            text(
                """
                SELECT c.id AS chunk_id, c.document_id, c.content, c.summary, c.metadata_json,
                       d.title, d.source, d.doc_type, d.symbols_json, d.tags_json,
                       bm25(knowledge_chunks_fts) AS rank
                FROM knowledge_chunks_fts
                JOIN knowledge_chunks c ON c.id = knowledge_chunks_fts.chunk_id
                JOIN knowledge_documents d ON d.id = c.document_id
                WHERE knowledge_chunks_fts MATCH :query AND d.enabled = 1
                ORDER BY rank
                LIMIT :limit
                """
            ),
            {"query": terms, "limit": max(payload.top_k * 4, 20)},
        ).mappings()
    except Exception:
        return []
    return _filter_rows([dict(row) for row in rows], payload)


def _fallback_search(db: Session, payload: KnowledgeSearchRequest) -> list[dict[str, Any]]:
    chunks = db.execute(
        text(
            """
            SELECT c.id AS chunk_id, c.document_id, c.content, c.summary, c.metadata_json,
                   d.title, d.source, d.doc_type, d.symbols_json, d.tags_json
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE d.enabled = 1
            LIMIT 500
            """
        )
    ).mappings()
    keywords = _keywords(payload.query)
    rows = []
    for row in chunks:
        data = dict(row)
        haystack = f"{data['title']} {data['content']} {' '.join(_json_list(data['tags_json']))}"
        score = sum(1 for keyword in keywords if keyword.lower() in haystack.lower())
        if score > 0:
            data["rank"] = -float(score)
            rows.append(data)
    return _filter_rows(sorted(rows, key=lambda item: item["rank"]), payload)


def _vector_search(db: Session, payload: KnowledgeSearchRequest) -> list[dict[str, Any]]:
    try:
        query_vector = embed_texts([payload.query])[0]
    except (EmbeddingError, IndexError):
        return []
    faiss_rows = _faiss_vector_search(db, payload, query_vector)
    if faiss_rows:
        return faiss_rows
    return _sqlite_vector_search(db, payload, query_vector)


def _faiss_vector_search(
    db: Session,
    payload: KnowledgeSearchRequest,
    query_vector: list[float],
) -> list[dict[str, Any]]:
    hits = search_faiss(query_vector, max(payload.top_k * 4, 20))
    if not hits:
        return []
    score_by_chunk_id = {int(hit["chunk_id"]): float(hit.get("vector_score") or 0.0) for hit in hits}
    rows = db.execute(
        select(
            KnowledgeChunk.id.label("chunk_id"),
            KnowledgeChunk.document_id,
            KnowledgeChunk.content,
            KnowledgeChunk.summary,
            KnowledgeChunk.metadata_json,
            KnowledgeDocument.title,
            KnowledgeDocument.source,
            KnowledgeDocument.doc_type,
            KnowledgeDocument.symbols_json,
            KnowledgeDocument.tags_json,
        )
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.enabled.is_(True), KnowledgeChunk.id.in_(score_by_chunk_id))
    ).mappings()
    scored: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        similarity = score_by_chunk_id.get(int(data["chunk_id"]), 0.0)
        data["rank"] = -similarity
        data["vector_score"] = similarity
        scored.append(data)
    return _filter_rows(sorted(scored, key=lambda item: item["rank"]), payload)


def _sqlite_vector_search(
    db: Session,
    payload: KnowledgeSearchRequest,
    query_vector: list[float],
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT c.id AS chunk_id, c.document_id, c.content, c.summary, c.metadata_json,
                   d.title, d.source, d.doc_type, d.symbols_json, d.tags_json,
                   e.vector_json
            FROM knowledge_embeddings e
            JOIN knowledge_chunks c ON c.id = e.chunk_id
            JOIN knowledge_documents d ON d.id = c.document_id
            WHERE d.enabled = 1 AND e.model = :model
            LIMIT 1000
            """
        ),
        {"model": settings.embedding_model},
    ).mappings()
    scored: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        vector = _json_float_list(data.pop("vector_json", "[]"))
        if not vector:
            continue
        similarity = _cosine_similarity(query_vector, vector)
        data["rank"] = -similarity
        data["vector_score"] = similarity
        scored.append(data)
    return _filter_rows(sorted(scored, key=lambda item: item["rank"]), payload)


def _merge_search_rows(
    fts_rows: list[dict[str, Any]],
    vector_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(fts_rows):
        item = dict(row)
        item["hybrid_score"] = item.get("hybrid_score", 0.0) + 1.0 / (index + 1)
        merged[int(item["chunk_id"])] = item
    for index, row in enumerate(vector_rows):
        chunk_id = int(row["chunk_id"])
        item = merged.get(chunk_id, dict(row))
        item["hybrid_score"] = item.get("hybrid_score", 0.0) + 1.2 / (index + 1)
        if "vector_score" in row:
            item["vector_score"] = row["vector_score"]
        merged[chunk_id] = item
    return sorted(merged.values(), key=lambda item: item.get("hybrid_score", 0.0), reverse=True)


def _filter_rows(rows: list[dict[str, Any]], payload: KnowledgeSearchRequest) -> list[dict[str, Any]]:
    result = []
    symbols = set(_normalize_list(payload.symbols))
    doc_types = set(_normalize_list(payload.doc_types))
    tags = set(_normalize_list(payload.tags))
    for row in rows:
        row_symbols = set(_json_list(row["symbols_json"]))
        row_tags = set(_json_list(row["tags_json"]))
        if symbols and not (symbols & row_symbols):
            continue
        if doc_types and row["doc_type"] not in doc_types:
            continue
        if tags and not (tags & row_tags):
            continue
        result.append(row)
    return result


def _row_to_search_item(row: dict[str, Any]) -> KnowledgeSearchItem:
    rank = float(row.get("rank", 0) or 0)
    if "hybrid_score" in row:
        score = round(min(float(row["hybrid_score"]), 1.0), 4)
    else:
        score = round(1 / (1 + max(rank, 0)), 4) if rank >= 0 else round(min(abs(rank), 10) / 10, 4)
    return KnowledgeSearchItem(
        chunk_id=int(row["chunk_id"]),
        document_id=int(row["document_id"]),
        title=str(row["title"]),
        snippet=_snippet(str(row["content"])),
        score=score,
        source=str(row["source"]),
        doc_type=str(row["doc_type"]),
        symbols=_json_list(row["symbols_json"]),
        tags=_json_list(row["tags_json"]),
        citation=f"doc:{row['document_id']}#chunk:{row['chunk_id']}",
        metadata=_json_dict(row.get("metadata_json", "{}")),
    )


def _chunk_text(content: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [content.strip()]:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        prefix = current[-overlap:] if overlap and current else ""
        current = f"{prefix}\n\n{paragraph}".strip() if prefix else paragraph
    if current:
        chunks.append(current)
    return chunks or [content[:max_chars]]


def _summarize(content: str, max_chars: int = 180) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    return compact[:max_chars]


def _snippet(content: str, max_chars: int = 260) -> str:
    return _summarize(content, max_chars=max_chars)


def _fts_query(query: str) -> str:
    keywords = _keywords(query)
    return " OR ".join(keywords[:8])


def _keywords(query: str) -> list[str]:
    keywords: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", query):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) <= 4:
                keywords.append(token)
            keywords.extend(token[index : index + 2] for index in range(0, max(len(token) - 1, 0)))
        else:
            keywords.append(token)
    deduped: list[str] = []
    for keyword in keywords:
        if keyword and keyword not in deduped:
            deduped.append(keyword)
    return deduped


def _normalize_list(items: list[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_float_list(value: str) -> list[float]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [float(item) for item in parsed]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
