from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.data_source import DataSnapshot
from app.schemas.data_source import DataSnapshotCreateRequest, DataSnapshotRead
from app.schemas.knowledge import KnowledgeSearchRequest
from app.services.data_fetcher import DataFetchError, get_klines, get_market_news, get_realtime_quote
from app.services.knowledge_base import search_knowledge
from app.services.technical_indicators import calculate_indicators


def create_analysis_snapshot(
    db: Session,
    payload: DataSnapshotCreateRequest,
    query: str = "",
    include_knowledge: bool = False,
) -> DataSnapshotRead:
    symbol = _normalize_symbol(payload.symbol)
    snapshot_payload: dict[str, Any] = {
        "symbol": symbol,
        "period": payload.period,
        "query": query,
        "quote": None,
        "kline": None,
        "indicators": None,
        "market_news": None,
        "knowledge_context": None,
        "warnings": [],
    }

    if symbol:
        try:
            snapshot_payload["quote"] = get_realtime_quote(db, symbol).model_dump(mode="json")
        except DataFetchError as exc:
            snapshot_payload["warnings"].append({"stage": "quote", "message": str(exc)})

        try:
            kline = get_klines(db, symbol=symbol, period=payload.period, limit=payload.limit)
            snapshot_payload["kline"] = kline.model_dump(mode="json")
            snapshot_payload["indicators"] = calculate_indicators(
                kline,
                ["ma", "macd", "rsi", "kdj", "boll"],
            ).model_dump(mode="json")
        except DataFetchError as exc:
            snapshot_payload["warnings"].append({"stage": "kline", "message": str(exc)})

    try:
        snapshot_payload["market_news"] = get_market_news(db, limit=payload.news_limit).model_dump(mode="json")
    except DataFetchError as exc:
        snapshot_payload["warnings"].append({"stage": "market_news", "message": str(exc)})

    if include_knowledge and query.strip():
        try:
            snapshot_payload["knowledge_context"] = search_knowledge(
                db,
                KnowledgeSearchRequest(
                    query=query,
                    symbols=[symbol] if symbol else [],
                    top_k=8,
                    require_citations=True,
                ),
            ).model_dump(mode="json")
        except Exception as exc:
            snapshot_payload["warnings"].append({"stage": "knowledge_context", "message": str(exc)})

    snapshot = DataSnapshot(
        symbol=symbol,
        period=payload.period,
        snapshot_type="analysis_context",
        snapshot_json=json.dumps(snapshot_payload, ensure_ascii=False),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return DataSnapshotRead.model_validate(snapshot)


def snapshot_brief(snapshot: DataSnapshotRead | None) -> str:
    if not snapshot:
        return "未生成数据快照"
    try:
        data = json.loads(snapshot.snapshot_json)
    except json.JSONDecodeError:
        return f"snapshot:{snapshot.id}"
    quote = data.get("quote") or {}
    indicators = data.get("indicators") or {}
    news = data.get("market_news") or {}
    knowledge = data.get("knowledge_context") or {}
    parts = [f"snapshot:{snapshot.id}", f"period:{snapshot.period}"]
    if snapshot.symbol:
        parts.insert(1, f"symbol:{snapshot.symbol}")
    if quote:
        parts.append(f"price:{quote.get('price')}")
        parts.append(f"quote_provider:{quote.get('provider_key')}")
    if indicators:
        parts.append(f"indicators:{len(indicators.get('items') or [])}")
    if news:
        parts.append(f"news:{len(news.get('items') or [])}")
    if knowledge:
        parts.append(f"knowledge:{len(knowledge.get('items') or [])}")
    warnings = data.get("warnings") or []
    if warnings:
        parts.append(f"warnings:{len(warnings)}")
    return " | ".join(parts)


def _normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :]
    return cleaned
