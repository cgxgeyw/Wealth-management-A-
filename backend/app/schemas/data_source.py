from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DataProviderRead(BaseModel):
    id: int
    key: str
    name: str
    type: str
    enabled: bool
    auth_type: str
    base_url: str
    test_url: str
    cache_ttl_seconds: int
    health_status: str
    last_success_at: datetime | None
    last_failure_at: datetime | None

    model_config = {"from_attributes": True}


class DataRouteRead(BaseModel):
    id: int
    data_category: str
    tool_name: str
    provider_chain: list[str]
    enabled: bool
    fallback_policy: str


class DataFetchLogRead(BaseModel):
    id: int
    provider_key: str
    data_category: str
    tool_name: str
    symbol: str
    status: str
    http_status: int | None
    latency_ms: int | None
    cache_hit: bool
    fallback_used: bool
    error_type: str
    error_message: str
    fetched_at: datetime

    model_config = {"from_attributes": True}


class DataProviderListResponse(BaseModel):
    items: list[DataProviderRead]


class DataProviderUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    auth_type: str | None = None
    base_url: str | None = None
    test_url: str | None = None
    cache_ttl_seconds: int | None = Field(default=None, ge=0, le=86400)
    config: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None


class DataProviderCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=120)
    type: str = "http"
    enabled: bool = True
    auth_type: str = "none"
    base_url: str = ""
    test_url: str = ""
    cache_ttl_seconds: int = Field(default=60, ge=0, le=86400)


class DataRouteUpdateRequest(BaseModel):
    provider_chain: list[str] = Field(default_factory=list)
    enabled: bool | None = None
    fallback_policy: str | None = None


class DataProviderCredentialRead(BaseModel):
    provider_key: str
    credential_type: str
    configured: bool
    masked_value: str = ""
    last_verified_at: datetime | None = None
    verification_status: str = "unknown"


class DataProviderCredentialListResponse(BaseModel):
    items: list[DataProviderCredentialRead]


class DataProviderCredentialUpsertRequest(BaseModel):
    credential_type: str
    value: str


class DataRouteListResponse(BaseModel):
    items: list[DataRouteRead]


class DataFetchLogListResponse(BaseModel):
    items: list[DataFetchLogRead]


class HealthCheckRequest(BaseModel):
    provider_key: str | None = Field(default=None, description="Empty means check all providers.")


class HealthCheckResult(BaseModel):
    provider_key: str
    status: str
    http_status: int | None = None
    latency_ms: int | None = None
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class HealthCheckResponse(BaseModel):
    items: list[HealthCheckResult]


