import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.data_source import DataFetchLog, DataProvider, DataProviderCredential, DataRoute, DataSnapshot
from app.models.data_source import DataWatchlistItem
from app.schemas.data_source import (
    CacheClearResponse,
    DataFetchLogListResponse,
    DataFetchLogRead,
    DataAlertItem,
    DataAlertListResponse,
    DataQualityItem,
    DataQualityResponse,
    DataProviderListResponse,
    DataProviderCredentialListResponse,
    DataProviderCredentialRead,
    DataProviderCredentialUpsertRequest,
    DataProviderRead,
    DataProviderUpdateRequest,
    DataProviderCreateRequest,
    DataRouteListResponse,
    DataRouteRead,
    DataRouteUpdateRequest,
    DataSnapshotCreateRequest,
    DataSnapshotListResponse,
    DataSnapshotRead,
    HealthCheckRequest,
    HealthCheckResponse,
    KlineResponse,
    NewsResponse,
    PremarketRecommendationRead,
    PremarketRecommendationResponse,
    ScheduledTaskListResponse,
    ScheduledTaskRead,
    ScheduledTaskRunListResponse,
    ScheduledTaskRunRead,
    ScheduledTaskUpdateRequest,
    RealtimeQuote,
    WatchlistCreateRequest,
    WatchlistItemRead,
    WatchlistListResponse,
    WatchlistReorderRequest,
)
from app.services.data_source_health import check_provider_health
from app.services.data_fetcher import (
    DataFetchError,
    clear_runtime_cache,
    get_klines,
    get_market_news,
    get_realtime_quote,
)
from app.services.data_snapshots import create_analysis_snapshot
from app.services.scheduler import (
    TASKS,
    get_task_settings,
    last_run_by_task,
    list_premarket_recommendations,
    list_task_runs,
    run_task_once,
    update_task_settings,
)

router = APIRouter()


def _normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[2:]
    return cleaned


def _get_provider_or_404(db: Session, provider_key: str) -> DataProvider:
    provider = db.scalar(select(DataProvider).where(DataProvider.key == provider_key))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found.")
    return provider


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


def _credential_read(credential: DataProviderCredential) -> DataProviderCredentialRead:
    return DataProviderCredentialRead(
        provider_key=credential.provider_key,
        credential_type=credential.credential_type,
        configured=bool(credential.encrypted_value),
        masked_value=_mask_secret(credential.encrypted_value),
        last_verified_at=credential.last_verified_at,
        verification_status=credential.verification_status,
    )


@router.get("/providers", response_model=DataProviderListResponse)
def list_providers(db: Session = Depends(get_db)) -> DataProviderListResponse:
    providers = db.scalars(select(DataProvider).order_by(DataProvider.id)).all()
    return DataProviderListResponse(
        items=[DataProviderRead.model_validate(provider) for provider in providers]
    )


@router.patch("/providers/{provider_key}", response_model=DataProviderRead)
def update_provider(
    provider_key: str,
    payload: DataProviderUpdateRequest,
    db: Session = Depends(get_db),
) -> DataProviderRead:
    provider = _get_provider_or_404(db, provider_key)
    if payload.name is not None:
        provider.name = payload.name.strip() or provider.name
    if payload.enabled is not None:
        provider.enabled = payload.enabled
    if payload.auth_type is not None:
        provider.auth_type = payload.auth_type.strip() or "none"
    if payload.base_url is not None:
        provider.base_url = payload.base_url.strip()
    if payload.test_url is not None:
        provider.test_url = payload.test_url.strip()
    if payload.cache_ttl_seconds is not None:
        provider.cache_ttl_seconds = payload.cache_ttl_seconds
    if payload.config is not None:
        provider.config_json = json.dumps(payload.config, ensure_ascii=False)
    if payload.rate_limit is not None:
        provider.rate_limit_json = json.dumps(payload.rate_limit, ensure_ascii=False)

    db.add(provider)
    db.commit()
    db.refresh(provider)
    return DataProviderRead.model_validate(provider)


