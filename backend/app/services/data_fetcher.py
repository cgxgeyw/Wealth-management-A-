import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Callable

import httpx
from html import unescape
import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataContentRecord, DataFetchLog, DataProvider, DataRoute
from app.schemas.data_source import (
    AnnouncementItem,
    AnnouncementResponse,
    DragonTigerItem,
    DragonTigerResponse,
    FinancialStatementResponse,
    FinancialStatementRow,
    FundamentalMetric,
    FundamentalResponse,
    FundFlowItem,
    FundFlowResponse,
    KlineBar,
    KlineResponse,
    LockupExpiryItem,
    LockupExpiryResponse,
    MacroIndicatorItem,
    MacroIndicatorResponse,
    MarginTradingItem,
    MarginTradingResponse,
    NorthboundFlowItem,
    NorthboundFlowResponse,
    NewsItem,
    NewsResponse,
    RealtimeQuote,
    ResearchReportItem,
    ResearchReportResponse,
    SectorSnapshotItem,
    SectorSnapshotResponse,
)
from app.services.cache_policy import resolve_cache_ttl


class DataFetchError(RuntimeError):
    def __init__(self, message: str, error_type: str = "fetch_error") -> None:
        super().__init__(message)
        self.error_type = error_type


@dataclass
class CacheEntry:
    expires_at: float
    value: Any


_CACHE: dict[str, CacheEntry] = {}


PERIOD_TO_KLT = {
    "daily": "101",
    "day": "101",
    "1d": "101",
    "weekly": "102",
    "week": "102",
    "monthly": "103",
    "month": "103",
    "1m": "1",
    "1min": "1",
    "5m": "5",
    "5min": "5",
    "15m": "15",
    "30m": "30",
    "60m": "60",
}


def get_realtime_quote(db: Session, symbol: str) -> RealtimeQuote:
    return _fetch_with_route(db, "realtime_quote", symbol, {"symbol": _normalize_symbol(symbol)})


def get_klines(
    db: Session,
    symbol: str,
    period: str = "daily",
    limit: int = 120,
    adjust: str = "qfq",
) -> KlineResponse:
    normalized_period = period.lower()
    if normalized_period not in PERIOD_TO_KLT:
        raise DataFetchError(f"不支持的 K 线周期：{period}", "invalid_period")
    params = {
        "symbol": _normalize_symbol(symbol),
        "period": normalized_period,
        "limit": min(max(limit, 1), 800),
        "adjust": adjust,
    }
    category = "minute_kline" if PERIOD_TO_KLT[normalized_period] in {"1", "5", "15", "30", "60"} else "daily_kline"
    return _fetch_with_route(db, category, symbol, params)


def get_market_news(db: Session, limit: int = 30) -> NewsResponse:
    return _fetch_with_route(db, "market_news", "", {"limit": min(max(limit, 1), 100)})


def get_company_news(db: Session, symbol: str, limit: int = 30) -> NewsResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db, "company_news", normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 100)},
    )


def get_announcements(db: Session, symbol: str, limit: int = 20) -> AnnouncementResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db,
        "announcement",
        normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 100)},
    )


def get_fundamentals(db: Session, symbol: str) -> FundamentalResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(db, "fundamental_snapshot", normalized_symbol, {"symbol": normalized_symbol})


def get_financial_statements(
    db: Session,
    symbol: str,
    statement_type: str = "income",
    limit: int = 4,
) -> FinancialStatementResponse:
    normalized_symbol = _normalize_symbol(symbol)
    normalized_type = statement_type.lower()
    if normalized_type not in {"income", "balance", "cashflow"}:
        raise DataFetchError(f"不支持的财务报表类型：{statement_type}", "invalid_statement_type")
    return _fetch_with_route(
        db,
        "financial_statement",
        normalized_symbol,
        {"symbol": normalized_symbol, "statement_type": normalized_type, "limit": min(max(limit, 1), 20)},
    )


def get_fund_flow(db: Session, symbol: str, limit: int = 20) -> FundFlowResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db,
        "fund_flow",
        normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 120)},
    )


def get_sector_snapshots(db: Session, sector_type: str = "industry", limit: int = 20) -> SectorSnapshotResponse:
    normalized_type = sector_type.lower()
    if normalized_type not in {"industry", "concept"}:
        raise DataFetchError(f"不支持的板块类型：{sector_type}", "invalid_sector_type")
    return _fetch_with_route(
        db,
        "sector_snapshot",
        "",
        {"sector_type": normalized_type, "limit": min(max(limit, 1), 100)},
    )


def get_northbound_flow(db: Session, limit: int = 20) -> NorthboundFlowResponse:
    normalized_limit = min(max(limit, 1), 100)
    try:
        return _fetch_with_route(db, "northbound_flow", "", {"limit": normalized_limit})
    except DataFetchError as exc:
        cached = _northbound_from_archive(db, normalized_limit)
        if cached is None:
            raise exc
        return cached


def get_research_reports(db: Session, symbol: str, limit: int = 10) -> ResearchReportResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db,
        "research_report",
        normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 50)},
    )


