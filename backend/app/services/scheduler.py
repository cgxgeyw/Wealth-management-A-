import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.data_source import DataProvider, DataScheduledTaskRun, DataWatchlistItem
from app.services.data_fetcher import get_klines, get_market_news, get_realtime_quote
from app.services.data_source_health import check_provider_health
from app.services.trading_time import is_trading_time


@dataclass(frozen=True)
class ScheduledTask:
    key: str
    name: str
    interval_seconds: int
    enabled: bool
    runner: Callable[[Session], str]
    trading_time_only: bool = False


def _run_health_check(db: Session) -> str:
    providers = db.scalars(select(DataProvider).order_by(DataProvider.id)).all()
    results = [check_provider_health(db, provider) for provider in providers]
    return "；".join(f"{item.provider_key}:{item.status}" for item in results)


def _refresh_watchlist_quotes(db: Session) -> str:
    items = db.scalars(select(DataWatchlistItem).order_by(DataWatchlistItem.sort_order)).all()
    refreshed = 0
    for item in items:
        get_realtime_quote(db, item.symbol)
        refreshed += 1
    return f"刷新自选股行情 {refreshed} 条"


def _refresh_market_news(db: Session) -> str:
    news = get_market_news(db, limit=30)
    return f"刷新市场快讯 {len(news.items)} 条"


def _refresh_daily_klines(db: Session) -> str:
    items = db.scalars(select(DataWatchlistItem).order_by(DataWatchlistItem.sort_order)).all()
    refreshed = 0
    for item in items:
        get_klines(db, symbol=item.symbol, period="daily", limit=120)
        refreshed += 1
    return f"刷新自选股日 K {refreshed} 条"


TASKS: dict[str, ScheduledTask] = {
    "data_source_health_check": ScheduledTask(
        key="data_source_health_check",
        name="数据源健康检查",
        interval_seconds=30 * 60,
        enabled=True,
        runner=_run_health_check,
    ),
    "watchlist_quote_refresh": ScheduledTask(
        key="watchlist_quote_refresh",
        name="自选股实时行情刷新",
        interval_seconds=30,
        enabled=True,
        runner=_refresh_watchlist_quotes,
        trading_time_only=True,
    ),
    "market_news_refresh": ScheduledTask(
        key="market_news_refresh",
        name="市场快讯刷新",
        interval_seconds=3 * 60,
        enabled=True,
        runner=_refresh_market_news,
    ),
    "watchlist_daily_kline_refresh": ScheduledTask(
        key="watchlist_daily_kline_refresh",
        name="自选股日 K 刷新",
        interval_seconds=10 * 60,
        enabled=True,
        runner=_refresh_daily_klines,
    ),
}


_scheduler_tasks: list[asyncio.Task[None]] = []


def run_task_once(task_key: str) -> DataScheduledTaskRun:
    task = TASKS.get(task_key)
    if not task:
        raise KeyError(task_key)
    started = datetime.now(timezone.utc)
    started_perf = perf_counter()
    with SessionLocal() as db:
        run = DataScheduledTaskRun(
            task_key=task.key,
            status="running",
            started_at=started,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        try:
            message = task.runner(db)
            run.status = "success"
            run.message = message
        except Exception as exc:  # noqa: BLE001 - scheduled task log must capture all failures.
            run.status = "failed"
            run.message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((perf_counter() - started_perf) * 1000)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run


async def _task_loop(task: ScheduledTask) -> None:
    while True:
        await asyncio.sleep(task.interval_seconds)
        if not task.enabled:
            continue
        if task.trading_time_only and not is_trading_time():
            continue
        await asyncio.to_thread(run_task_once, task.key)


def start_scheduler() -> None:
    if _scheduler_tasks:
        return
    loop = asyncio.get_running_loop()
    for task in TASKS.values():
        _scheduler_tasks.append(loop.create_task(_task_loop(task)))


async def stop_scheduler() -> None:
    tasks = list(_scheduler_tasks)
    _scheduler_tasks.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def list_task_runs(db: Session, limit: int = 50) -> list[DataScheduledTaskRun]:
    return db.scalars(
        select(DataScheduledTaskRun)
        .order_by(desc(DataScheduledTaskRun.id))
        .limit(min(max(limit, 1), 200))
    ).all()


def last_run_by_task(db: Session) -> dict[str, DataScheduledTaskRun]:
    runs = list_task_runs(db, limit=200)
    result: dict[str, DataScheduledTaskRun] = {}
    for run in runs:
        result.setdefault(run.task_key, run)
    return result