class RealtimeQuote(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    pre_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    change: float | None = None
    change_percent: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    timestamp: str = ""
    provider_key: str


class KlineBar(BaseModel):
    time: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float
    amplitude: float | None = None
    change_percent: float | None = None
    change: float | None = None
    turnover_rate: float | None = None


class KlineResponse(BaseModel):
    symbol: str
    name: str = ""
    period: str
    provider_key: str
    items: list[KlineBar]


class NewsItem(BaseModel):
    id: str
    title: str
    content: str = ""
    source: str = ""
    publish_time: str = ""
    level: str = ""
    related_stocks: list[str] = Field(default_factory=list)
    url: str = ""


class NewsResponse(BaseModel):
    provider_key: str
    items: list[NewsItem]


class AnnouncementItem(BaseModel):
    id: str
    symbol: str
    title: str
    publish_time: str = ""
    category: str = ""
    source: str = ""
    url: str = ""


class AnnouncementResponse(BaseModel):
    symbol: str
    provider_key: str
    items: list[AnnouncementItem]


class FundamentalMetric(BaseModel):
    key: str
    label: str
    value: float | str | None = None
    unit: str = ""


class FundamentalResponse(BaseModel):
    symbol: str
    name: str = ""
    provider_key: str
    metrics: list[FundamentalMetric]


class FinancialStatementRow(BaseModel):
    report_date: str
    notice_date: str = ""
    values: dict[str, float | str | None] = Field(default_factory=dict)


class FinancialStatementResponse(BaseModel):
    symbol: str
    statement_type: str
    provider_key: str
    items: list[FinancialStatementRow]


class FundFlowItem(BaseModel):
    date: str
    main_net_inflow: float | None = None
    small_net_inflow: float | None = None
    medium_net_inflow: float | None = None
    large_net_inflow: float | None = None
    super_large_net_inflow: float | None = None


class FundFlowResponse(BaseModel):
    symbol: str
    name: str = ""
    provider_key: str
    items: list[FundFlowItem]


class SectorSnapshotItem(BaseModel):
    code: str
    name: str
    price: float | None = None
    change_percent: float | None = None
    main_net_inflow: float | None = None
    main_net_ratio: float | None = None
    sector_type: str = "industry"


class SectorSnapshotResponse(BaseModel):
    provider_key: str
    items: list[SectorSnapshotItem]


class NorthboundFlowItem(BaseModel):
    trade_date: str
    mutual_type: str
    net_deal_amount: float | None = None
    buy_amount: float | None = None
    sell_amount: float | None = None
    deal_amount: float | None = None
    lead_stock_code: str = ""
    lead_stock_name: str = ""


class NorthboundFlowResponse(BaseModel):
    provider_key: str
    items: list[NorthboundFlowItem]


class ResearchReportItem(BaseModel):
    id: str
    title: str
    stock_code: str = ""
    stock_name: str = ""
    org_name: str = ""
    publish_date: str = ""
    rating: str = ""
    author: str = ""
    url: str = ""


class ResearchReportResponse(BaseModel):
    symbol: str
    provider_key: str
    items: list[ResearchReportItem]


class DragonTigerItem(BaseModel):
    trade_date: str
    symbol: str
    name: str = ""
    reason: str = ""
    close_price: float | None = None
    change_percent: float | None = None
    buy_amount: float | None = None
    sell_amount: float | None = None
    net_amount: float | None = None
    deal_amount: float | None = None
    explanation: str = ""


class DragonTigerResponse(BaseModel):
    symbol: str
    provider_key: str
    items: list[DragonTigerItem]


class LockupExpiryItem(BaseModel):
    free_date: str
    symbol: str
    name: str = ""
    shares: float | None = None
    market_cap: float | None = None
    free_ratio: float | None = None
    share_type: str = ""


class LockupExpiryResponse(BaseModel):
    symbol: str
    provider_key: str
    items: list[LockupExpiryItem]


class MarginTradingItem(BaseModel):
    date: str
    symbol: str
    name: str = ""
    financing_balance: float | None = None
    securities_lending_balance: float | None = None
    margin_balance: float | None = None
    financing_buy_amount: float | None = None
    financing_net_buy_amount: float | None = None
    short_selling_volume: float | None = None


class MarginTradingResponse(BaseModel):
    symbol: str
    provider_key: str
    items: list[MarginTradingItem]


class MacroIndicatorItem(BaseModel):
    report_date: str
    time_label: str = ""
    values: dict[str, float | str | None] = Field(default_factory=dict)


class MacroIndicatorResponse(BaseModel):
    indicator: str
    provider_key: str
    items: list[MacroIndicatorItem]


class DataQualityItem(BaseModel):
    provider_key: str
    health_status: str
    score: int
    recent_total: int
    recent_failures: int
    cache_hits: int
    last_message: str = ""


class DataQualityResponse(BaseModel):
    items: list[DataQualityItem]


class DataAlertItem(BaseModel):
    provider_key: str
    severity: str
    message: str
    status: str = ""
    fetched_at: datetime | None = None


class DataAlertListResponse(BaseModel):
    items: list[DataAlertItem]


class WatchlistItemRead(BaseModel):
    id: int
    symbol: str
    name: str
    sort_order: int
    note: str = ""

    model_config = {"from_attributes": True}


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItemRead]


class WatchlistCreateRequest(BaseModel):
    symbol: str
    name: str | None = None
    note: str = ""


class WatchlistReorderRequest(BaseModel):
    symbols: list[str]


class StockSearchItem(BaseModel):
    symbol: str
    name: str
    market: str = "A_SHARE"
    exchange: str = ""
    pinyin: str = ""


class StockSearchResponse(BaseModel):
    items: list[StockSearchItem]


class StockProfile(BaseModel):
    symbol: str
    name: str
    market: str = "A_SHARE"
    exchange: str = ""
    currency: str = "CNY"
    status: str = "active"
    data_sources: list[str] = Field(default_factory=list)


class IndicatorSeries(BaseModel):
    name: str
    values: list[float | None]


class IndicatorResponse(BaseModel):
    symbol: str
    period: str
    source: str
    items: list[IndicatorSeries]


class CacheClearResponse(BaseModel):
    cleared: bool
    message: str = ""


class DataSnapshotCreateRequest(BaseModel):
    symbol: str
    period: str = "daily"
    limit: int = 120
    news_limit: int = 10


class DataSnapshotRead(BaseModel):
    id: int
    symbol: str
    period: str
    snapshot_type: str
    snapshot_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DataSnapshotListResponse(BaseModel):
    items: list[DataSnapshotRead]


class ScheduledTaskRead(BaseModel):
    key: str
    name: str
    interval_seconds: int
    schedule: str = ""
    enabled: bool
    last_status: str | None = None
    last_message: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None


class ScheduledTaskListResponse(BaseModel):
    items: list[ScheduledTaskRead]


class ScheduledTaskRunRead(BaseModel):
    id: int
    task_key: str
    status: str
    message: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None

    model_config = {"from_attributes": True}


class ScheduledTaskRunListResponse(BaseModel):
    items: list[ScheduledTaskRunRead]


class PremarketRecommendationRead(BaseModel):
    symbol: str
    name: str
    rank: int
    score: float
    reason: str


class PremarketRecommendationResponse(BaseModel):
    scan_date: str = ""
    generated_at: datetime | None = None
    source: str = "watchlist_premarket_scan"
    source_label: str = "当前自选股候选池"
    candidate_count: int = 0
    items: list[PremarketRecommendationRead]