def get_dragon_tiger(db: Session, symbol: str, limit: int = 10) -> DragonTigerResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db,
        "dragon_tiger",
        normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 50)},
    )


def get_lockup_expiry(db: Session, symbol: str, limit: int = 10) -> LockupExpiryResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db,
        "lockup_expiry",
        normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 50)},
    )


def get_margin_trading(db: Session, symbol: str, limit: int = 10) -> MarginTradingResponse:
    normalized_symbol = _normalize_symbol(symbol)
    return _fetch_with_route(
        db,
        "margin_trading",
        normalized_symbol,
        {"symbol": normalized_symbol, "limit": min(max(limit, 1), 120)},
    )


def get_macro_indicator(db: Session, indicator: str = "cpi", limit: int = 12) -> MacroIndicatorResponse:
    normalized_indicator = indicator.lower()
    if normalized_indicator not in {"cpi", "pmi"}:
        raise DataFetchError(f"不支持的宏观指标：{indicator}", "invalid_macro_indicator")
    return _fetch_with_route(
        db,
        "macro_indicator",
        "",
        {"indicator": normalized_indicator, "limit": min(max(limit, 1), 120)},
    )


def clear_runtime_cache() -> None:
    _CACHE.clear()


def _fetch_with_route(db: Session, data_category: str, symbol: str, params: dict[str, Any]) -> Any:
    route = db.scalar(select(DataRoute).where(DataRoute.data_category == data_category))
    if not route or not route.enabled:
        raise DataFetchError(f"数据路由未启用：{data_category}", "route_disabled")

    try:
        provider_chain = json.loads(route.provider_chain_json)
    except json.JSONDecodeError as exc:
        raise DataFetchError("数据路由配置不是合法 JSON。", "bad_route_config") from exc

    last_error: DataFetchError | None = None
    for index, provider_key in enumerate(provider_chain):
        provider = db.scalar(select(DataProvider).where(DataProvider.key == provider_key))
        if not provider or not provider.enabled:
            continue
        try:
            return _fetch_with_provider(
                db=db,
                provider=provider,
                data_category=data_category,
                symbol=symbol,
                params=params,
                fallback_used=index > 0,
            )
        except DataFetchError as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    raise DataFetchError(f"没有可用数据源：{data_category}", "no_provider")


def _fetch_with_provider(
    db: Session,
    provider: DataProvider,
    data_category: str,
    symbol: str,
    params: dict[str, Any],
    fallback_used: bool,
) -> Any:
    fetcher = _resolve_fetcher(provider.key, data_category)
    cache_key = _cache_key(provider.key, data_category, params)
    now_ts = perf_counter()
    cached = _CACHE.get(cache_key)
    if cached and cached.expires_at > now_ts:
        _log_fetch(
            db=db,
            provider=provider,
            data_category=data_category,
            symbol=symbol,
            status="success",
            latency_ms=0,
            cache_hit=True,
            fallback_used=fallback_used,
        )
        return cached.value

    started = perf_counter()
    try:
        value = fetcher(provider, params)
        _persist_content_records(db, value)
        latency_ms = int((perf_counter() - started) * 1000)
        _CACHE[cache_key] = CacheEntry(
            expires_at=perf_counter() + resolve_cache_ttl(data_category, provider.cache_ttl_seconds),
            value=value,
        )
        _log_fetch(
            db=db,
            provider=provider,
            data_category=data_category,
            symbol=symbol,
            status="success",
            latency_ms=latency_ms,
            cache_hit=False,
            fallback_used=fallback_used,
        )
        return value
    except httpx.TimeoutException as exc:
        _record_failure(db, provider, data_category, symbol, "timeout", str(exc), fallback_used)
        raise DataFetchError(str(exc), "timeout") from exc
    except httpx.HTTPError as exc:
        _record_failure(db, provider, data_category, symbol, "http_error", str(exc), fallback_used)
        raise DataFetchError(str(exc), "http_error") from exc
    except (KeyError, ValueError, TypeError) as exc:
        _record_failure(db, provider, data_category, symbol, "parse_error", str(exc), fallback_used)
        raise DataFetchError(str(exc), "parse_error") from exc


