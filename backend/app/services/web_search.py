from __future__ import annotations

import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataFetchLog, DataProvider, DataProviderCredential, DataRoute


class WebSearchError(RuntimeError):
    pass


def search_web(db: Session, payload: dict[str, Any], *, finance: bool) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        raise WebSearchError("搜索关键词不能为空。")
    limit = min(max(int(payload.get("limit") or 8), 1), 20)
    recency_days = min(max(int(payload.get("recency_days") or (7 if finance else 30)), 1), 3650)
    domains = [str(item).strip() for item in payload.get("domains") or [] if str(item).strip()]
    language = str(payload.get("language") or "zh-CN").strip()
    symbol = str(payload.get("symbol") or "").strip() if finance else ""
    effective_query = " ".join(part for part in (symbol, query) if part)
    route_key = "finance_web_search" if finance else "web_search"
    chain = _provider_chain(db, route_key)
    errors: list[str] = []

    for provider_key in chain:
        provider = db.scalar(select(DataProvider).where(DataProvider.key == provider_key))
        if not provider or not provider.enabled:
            errors.append(f"{provider_key}:未启用")
            continue
        api_key = _api_key(db, provider.key)
        if not api_key:
            errors.append(f"{provider.key}:缺少 API Key")
            continue
        started = perf_counter()
        try:
            if provider.key == "bocha_search":
                raw_items = _search_bocha(provider, api_key, effective_query, limit, recency_days, domains)
            elif provider.key == "tavily_search":
                raw_items = _search_tavily(provider, api_key, effective_query, limit, recency_days, domains, finance)
            else:
                raise WebSearchError(f"未实现搜索数据源：{provider.key}")
            items = [_normalize_result(item, provider.key, finance) for item in raw_items]
            items = [item for item in items if item["title"] and item["url"]]
            if finance:
                items.sort(key=lambda item: (item["authority_level"], item["score"]), reverse=True)
            _record_fetch(db, provider.key, route_key, "success", started)
            return {
                "query": query,
                "effective_query": effective_query,
                "search_type": "finance" if finance else "web",
                "provider_key": provider.key,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "language": language,
                "items": items[:limit],
                "warnings": errors,
            }
        except (httpx.HTTPError, WebSearchError, ValueError, KeyError) as exc:
            errors.append(f"{provider.key}:{exc}")
            _record_fetch(db, provider.key, route_key, "failed", started, str(exc))

    raise WebSearchError("联网搜索不可用：" + "；".join(errors or ["没有配置搜索数据源"]))


def _provider_chain(db: Session, route_key: str) -> list[str]:
    route = db.scalar(select(DataRoute).where(DataRoute.data_category == route_key))
    if not route or not route.enabled:
        return []
    try:
        parsed = json.loads(route.provider_chain_json)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _api_key(db: Session, provider_key: str) -> str:
    credential = db.scalar(
        select(DataProviderCredential)
        .where(DataProviderCredential.provider_key == provider_key)
        .order_by(DataProviderCredential.id)
    )
    return credential.encrypted_value.strip() if credential else ""


def _search_bocha(
    provider: DataProvider,
    api_key: str,
    query: str,
    limit: int,
    recency_days: int,
    domains: list[str],
) -> list[dict[str, Any]]:
    freshness = "oneWeek" if recency_days <= 7 else "oneMonth" if recency_days <= 31 else "oneYear"
    scoped_query = query + (" site:" + " OR site:".join(domains) if domains else "")
    response = httpx.post(
        provider.base_url.rstrip("/") + "/v1/web-search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"query": scoped_query, "freshness": freshness, "summary": True, "count": limit},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("code") not in (None, 200):
        raise WebSearchError(str(data.get("msg") or data.get("message") or "博查搜索失败"))
    values = (((data.get("data") or {}).get("webPages") or {}).get("value") or [])
    return [item for item in values if isinstance(item, dict)]


def _search_tavily(
    provider: DataProvider,
    api_key: str,
    query: str,
    limit: int,
    recency_days: int,
    domains: list[str],
    finance: bool,
) -> list[dict[str, Any]]:
    response = httpx.post(
        provider.base_url.rstrip("/") + "/search",
        json={
            "api_key": api_key,
            "query": query,
            "topic": "news" if finance else "general",
            "search_depth": "advanced",
            "max_results": limit,
            "days": recency_days,
            "include_domains": domains,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    return [item for item in response.json().get("results") or [] if isinstance(item, dict)]


def _normalize_result(item: dict[str, Any], provider_key: str, finance: bool) -> dict[str, Any]:
    title = str(item.get("title") or item.get("name") or "").strip()
    url = str(item.get("url") or "").strip()
    content = str(item.get("content") or item.get("summary") or item.get("snippet") or "").strip()
    published_at = str(item.get("published_date") or item.get("datePublished") or "").strip()
    score = float(item.get("score") or 0)
    source_type, authority_level = _classify_source(url, title) if finance else ("web", 1)
    return {
        "title": title,
        "url": url,
        "snippet": content,
        "published_at": published_at,
        "provider": provider_key,
        "source_type": source_type,
        "authority_level": authority_level,
        "score": score,
    }


def _classify_source(url: str, title: str) -> tuple[str, int]:
    value = (url + " " + title).lower()
    if any(domain in value for domain in ("cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn")):
        return "official_disclosure", 5
    if any(marker in value for marker in ("股份有限公司", "集团有限公司", "官网", "official")):
        return "company_official", 4
    if any(domain in value for domain in ("eastmoney.com", "cls.cn", "stcn.com", "cnstock.com", "yicai.com")):
        return "financial_media", 3
    if any(marker in value for marker in ("证券", "研报", "研究报告")):
        return "research_opinion", 2
    return "web", 1


def _record_fetch(
    db: Session,
    provider_key: str,
    category: str,
    status: str,
    started: float,
    error: str = "",
) -> None:
    db.add(DataFetchLog(
        provider_key=provider_key,
        data_category=category,
        tool_name="finance.search" if category == "finance_web_search" else "web.search",
        status=status,
        latency_ms=int((perf_counter() - started) * 1000),
        error_type="search_error" if error else "",
        error_message=error,
    ))
    db.commit()