@router.post("/providers", response_model=DataProviderRead)
def create_provider(payload: DataProviderCreateRequest, db: Session = Depends(get_db)) -> DataProviderRead:
    if db.scalar(select(DataProvider).where(DataProvider.key == payload.key)):
        raise HTTPException(status_code=409, detail="Provider key already exists.")
    provider = DataProvider(
        key=payload.key,
        name=payload.name,
        type=payload.type,
        enabled=payload.enabled,
        auth_type=payload.auth_type,
        base_url=payload.base_url,
        test_url=payload.test_url,
        cache_ttl_seconds=payload.cache_ttl_seconds,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return DataProviderRead.model_validate(provider)


@router.get("/providers/{provider_key}/credentials", response_model=DataProviderCredentialListResponse)
def list_provider_credentials(
    provider_key: str,
    db: Session = Depends(get_db),
) -> DataProviderCredentialListResponse:
    _get_provider_or_404(db, provider_key)
    credentials = db.scalars(
        select(DataProviderCredential)
        .where(DataProviderCredential.provider_key == provider_key)
        .order_by(DataProviderCredential.credential_type)
    ).all()
    return DataProviderCredentialListResponse(
        items=[_credential_read(credential) for credential in credentials]
    )


@router.post("/providers/{provider_key}/credentials", response_model=DataProviderCredentialRead)
def upsert_provider_credential(
    provider_key: str,
    payload: DataProviderCredentialUpsertRequest,
    db: Session = Depends(get_db),
) -> DataProviderCredentialRead:
    _get_provider_or_404(db, provider_key)
    credential_type = payload.credential_type.strip()
    value = payload.value.strip()
    if not credential_type:
        raise HTTPException(status_code=400, detail="Credential type is required.")
    if not value:
        raise HTTPException(status_code=400, detail="Credential value is required.")

    credential = db.scalar(
        select(DataProviderCredential).where(
            DataProviderCredential.provider_key == provider_key,
            DataProviderCredential.credential_type == credential_type,
        )
    )
    if not credential:
        credential = DataProviderCredential(
            provider_key=provider_key,
            credential_type=credential_type,
            encrypted_value=value,
            verification_status="configured",
        )
    else:
        credential.encrypted_value = value
        credential.verification_status = "configured"
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return _credential_read(credential)


@router.delete("/providers/{provider_key}/credentials/{credential_type}", response_model=DataProviderCredentialListResponse)
def delete_provider_credential(
    provider_key: str,
    credential_type: str,
    db: Session = Depends(get_db),
) -> DataProviderCredentialListResponse:
    _get_provider_or_404(db, provider_key)
    credential = db.scalar(
        select(DataProviderCredential).where(
            DataProviderCredential.provider_key == provider_key,
            DataProviderCredential.credential_type == credential_type,
        )
    )
    if credential:
        db.delete(credential)
        db.commit()
    return list_provider_credentials(provider_key, db)


@router.get("/routes", response_model=DataRouteListResponse)
def list_routes(db: Session = Depends(get_db)) -> DataRouteListResponse:
    routes = db.scalars(select(DataRoute).order_by(DataRoute.id)).all()
    items = []
    for route in routes:
        try:
            chain = json.loads(route.provider_chain_json)
        except json.JSONDecodeError:
            chain = []
        items.append(
            DataRouteRead(
                id=route.id,
                data_category=route.data_category,
                tool_name=route.tool_name,
                provider_chain=chain,
                enabled=route.enabled,
                fallback_policy=route.fallback_policy,
            )
        )
    return DataRouteListResponse(items=items)


@router.patch("/routes/{route_id}", response_model=DataRouteRead)
def update_route(route_id: int, payload: DataRouteUpdateRequest, db: Session = Depends(get_db)) -> DataRouteRead:
    route = db.get(DataRoute, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Data route not found.")
    if payload.provider_chain:
        provider_keys = set(db.scalars(select(DataProvider.key).where(DataProvider.key.in_(payload.provider_chain))).all())
        if provider_keys != set(payload.provider_chain):
            raise HTTPException(status_code=400, detail="One or more providers in the route do not exist.")
        route.provider_chain_json = json.dumps(payload.provider_chain, ensure_ascii=False)
    if payload.enabled is not None:
        route.enabled = payload.enabled
    if payload.fallback_policy is not None:
        route.fallback_policy = payload.fallback_policy
    db.add(route)
    db.commit()
    db.refresh(route)
    return DataRouteRead(id=route.id, data_category=route.data_category, tool_name=route.tool_name, provider_chain=json.loads(route.provider_chain_json), enabled=route.enabled, fallback_policy=route.fallback_policy)


@router.get("/fetch-logs", response_model=DataFetchLogListResponse)
def list_fetch_logs(limit: int = 50, db: Session = Depends(get_db)) -> DataFetchLogListResponse:
    limit = min(max(limit, 1), 200)
    logs = db.scalars(select(DataFetchLog).order_by(desc(DataFetchLog.id)).limit(limit)).all()
    return DataFetchLogListResponse(
        items=[DataFetchLogRead.model_validate(log) for log in logs]
    )


@router.get("/quality", response_model=DataQualityResponse)
def data_quality(db: Session = Depends(get_db)) -> DataQualityResponse:
    providers = db.scalars(select(DataProvider).order_by(DataProvider.id)).all()
    logs = db.scalars(select(DataFetchLog).order_by(desc(DataFetchLog.id)).limit(500)).all()
    items: list[DataQualityItem] = []
    for provider in providers:
        provider_logs = [log for log in logs if log.provider_key == provider.key]
        failures = [log for log in provider_logs if log.status in {"failed", "unavailable", "auth_failed", "auth_required"}]
        cache_hits = [log for log in provider_logs if log.cache_hit]
        score = 100
        if provider.health_status in {"unavailable", "auth_failed"}:
            score -= 45
        elif provider.health_status in {"degraded", "auth_required", "rate_limited", "stale"}:
            score -= 25
        elif provider.health_status == "disabled":
            score -= 35
        score -= min(len(failures) * 5, 40)
        if provider_logs and len(cache_hits) / len(provider_logs) > 0.8:
            score -= 5
        latest_failure = failures[0] if failures else None
        items.append(
            DataQualityItem(
                provider_key=provider.key,
                health_status=provider.health_status,
                score=max(score, 0),
                recent_total=len(provider_logs),
                recent_failures=len(failures),
                cache_hits=len(cache_hits),
                last_message=latest_failure.error_message if latest_failure else "",
            )
        )
    return DataQualityResponse(items=items)


@router.get("/alerts", response_model=DataAlertListResponse)
def data_alerts(limit: int = 50, db: Session = Depends(get_db)) -> DataAlertListResponse:
    providers = db.scalars(select(DataProvider).order_by(DataProvider.id)).all()
    alerts: list[DataAlertItem] = []
    for provider in providers:
        if provider.health_status in {"unavailable", "auth_failed"}:
            alerts.append(
                DataAlertItem(
                    provider_key=provider.key,
                    severity="high",
                    status=provider.health_status,
                    message=f"数据源状态异常：{provider.health_status}",
                )
            )
        elif provider.health_status in {"degraded", "auth_required", "rate_limited", "stale"}:
            alerts.append(
                DataAlertItem(
                    provider_key=provider.key,
                    severity="medium",
                    status=provider.health_status,
                    message=f"数据源需要关注：{provider.health_status}",
                )
            )

    logs = db.scalars(
        select(DataFetchLog)
        .where(DataFetchLog.status.in_(["failed", "unavailable", "auth_required", "auth_failed"]))
        .order_by(desc(DataFetchLog.id))
        .limit(min(max(limit, 1), 200))
    ).all()
    for log in logs:
        alerts.append(
            DataAlertItem(
                provider_key=log.provider_key,
                severity="high" if log.status in {"failed", "unavailable"} else "medium",
                status=log.status,
                message=log.error_message or log.error_type or "数据抓取异常",
                fetched_at=log.fetched_at,
            )
        )
    return DataAlertListResponse(items=alerts[: min(max(limit, 1), 200)])


@router.post("/health-check", response_model=HealthCheckResponse)
def run_health_check(
    payload: HealthCheckRequest,
    db: Session = Depends(get_db),
) -> HealthCheckResponse:
    if payload.provider_key:
        provider = db.scalar(
            select(DataProvider).where(DataProvider.key == payload.provider_key)
        )
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found.")
        return HealthCheckResponse(items=[check_provider_health(db, provider)])

    providers = db.scalars(select(DataProvider).order_by(DataProvider.id)).all()
    return HealthCheckResponse(
        items=[check_provider_health(db, provider) for provider in providers]
    )


@router.get("/quote/{symbol}", response_model=RealtimeQuote)
def fetch_realtime_quote(symbol: str, db: Session = Depends(get_db)) -> RealtimeQuote:
    try:
        return get_realtime_quote(db, symbol)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/klines/{symbol}", response_model=KlineResponse)
def fetch_klines(
    symbol: str,
    period: str = "daily",
    limit: int = 120,
    adjust: str = "qfq",
    db: Session = Depends(get_db),
) -> KlineResponse:
    try:
        return get_klines(db, symbol=symbol, period=period, limit=limit, adjust=adjust)
    except DataFetchError as exc:
        status_code = 400 if exc.error_type == "invalid_period" else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/news", response_model=NewsResponse)
def fetch_market_news(limit: int = 30, db: Session = Depends(get_db)) -> NewsResponse:
    try:
        return get_market_news(db, limit=limit)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/cache/clear", response_model=CacheClearResponse)
def clear_cache() -> CacheClearResponse:
    clear_runtime_cache()
    return CacheClearResponse(cleared=True, message="Runtime cache cleared.")


@router.get("/scheduled-tasks", response_model=ScheduledTaskListResponse)
def list_scheduled_tasks(db: Session = Depends(get_db)) -> ScheduledTaskListResponse:
    latest_runs = last_run_by_task(db)
    items = []
    for task in TASKS.values():
        latest = latest_runs.get(task.key)
        enabled, daily_at = get_task_settings(db, task)
        schedule = task.schedule
        if daily_at:
            prefix = "交易日" if task.trading_day_only else "每日"
            schedule = f"{prefix} {daily_at.strftime('%H:%M')}"
        items.append(
            ScheduledTaskRead(
                key=task.key,
                name=task.name,
                description=task.description,
                category=task.category,
                interval_seconds=task.interval_seconds,
                schedule=schedule,
                enabled=enabled,
                configurable=task.daily_at is not None,
                daily_time=daily_at.strftime("%H:%M") if daily_at else None,
                last_status=latest.status if latest else None,
                last_message=latest.message if latest else None,
                last_started_at=latest.started_at if latest else None,
                last_finished_at=latest.finished_at if latest else None,
            )
        )
    return ScheduledTaskListResponse(items=items)


@router.patch("/scheduled-tasks/{task_key}", response_model=ScheduledTaskRead)
def update_scheduled_task(
    task_key: str,
    payload: ScheduledTaskUpdateRequest,
    db: Session = Depends(get_db),
) -> ScheduledTaskRead:
    task = TASKS.get(task_key)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found.")
    try:
        update_task_settings(db, task_key, enabled=payload.enabled, daily_time=payload.daily_time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    latest = last_run_by_task(db).get(task_key)
    enabled, daily_at = get_task_settings(db, task)
    prefix = "交易日" if task.trading_day_only else "每日"
    schedule = f"{prefix} {daily_at.strftime('%H:%M')}" if daily_at else task.schedule
    return ScheduledTaskRead(
        key=task.key,
        name=task.name,
        description=task.description,
        category=task.category,
        interval_seconds=task.interval_seconds,
        schedule=schedule,
        enabled=enabled,
        configurable=task.daily_at is not None,
        daily_time=daily_at.strftime("%H:%M") if daily_at else None,
        last_status=latest.status if latest else None,
        last_message=latest.message if latest else None,
        last_started_at=latest.started_at if latest else None,
        last_finished_at=latest.finished_at if latest else None,
    )


@router.post("/scheduled-tasks/{task_key}/run", response_model=ScheduledTaskRunRead)
def run_scheduled_task(task_key: str) -> ScheduledTaskRunRead:
    try:
        return ScheduledTaskRunRead.model_validate(run_task_once(task_key))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scheduled task not found.") from exc


@router.get("/scheduled-task-runs", response_model=ScheduledTaskRunListResponse)
def list_scheduled_task_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> ScheduledTaskRunListResponse:
    return ScheduledTaskRunListResponse(
        items=[ScheduledTaskRunRead.model_validate(run) for run in list_task_runs(db, limit=limit)]
    )


@router.get("/premarket-recommendations", response_model=PremarketRecommendationResponse)
def get_premarket_recommendations(db: Session = Depends(get_db)) -> PremarketRecommendationResponse:
    rows = list_premarket_recommendations(db)
    return PremarketRecommendationResponse(
        scan_date=rows[0].scan_date if rows else "",
        generated_at=rows[0].generated_at if rows else None,
        candidate_count=len(rows),
        items=[PremarketRecommendationRead.model_validate(row, from_attributes=True) for row in rows],
    )


@router.post("/snapshots", response_model=DataSnapshotRead)
def create_snapshot(
    payload: DataSnapshotCreateRequest,
    db: Session = Depends(get_db),
) -> DataSnapshotRead:
    return create_analysis_snapshot(db, payload)


@router.get("/snapshots", response_model=DataSnapshotListResponse)
def list_snapshots(
    symbol: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> DataSnapshotListResponse:
    stmt = select(DataSnapshot).order_by(desc(DataSnapshot.id)).limit(min(max(limit, 1), 100))
    if symbol:
        stmt = (
            select(DataSnapshot)
            .where(DataSnapshot.symbol == _normalize_symbol(symbol))
            .order_by(desc(DataSnapshot.id))
            .limit(min(max(limit, 1), 100))
        )
    snapshots = db.scalars(stmt).all()
    return DataSnapshotListResponse(
        items=[DataSnapshotRead.model_validate(snapshot) for snapshot in snapshots]
    )


@router.get("/snapshots/{snapshot_id}", response_model=DataSnapshotRead)
def get_snapshot(snapshot_id: int, db: Session = Depends(get_db)) -> DataSnapshotRead:
    snapshot = db.get(DataSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Data snapshot not found.")
    return DataSnapshotRead.model_validate(snapshot)


@router.get("/watchlist", response_model=WatchlistListResponse)
def list_watchlist(db: Session = Depends(get_db)) -> WatchlistListResponse:
    items = db.scalars(
        select(DataWatchlistItem).order_by(DataWatchlistItem.sort_order, DataWatchlistItem.id)
    ).all()
    return WatchlistListResponse(items=[WatchlistItemRead.model_validate(item) for item in items])


@router.post("/watchlist", response_model=WatchlistItemRead)
def add_watchlist_item(
    payload: WatchlistCreateRequest,
    db: Session = Depends(get_db),
) -> WatchlistItemRead:
    symbol = _normalize_symbol(payload.symbol)
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required.")
    exists = db.scalar(select(DataWatchlistItem).where(DataWatchlistItem.symbol == symbol))
    if exists:
        return WatchlistItemRead.model_validate(exists)

    name = payload.name or symbol
    try:
        quote = get_realtime_quote(db, symbol)
        name = quote.name or name
    except DataFetchError:
        pass

    max_order = db.scalars(select(DataWatchlistItem.sort_order)).all()
    item = DataWatchlistItem(
        symbol=symbol,
        name=name,
        sort_order=(max(max_order) + 1) if max_order else 0,
        note=payload.note,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return WatchlistItemRead.model_validate(item)


@router.delete("/watchlist/{symbol}", response_model=WatchlistListResponse)
def delete_watchlist_item(symbol: str, db: Session = Depends(get_db)) -> WatchlistListResponse:
    normalized = _normalize_symbol(symbol)
    item = db.scalar(select(DataWatchlistItem).where(DataWatchlistItem.symbol == normalized))
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    db.delete(item)
    db.commit()
    return list_watchlist(db)


@router.post("/watchlist/reorder", response_model=WatchlistListResponse)
def reorder_watchlist(
    payload: WatchlistReorderRequest,
    db: Session = Depends(get_db),
) -> WatchlistListResponse:
    normalized_symbols = [_normalize_symbol(symbol) for symbol in payload.symbols]
    items = {
        item.symbol: item
        for item in db.scalars(select(DataWatchlistItem)).all()
    }
    for index, symbol in enumerate(normalized_symbols):
        item = items.get(symbol)
        if item:
            item.sort_order = index
            db.add(item)
    db.commit()
    return list_watchlist(db)