def _resolve_fetcher(provider_key: str, data_category: str) -> Callable[[DataProvider, dict[str, Any]], Any]:
    if provider_key == "tencent_quote" and data_category == "realtime_quote":
        return _fetch_tencent_quote
    if provider_key == "eastmoney_push2his" and data_category in {"daily_kline", "minute_kline"}:
        return _fetch_eastmoney_kline
    if provider_key == "sina_kline" and data_category in {"daily_kline", "minute_kline"}:
        return _fetch_sina_kline
    if provider_key == "cls" and data_category == "market_news":
        return _fetch_cls_news
    if provider_key == "sina_stock_news" and data_category == "company_news":
        return _fetch_sina_stock_news
    if provider_key == "eastmoney_announcement" and data_category == "announcement":
        return _fetch_eastmoney_announcements
    if provider_key == "cninfo_announcement" and data_category == "announcement":
        return _fetch_cninfo_announcements
    if provider_key == "eastmoney_push2" and data_category == "fundamental_snapshot":
        return _fetch_eastmoney_fundamentals
    if provider_key == "tencent_quote" and data_category == "fundamental_snapshot":
        return _fetch_tencent_fundamentals
    if provider_key == "eastmoney_datacenter" and data_category == "financial_statement":
        return _fetch_eastmoney_financial_statement
    if provider_key == "eastmoney_push2" and data_category == "fund_flow":
        return _fetch_eastmoney_fund_flow
    if provider_key == "eastmoney_push2" and data_category == "sector_snapshot":
        return _fetch_eastmoney_sector_snapshots
    if provider_key == "eastmoney_datacenter" and data_category == "northbound_flow":
        return _fetch_eastmoney_northbound_flow
    if provider_key == "eastmoney_reportapi" and data_category == "research_report":
        return _fetch_eastmoney_research_reports
    if provider_key == "eastmoney_datacenter" and data_category == "dragon_tiger":
        return _fetch_eastmoney_dragon_tiger
    if provider_key == "eastmoney_datacenter" and data_category == "lockup_expiry":
        return _fetch_eastmoney_lockup_expiry
    if provider_key == "eastmoney_datacenter" and data_category == "margin_trading":
        return _fetch_eastmoney_margin_trading
    if provider_key == "eastmoney_datacenter" and data_category == "macro_indicator":
        return _fetch_eastmoney_macro_indicator
    raise DataFetchError(f"{provider_key} 暂不支持 {data_category}", "unsupported_provider")


def _fetch_tencent_quote(provider: DataProvider, params: dict[str, Any]) -> RealtimeQuote:
    symbol = params["symbol"]
    qt_symbol = _to_tencent_symbol(symbol)
    url = f"{provider.base_url}/q={qt_symbol}"
    text = _http_get_text(url, encoding="gbk")
    if '="' not in text:
        raise ValueError("腾讯行情返回格式异常。")
    raw = text.split('="', 1)[1].rsplit('";', 1)[0]
    parts = raw.split("~")
    if len(parts) < 35:
        raise ValueError("腾讯行情字段不足。")
    return RealtimeQuote(
        symbol=parts[2] or symbol,
        name=parts[1],
        price=_to_float(parts[3]),
        pre_close=_to_float(parts[4]),
        open=_to_float(parts[5]),
        volume=_to_float(parts[6]),
        timestamp=parts[30] if len(parts) > 30 else "",
        change=_to_float(parts[31]) if len(parts) > 31 else None,
        change_percent=_to_float(parts[32]) if len(parts) > 32 else None,
        high=_to_float(parts[33]) if len(parts) > 33 else None,
        low=_to_float(parts[34]) if len(parts) > 34 else None,
        turnover_rate=_to_float(parts[38]) if len(parts) > 38 else None,
        amount=_to_float(parts[37]) if len(parts) > 37 else None,
        pe_ttm=_to_float(parts[39]) if len(parts) > 39 else None,
        pb=_to_float(parts[46]) if len(parts) > 46 else None,
        market_cap=_to_float(parts[45]) if len(parts) > 45 else None,
        provider_key=provider.key,
    )


def _fetch_eastmoney_kline(provider: DataProvider, params: dict[str, Any]) -> KlineResponse:
    symbol = params["symbol"]
    secid = _to_eastmoney_secid(symbol)
    klt = PERIOD_TO_KLT[params["period"]]
    fqt = {"none": "0", "qfq": "1", "hfq": "2"}.get(params.get("adjust", "qfq"), "1")
    limit = int(params["limit"])
    url = (
        f"{provider.base_url}/api/qt/stock/kline/get"
        "?fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&secid={secid}&klt={klt}&fqt={fqt}&beg=0&end=20500101"
    )
    payload = _http_get_json(url)
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    bars = [_parse_eastmoney_bar(item) for item in klines[-limit:]]
    return KlineResponse(
        symbol=symbol,
        name=data.get("name") or "",
        period=params["period"],
        provider_key=provider.key,
        items=bars,
    )


def _fetch_sina_kline(provider: DataProvider, params: dict[str, Any]) -> KlineResponse:
    symbol = params["symbol"]
    scale = _to_sina_scale(params["period"])
    limit = int(params["limit"])
    sina_symbol = _to_tencent_symbol(symbol)
    url = (
        f"{provider.base_url}/cn/api/json_v2.php/CN_MarketData.getKLineData"
        f"?symbol={sina_symbol}&scale={scale}&ma=no&datalen={limit}"
    )
    payload = _http_get_json(url)
    if not isinstance(payload, list):
        raise ValueError("新浪 K 线返回格式异常。")
    bars = [
        KlineBar(
            time=str(item["day"]),
            open=float(item["open"]),
            close=float(item["close"]),
            high=float(item["high"]),
            low=float(item["low"]),
            volume=float(item["volume"]),
            amount=0.0,
        )
        for item in payload
    ]
    return KlineResponse(
        symbol=symbol,
        name="",
        period=params["period"],
        provider_key=provider.key,
        items=bars,
    )


def _fetch_cls_news(provider: DataProvider, params: dict[str, Any]) -> NewsResponse:
    limit = int(params["limit"])
    url = f"{provider.base_url}/api/cache?app=CailianpressWeb&name=telegraph&os=web&sv=8.7.9"
    payload = _http_get_json(url, headers={"Referer": "https://www.cls.cn/telegraph"})
    rows = ((payload.get("data") or {}).get("roll_data") or [])[:limit]
    items: list[NewsItem] = []
    for row in rows:
        ctime = row.get("ctime")
        publish_time = ""
        if isinstance(ctime, int | float):
            publish_time = datetime.fromtimestamp(ctime, tz=timezone.utc).isoformat()
        stock_list = row.get("stock_list") or []
        related_stocks = [
            str(item.get("symbol") or item.get("code") or "")
            for item in stock_list
            if isinstance(item, dict)
        ]
        news_id = str(row.get("id") or "")
        items.append(
            NewsItem(
                id=news_id,
                title=row.get("title") or "",
                content=row.get("brief") or row.get("content") or "",
                source="财联社",
                publish_time=publish_time,
                level=row.get("level") or "",
                related_stocks=[item for item in related_stocks if item],
                url=f"https://www.cls.cn/detail/{news_id}" if news_id else "",
            )
        )
    return NewsResponse(provider_key=provider.key, items=items)


def _fetch_sina_stock_news(provider: DataProvider, params: dict[str, Any]) -> NewsResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    url = f"{provider.base_url}/corp/go.php/vCB_AllNewsStock/symbol/{_to_tencent_symbol(symbol)}.phtml"
    text = _http_get_text(url, encoding="gb18030")
    pattern = re.compile(
        r"(?P<date>20\d{2}-\d{2}-\d{2})\s*&nbsp;\s*(?P<time>\d{2}:\d{2})"
        r".*?<a[^>]+href=['\"](?P<url>[^'\"]+)['\"][^>]*>(?P<title>.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    items: list[NewsItem] = []
    for match in pattern.finditer(text):
        title = re.sub(r"<[^>]+>", "", unescape(match.group("title"))).strip()
        if not title:
            continue
        article_url = unescape(match.group("url")).strip()
        news_id = article_url.rsplit("/", 1)[-1].split("?", 1)[0] or f"{symbol}-{len(items)}"
        items.append(NewsItem(
            id=news_id,
            title=title,
            source="新浪财经",
            publish_time=f"{match.group('date')} {match.group('time')}",
            related_stocks=[symbol],
            url=article_url,
        ))
        if len(items) >= limit:
            break
    if not items:
        raise ValueError("新浪个股资讯未返回可解析新闻。")
    return NewsResponse(provider_key=provider.key, items=items)


def _fetch_eastmoney_announcements(
    provider: DataProvider,
    params: dict[str, Any],
) -> AnnouncementResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    url = (
        f"{provider.base_url}/api/security/ann"
        f"?sr=-1&page_size={limit}&page_index=1"
        "&ann_type=A&client_source=web"
        f"&stock_list={symbol}"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("data") or {}).get("list") or [])[:limit]
    items: list[AnnouncementItem] = []
    for row in rows:
        art_code = str(row.get("art_code") or "")
        codes = row.get("codes") or []
        columns = row.get("columns") or []
        row_symbol = symbol
        if codes and isinstance(codes[0], dict):
            row_symbol = str(codes[0].get("stock_code") or symbol)
        category = ""
        if columns and isinstance(columns[0], dict):
            category = str(columns[0].get("column_name") or "")
        items.append(
            AnnouncementItem(
                id=art_code,
                symbol=row_symbol,
                title=row.get("title_ch") or row.get("title") or "",
                publish_time=row.get("display_time") or row.get("notice_date") or "",
                category=category,
                source="东方财富",
                url=(
                    f"https://data.eastmoney.com/notices/detail/{row_symbol}/{art_code}.html"
                    if art_code
                    else ""
                ),
            )
        )
    return AnnouncementResponse(symbol=symbol, provider_key=provider.key, items=items)


def _fetch_cninfo_announcements(provider: DataProvider, params: dict[str, Any]) -> AnnouncementResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    plate = "sse" if symbol.startswith(("5", "6", "9")) else "szse"
    payload = _http_post_json(
        f"{provider.base_url}/new/hisAnnouncement/query",
        {
            "stock": symbol,
            "tabName": "fulltext",
            "pageSize": str(limit),
            "pageNum": "1",
            "column": plate,
            "category": "",
            "plate": plate,
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
        headers={"Referer": "https://www.cninfo.com.cn/"},
    )
    items: list[AnnouncementItem] = []
    for row in (payload.get("announcements") or [])[:limit]:
        adjunct_url = str(row.get("adjunctUrl") or "")
        announcement_id = str(row.get("announcementId") or adjunct_url or "")
        items.append(AnnouncementItem(
            id=announcement_id,
            symbol=symbol,
            title=str(row.get("announcementTitle") or ""),
            publish_time=str(row.get("announcementTime") or ""),
            category=str(row.get("announcementTypeName") or ""),
            source="巨潮资讯",
            url=f"https://static.cninfo.com.cn/{adjunct_url.lstrip('/')}" if adjunct_url else "",
        ))
    if not items:
        raise ValueError("巨潮资讯未返回公告。")
    return AnnouncementResponse(symbol=symbol, provider_key=provider.key, items=items)


def _fetch_eastmoney_fundamentals(provider: DataProvider, params: dict[str, Any]) -> FundamentalResponse:
    symbol = params["symbol"]
    secid = _to_eastmoney_secid(symbol)
    fields = "f57,f58,f84,f85,f116,f117,f162,f167,f173,f187"
    payload = _http_get_json(f"{provider.base_url}/api/qt/stock/get?secid={secid}&fields={fields}")
    data = payload.get("data") or {}
    metrics = [
        FundamentalMetric(key="total_shares", label="总股本", value=_to_float(data.get("f84")), unit="股"),
        FundamentalMetric(key="float_shares", label="流通股本", value=_to_float(data.get("f85")), unit="股"),
        FundamentalMetric(key="market_cap", label="总市值", value=_to_float(data.get("f116")), unit="元"),
        FundamentalMetric(key="float_market_cap", label="流通市值", value=_to_float(data.get("f117")), unit="元"),
        FundamentalMetric(key="pe_ttm", label="PE(TTM)", value=_to_float(data.get("f162"))),
        FundamentalMetric(key="pb", label="PB", value=_to_float(data.get("f167"))),
        FundamentalMetric(key="roe", label="ROE", value=_to_float(data.get("f173")), unit="%"),
        FundamentalMetric(key="gross_margin", label="销售毛利率", value=_to_float(data.get("f187")), unit="%"),
    ]
    return FundamentalResponse(
        symbol=symbol,
        name=data.get("f58") or "",
        provider_key=provider.key,
        metrics=metrics,
    )


def _fetch_tencent_fundamentals(provider: DataProvider, params: dict[str, Any]) -> FundamentalResponse:
    quote = _fetch_tencent_quote(provider, params)
    return FundamentalResponse(
        symbol=quote.symbol,
        name=quote.name,
        provider_key=provider.key,
        metrics=[
            FundamentalMetric(key="pe_ttm", label="PE(TTM)", value=quote.pe_ttm, unit="倍"),
            FundamentalMetric(key="pb", label="PB", value=quote.pb, unit="倍"),
            FundamentalMetric(key="market_cap", label="总市值", value=quote.market_cap, unit="元"),
            FundamentalMetric(key="turnover_rate", label="换手率", value=quote.turnover_rate, unit="%"),
        ],
    )


def _fetch_eastmoney_financial_statement(
    provider: DataProvider,
    params: dict[str, Any],
) -> FinancialStatementResponse:
    symbol = params["symbol"]
    statement_type = params["statement_type"]
    limit = int(params["limit"])
    report_map = {
        "income": "RPT_DMSK_FN_INCOME",
        "balance": "RPT_DMSK_FN_BALANCE",
        "cashflow": "RPT_DMSK_FN_CASHFLOW",
    }
    url = (
        f"{provider.base_url}/api/data/v1/get"
        f"?reportName={report_map[statement_type]}&columns=ALL"
        f"&filter=(SECURITY_CODE%3D%22{symbol}%22)"
        f"&pageNumber=1&pageSize={limit}&sortColumns=REPORT_DATE&sortTypes=-1"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("result") or {}).get("data") or [])[:limit]
    items: list[FinancialStatementRow] = []
    for row in rows:
        values = {
            key: row.get(key)
            for key in _statement_keys(statement_type)
            if key in row
        }
        items.append(
            FinancialStatementRow(
                report_date=str(row.get("REPORT_DATE") or ""),
                notice_date=str(row.get("NOTICE_DATE") or ""),
                values=values,
            )
        )
    return FinancialStatementResponse(
        symbol=symbol,
        statement_type=statement_type,
        provider_key=provider.key,
        items=items,
    )


def _fetch_eastmoney_fund_flow(provider: DataProvider, params: dict[str, Any]) -> FundFlowResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    secid = _to_eastmoney_secid(symbol)
    url = (
        f"{provider.base_url}/api/qt/stock/fflow/kline/get"
        f"?lmt={limit}&klt=101&secid={secid}"
        "&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"
    )
    payload = _http_get_json(url)
    data = payload.get("data") or {}
    items: list[FundFlowItem] = []
    for raw in (data.get("klines") or [])[-limit:]:
        parts = str(raw).split(",")
        if len(parts) < 6:
            continue
        items.append(
            FundFlowItem(
                date=parts[0],
                main_net_inflow=_to_float(parts[1]),
                small_net_inflow=_to_float(parts[2]),
                medium_net_inflow=_to_float(parts[3]),
                large_net_inflow=_to_float(parts[4]),
                super_large_net_inflow=_to_float(parts[5]),
            )
        )
    return FundFlowResponse(
        symbol=symbol,
        name=data.get("name") or "",
        provider_key=provider.key,
        items=items,
    )


def _fetch_eastmoney_sector_snapshots(
    provider: DataProvider,
    params: dict[str, Any],
) -> SectorSnapshotResponse:
    sector_type = params["sector_type"]
    limit = int(params["limit"])
    fs = "m:90+t:2" if sector_type == "industry" else "m:90+t:3"
    url = (
        f"{provider.base_url}/api/qt/clist/get"
        f"?pn=1&pz={limit}&po=1&np=1&fltt=2&invt=2&fid=f62"
        f"&fs={fs}&fields=f12,f14,f2,f3,f62,f184"
    )
    payload = _http_get_json(url)
    rows = ((payload.get("data") or {}).get("diff") or [])[:limit]
    return SectorSnapshotResponse(
        provider_key=provider.key,
        items=[
            SectorSnapshotItem(
                code=str(row.get("f12") or ""),
                name=str(row.get("f14") or ""),
                price=_to_float(row.get("f2")),
                change_percent=_to_float(row.get("f3")),
                main_net_inflow=_to_float(row.get("f62")),
                main_net_ratio=_to_float(row.get("f184")),
                sector_type=sector_type,
            )
            for row in rows
        ],
    )


def _fetch_eastmoney_northbound_flow(
    provider: DataProvider,
    params: dict[str, Any],
) -> NorthboundFlowResponse:
    limit = int(params["limit"])
    url = (
        f"{provider.base_url}/api/data/v1/get"
        "?reportName=RPT_MUTUAL_DEAL_HISTORY&columns=ALL"
        f"&pageNumber=1&pageSize={limit}&sortColumns=TRADE_DATE&sortTypes=-1"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("result") or {}).get("data") or [])[:limit]
    return NorthboundFlowResponse(
        provider_key=provider.key,
        items=[
            NorthboundFlowItem(
                trade_date=str(row.get("TRADE_DATE") or ""),
                mutual_type=str(row.get("MUTUAL_TYPE") or ""),
                net_deal_amount=_to_float(row.get("NET_DEAL_AMT")),
                buy_amount=_to_float(row.get("BUY_AMT")),
                sell_amount=_to_float(row.get("SELL_AMT")),
                deal_amount=_to_float(row.get("DEAL_AMT")),
                lead_stock_code=str(row.get("LEAD_STOCKS_CODE") or ""),
                lead_stock_name=str(row.get("LEAD_STOCKS_NAME") or ""),
            )
            for row in rows
        ],
    )


def _fetch_eastmoney_research_reports(
    provider: DataProvider,
    params: dict[str, Any],
) -> ResearchReportResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    end_date = datetime.now(timezone.utc).date()
    begin_date = end_date - timedelta(days=730)
    url = (
        f"{provider.base_url}/report/list"
        f"?pageSize={limit}&pageNo=1&qType=0&code={symbol}"
        f"&beginTime={begin_date.isoformat()}&endTime={end_date.isoformat()}"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = payload.get("data") or []
    return ResearchReportResponse(
        symbol=symbol,
        provider_key=provider.key,
        items=[
            ResearchReportItem(
                id=str(row.get("infoCode") or ""),
                title=str(row.get("title") or ""),
                stock_code=str(row.get("stockCode") or symbol),
                stock_name=str(row.get("stockName") or ""),
                org_name=str(row.get("orgSName") or row.get("orgName") or ""),
                publish_date=str(row.get("publishDate") or ""),
                rating=str(row.get("emRatingName") or row.get("rating") or ""),
                author=str(row.get("researcher") or row.get("author") or ""),
                url=(
                    f"https://data.eastmoney.com/report/info/{row.get('infoCode')}.html"
                    if row.get("infoCode")
                    else ""
                ),
            )
            for row in rows[:limit]
        ],
    )


def _fetch_eastmoney_dragon_tiger(
    provider: DataProvider,
    params: dict[str, Any],
) -> DragonTigerResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    url = (
        f"{provider.base_url}/api/data/v1/get"
        "?reportName=RPT_DAILYBILLBOARD_DETAILS&columns=ALL"
        f"&filter=(SECURITY_CODE%3D%22{symbol}%22)"
        f"&pageNumber=1&pageSize={limit}&sortColumns=TRADE_DATE&sortTypes=-1"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("result") or {}).get("data") or [])[:limit]
    return DragonTigerResponse(
        symbol=symbol,
        provider_key=provider.key,
        items=[
            DragonTigerItem(
                trade_date=str(row.get("TRADE_DATE") or ""),
                symbol=str(row.get("SECURITY_CODE") or symbol),
                name=str(row.get("SECURITY_NAME_ABBR") or ""),
                reason=str(row.get("EXPLANATION") or ""),
                close_price=_to_float(row.get("CLOSE_PRICE")),
                change_percent=_to_float(row.get("CHANGE_RATE")),
                buy_amount=_to_float(row.get("BILLBOARD_BUY_AMT")),
                sell_amount=_to_float(row.get("BILLBOARD_SELL_AMT")),
                net_amount=_to_float(row.get("BILLBOARD_NET_AMT")),
                deal_amount=_to_float(row.get("BILLBOARD_DEAL_AMT")),
                explanation=str(row.get("EXPLAIN") or ""),
            )
            for row in rows
        ],
    )


def _fetch_eastmoney_lockup_expiry(
    provider: DataProvider,
    params: dict[str, Any],
) -> LockupExpiryResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    url = (
        f"{provider.base_url}/api/data/v1/get"
        "?reportName=RPT_LIFT_STAGE&columns=ALL"
        f"&filter=(SECURITY_CODE%3D%22{symbol}%22)"
        f"&pageNumber=1&pageSize={limit}&sortColumns=FREE_DATE&sortTypes=-1"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("result") or {}).get("data") or [])[:limit]
    return LockupExpiryResponse(
        symbol=symbol,
        provider_key=provider.key,
        items=[
            LockupExpiryItem(
                free_date=str(row.get("FREE_DATE") or ""),
                symbol=str(row.get("SECURITY_CODE") or symbol),
                name=str(row.get("SECURITY_NAME_ABBR") or ""),
                shares=_to_float(row.get("FREE_SHARES")),
                market_cap=_to_float(row.get("LIFT_MARKET_CAP")),
                free_ratio=_to_float(row.get("FREE_RATIO")),
                share_type=str(row.get("FREE_SHARES_TYPE") or ""),
            )
            for row in rows
        ],
    )


def _fetch_eastmoney_margin_trading(
    provider: DataProvider,
    params: dict[str, Any],
) -> MarginTradingResponse:
    symbol = params["symbol"]
    limit = int(params["limit"])
    url = (
        f"{provider.base_url}/api/data/v1/get"
        "?reportName=RPTA_WEB_RZRQ_GGMX&columns=ALL"
        f"&filter=(scode%3D%22{symbol}%22)"
        f"&pageNumber=1&pageSize={limit}&sortColumns=date&sortTypes=-1"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("result") or {}).get("data") or [])[:limit]
    return MarginTradingResponse(
        symbol=symbol,
        provider_key=provider.key,
        items=[
            MarginTradingItem(
                date=str(row.get("DATE") or ""),
                symbol=str(row.get("SCODE") or symbol),
                name=str(row.get("SECNAME") or ""),
                financing_balance=_to_float(row.get("RZYE")),
                securities_lending_balance=_to_float(row.get("RQYE")),
                margin_balance=_to_float(row.get("RZRQYE")),
                financing_buy_amount=_to_float(row.get("RZMRE")),
                financing_net_buy_amount=_to_float(row.get("RZJME")),
                short_selling_volume=_to_float(row.get("RQMCL")),
            )
            for row in rows
        ],
    )


def _fetch_eastmoney_macro_indicator(
    provider: DataProvider,
    params: dict[str, Any],
) -> MacroIndicatorResponse:
    indicator = params["indicator"]
    limit = int(params["limit"])
    report_map = {"cpi": "RPT_ECONOMY_CPI", "pmi": "RPT_ECONOMY_PMI"}
    url = (
        f"{provider.base_url}/api/data/v1/get"
        f"?reportName={report_map[indicator]}&columns=ALL"
        f"&pageNumber=1&pageSize={limit}&sortColumns=REPORT_DATE&sortTypes=-1"
    )
    payload = _http_get_json(url, headers={"Referer": "https://data.eastmoney.com/"})
    rows = ((payload.get("result") or {}).get("data") or [])[:limit]
    value_keys = {
        "cpi": ["NATIONAL_SAME", "NATIONAL_BASE", "NATIONAL_SEQUENTIAL", "NATIONAL_ACCUMULATE"],
        "pmi": ["MAKE_INDEX", "MAKE_SAME", "NMAKE_INDEX", "NMAKE_SAME"],
    }[indicator]
    return MacroIndicatorResponse(
        indicator=indicator,
        provider_key=provider.key,
        items=[
            MacroIndicatorItem(
                report_date=str(row.get("REPORT_DATE") or ""),
                time_label=str(row.get("TIME") or ""),
                values={key: row.get(key) for key in value_keys if key in row},
            )
            for row in rows
        ],
    )


def _parse_eastmoney_bar(value: str) -> KlineBar:
    parts = value.split(",")
    if len(parts) < 7:
        raise ValueError("东方财富 K 线字段不足。")
    return KlineBar(
        time=parts[0],
        open=float(parts[1]),
        close=float(parts[2]),
        high=float(parts[3]),
        low=float(parts[4]),
        volume=float(parts[5]),
        amount=float(parts[6]),
        amplitude=_to_float(parts[7]) if len(parts) > 7 else None,
        change_percent=_to_float(parts[8]) if len(parts) > 8 else None,
        change=_to_float(parts[9]) if len(parts) > 9 else None,
        turnover_rate=_to_float(parts[10]) if len(parts) > 10 else None,
    )


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    last_error: httpx.HTTPError | None = None
    for _ in range(2):
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True, headers=_headers(headers))
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise DataFetchError("HTTP 请求失败。", "http_error")


def _http_get_text(url: str, encoding: str | None = None) -> str:
    last_error: httpx.HTTPError | None = None
    for _ in range(2):
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True, headers=_headers())
            response.raise_for_status()
            if encoding:
                response.encoding = encoding
            return response.text
        except httpx.HTTPError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise DataFetchError("HTTP 请求失败。", "http_error")


def _http_post_json(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> Any:
    response = httpx.post(url, data=data, timeout=10.0, follow_redirects=True, headers=_headers(headers))
    response.raise_for_status()
    return response.json()


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        )
    }
    if extra:
        headers.update(extra)
    return headers


def _log_fetch(
    db: Session,
    provider: DataProvider,
    data_category: str,
    symbol: str,
    status: str,
    latency_ms: int | None,
    cache_hit: bool,
    fallback_used: bool,
) -> None:
    now = datetime.now(timezone.utc)
    provider.health_status = "healthy"
    provider.last_success_at = now
    db.add(provider)
    db.add(
        DataFetchLog(
            provider_key=provider.key,
            data_category=data_category,
            symbol=_normalize_symbol(symbol) if symbol else "",
            status=status,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
            fallback_used=fallback_used,
        )
    )
    db.commit()


def _record_failure(
    db: Session,
    provider: DataProvider,
    data_category: str,
    symbol: str,
    error_type: str,
    error_message: str,
    fallback_used: bool,
) -> None:
    provider.health_status = "unavailable"
    provider.last_failure_at = datetime.now(timezone.utc)
    db.add(provider)
    db.add(
        DataFetchLog(
            provider_key=provider.key,
            data_category=data_category,
            symbol=_normalize_symbol(symbol) if symbol else "",
            status="failed",
            fallback_used=fallback_used,
            error_type=error_type,
            error_message=error_message,
        )
    )
    db.commit()


def _persist_content_records(db: Session, value: Any) -> None:
    if isinstance(value, NewsResponse):
        records = [("news", item.source or value.provider_key, item.id, item.related_stocks[0] if item.related_stocks else "", item.title, item.content, item.url, item.publish_time, item.model_dump(mode="json")) for item in value.items]
    elif isinstance(value, AnnouncementResponse):
        records = [("announcement", item.source or value.provider_key, item.id, item.symbol, item.title, "", item.url, item.publish_time, item.model_dump(mode="json")) for item in value.items]
    elif isinstance(value, ResearchReportResponse):
        records = [("research_report", value.provider_key, item.id, item.stock_code or value.symbol, item.title, "", item.url, item.publish_date, item.model_dump(mode="json")) for item in value.items]
    elif isinstance(value, NorthboundFlowResponse):
        records = [("northbound_flow", value.provider_key, f"{item.trade_date}:{item.mutual_type}", "", item.mutual_type, "", "", item.trade_date, item.model_dump(mode="json")) for item in value.items]
    else:
        return
    for content_type, source, external_id, symbol, title, content, url, published_at, payload in records:
        if not external_id:
            continue
        row = db.scalar(select(DataContentRecord).where(
            DataContentRecord.content_type == content_type,
            DataContentRecord.source == source,
            DataContentRecord.external_id == external_id,
        ))
        if row is None:
            row = DataContentRecord(content_type=content_type, source=source, external_id=external_id)
        row.symbol, row.title, row.content, row.url, row.published_at = symbol, title, content, url, published_at
        row.payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        db.add(row)
    db.commit()


def _northbound_from_archive(db: Session, limit: int) -> NorthboundFlowResponse | None:
    rows = db.scalars(
        select(DataContentRecord)
        .where(DataContentRecord.content_type == "northbound_flow")
        .order_by(DataContentRecord.updated_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return None
    items: list[NorthboundFlowItem] = []
    for row in rows:
        try:
            items.append(NorthboundFlowItem.model_validate(json.loads(row.payload_json)))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return NorthboundFlowResponse(provider_key="local_northbound_cache", items=items) if items else None


def _cache_key(provider_key: str, data_category: str, params: dict[str, Any]) -> str:
    return json.dumps(
        {"provider": provider_key, "category": data_category, "params": params},
        sort_keys=True,
        ensure_ascii=False,
    )


def _normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[2:]
    return cleaned


def _to_eastmoney_secid(symbol: str) -> str:
    code = _normalize_symbol(symbol)
    market = "1" if code.startswith(("5", "6", "9")) else "0"
    return f"{market}.{code}"


def _to_tencent_symbol(symbol: str) -> str:
    code = _normalize_symbol(symbol)
    prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}{code}"


def _to_sina_scale(period: str) -> str:
    klt = PERIOD_TO_KLT[period]
    if klt == "101":
        return "240"
    if klt in {"1", "5", "15", "30", "60"}:
        return klt
    raise DataFetchError(f"新浪暂不支持该 K 线周期：{period}", "invalid_period")


def _statement_keys(statement_type: str) -> list[str]:
    if statement_type == "income":
        return [
            "TOTAL_OPERATE_INCOME",
            "TOTAL_OPERATE_COST",
            "OPERATE_PROFIT",
            "TOTAL_PROFIT",
            "PARENT_NETPROFIT",
            "BASIC_EPS",
            "DILUTED_EPS",
        ]
    if statement_type == "balance":
        return [
            "TOTAL_ASSETS",
            "TOTAL_LIABILITIES",
            "TOTAL_EQUITY",
            "MONETARYFUNDS",
            "ACCOUNTS_RECE",
            "INVENTORY",
            "SHORT_LOAN",
        ]
    return [
        "NETCASH_OPERATE",
        "NETCASH_INVEST",
        "NETCASH_FINANCE",
        "CASH_EQUIVALENTS",
        "CCE_ADD",
    ]


def _to_float(value: str | int | float | None) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
