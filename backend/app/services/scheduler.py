import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from time import perf_counter

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.data_source import (
    DataPremarketRecommendation,
    DataProvider,
    DataScheduledTaskConfig,
    DataScheduledTaskRun,
    DataWatchlistItem,
)
from app.services.data_fetcher import get_announcements, get_company_news, get_klines, get_market_news, get_realtime_quote, get_research_reports
from app.services.data_source_health import check_provider_health
from app.services.trading_time import is_trading_day, is_trading_time, now_cn


@dataclass(frozen=True)
class ScheduledTask:
    key: str
    name: str
    description: str
    interval_seconds: int
    enabled: bool
    runner: Callable[[Session], str]
    trading_time_only: bool = False
    daily_at: time | None = None
    trading_day_only: bool = False
    category: str = "maintenance"

    @property
    def schedule(self) -> str:
        if self.daily_at:
            prefix = "交易日" if self.trading_day_only else "每日"
            return f"{prefix} {self.daily_at.strftime('%H:%M')}"
        return f"每 {self.interval_seconds} 秒"


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


def _refresh_watchlist_content(db: Session) -> str:
    items = db.scalars(select(DataWatchlistItem).order_by(DataWatchlistItem.sort_order)).all()
    refreshed = 0
    for item in items:
        get_company_news(db, item.symbol, limit=30)
        get_announcements(db, item.symbol, limit=30)
        try:
            get_research_reports(db, item.symbol, limit=20)
        except Exception:
            pass
        refreshed += 1
    return f"刷新自选股新闻与公告 {refreshed} 只"


def _refresh_daily_klines(db: Session) -> str:
    items = db.scalars(select(DataWatchlistItem).order_by(DataWatchlistItem.sort_order)).all()
    refreshed = 0
    for item in items:
        get_klines(db, symbol=item.symbol, period="daily", limit=120)
        refreshed += 1
    return f"刷新自选股日 K {refreshed} 条"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _run_premarket_analysis(db: Session) -> str:
    watchlist = db.scalars(select(DataWatchlistItem).order_by(DataWatchlistItem.sort_order)).all()
    if not watchlist:
        raise ValueError("自选候选池为空，无法执行盘前分析。")

    scored: list[dict[str, object]] = []
    failures: list[str] = []
    for item in watchlist:
        try:
            response = get_klines(db, symbol=item.symbol, period="daily", limit=30)
            bars = response.items
            if len(bars) < 20:
                failures.append(f"{item.symbol}:K线不足20日")
                continue
            closes = [bar.close for bar in bars]
            volumes = [bar.volume for bar in bars]
            last_close = closes[-1]
            ma5 = sum(closes[-5:]) / 5
            ma20 = sum(closes[-20:]) / 20
            momentum5 = (last_close / closes[-6] - 1) * 100
            momentum20 = (last_close / closes[-20] - 1) * 100
            recent_volume = sum(volumes[-5:]) / 5
            previous_volume = sum(volumes[-10:-5]) / 5
            volume_ratio = recent_volume / previous_volume if previous_volume > 0 else 1

            score = 50.0
            score += 8 if last_close >= ma5 else -5
            score += 10 if ma5 >= ma20 else -7
            score += _clamp(momentum5 * 1.5, -10, 10)
            score += _clamp(momentum20 * 0.5, -10, 10)
            score += _clamp((volume_ratio - 1) * 8, -5, 8)
            score = round(_clamp(score, 0, 100))

            signals = [
                "价格站上5日均线" if last_close >= ma5 else "价格仍在5日均线下方",
                "短期均线强于20日均线" if ma5 >= ma20 else "短期均线尚未转强",
                f"近5日动量{momentum5:+.1f}%",
                f"近20日动量{momentum20:+.1f}%",
                f"量能比{volume_ratio:.2f}",
            ]
            scored.append({
                "symbol": item.symbol,
                "name": response.name or item.name,
                "score": score,
                "reason": "；".join(signals),
            })
        except Exception as exc:  # noqa: BLE001 - keep scanning other candidates.
            failures.append(f"{item.symbol}:{exc}")

    if not scored:
        raise ValueError("盘前候选池没有可用分析结果：" + "；".join(failures[:5]))

    scored.sort(key=lambda row: float(row["score"]), reverse=True)
    selected = [row for row in scored if float(row["score"]) >= 55][:8] or scored[:5]
    scan_date = now_cn().date().isoformat()
    db.execute(delete(DataPremarketRecommendation).where(DataPremarketRecommendation.scan_date == scan_date))
    for rank, row in enumerate(selected, start=1):
        db.add(DataPremarketRecommendation(
            scan_date=scan_date,
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            rank=rank,
            score=float(row["score"]),
            reason=str(row["reason"]),
        ))
    db.commit()
    suffix = f"，失败 {len(failures)} 只" if failures else ""
    return f"盘前扫描自选候选 {len(watchlist)} 只，生成推荐 {len(selected)} 只{suffix}"


TASKS: dict[str, ScheduledTask] = {
    "data_source_health_check": ScheduledTask(
        key="data_source_health_check",
        name="数据源健康检查",
        description="定期检查已配置数据源的可用性。",
        interval_seconds=30 * 60,
        enabled=True,
        runner=_run_health_check,
    ),
    "watchlist_quote_refresh": ScheduledTask(
        key="watchlist_quote_refresh",
        name="自选股实时行情刷新",
        description="交易时段内刷新自选股最新行情。",
        interval_seconds=30,
        enabled=True,
        runner=_refresh_watchlist_quotes,
        trading_time_only=True,
    ),
    "market_news_refresh": ScheduledTask(
        key="market_news_refresh",
        name="市场快讯刷新",
        description="定期拉取最新市场快讯。",
        interval_seconds=3 * 60,
        enabled=True,
        runner=_refresh_market_news,
    ),
    "watchlist_content_refresh": ScheduledTask(
        key="watchlist_content_refresh",
        name="自选股新闻与公告刷新",
        description="刷新关注池的个股新闻、公告并去重归档。",
        interval_seconds=15 * 60,
        enabled=True,
        runner=_refresh_watchlist_content,
    ),
    "watchlist_daily_kline_refresh": ScheduledTask(
        key="watchlist_daily_kline_refresh",
        name="自选股日 K 刷新",
        description="更新自选股日线数据。",
        interval_seconds=10 * 60,
        enabled=True,
        runner=_refresh_daily_klines,
    ),
    "premarket_watchlist_analysis": ScheduledTask(
        key="premarket_watchlist_analysis",
        name="每日盘前候选分析",
        description="交易日盘前扫描当前自选股候选池，生成当日优先关注列表。",
        interval_seconds=24 * 60 * 60,
        enabled=True,
        runner=_run_premarket_analysis,
        daily_at=time(8, 30),
        trading_day_only=True,
        category="analysis",
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


def get_task_settings(db: Session, task: ScheduledTask) -> tuple[bool, time | None]:
    config = db.get(DataScheduledTaskConfig, task.key)
    enabled = config.enabled if config else task.enabled
    daily_at = task.daily_at
    if config and config.daily_time and task.daily_at:
        hour, minute = (int(part) for part in config.daily_time.split(":", maxsplit=1))
        daily_at = time(hour, minute)
    return enabled, daily_at


def update_task_settings(db: Session, task_key: str, *, enabled: bool, daily_time: str | None) -> DataScheduledTaskConfig:
    task = TASKS.get(task_key)
    if not task:
        raise KeyError(task_key)
    if not task.daily_at and daily_time is not None:
        raise ValueError("This task does not support a daily execution time.")
    config = db.get(DataScheduledTaskConfig, task_key)
    if not config:
        config = DataScheduledTaskConfig(task_key=task_key)
    config.enabled = enabled
    config.daily_time = daily_time if task.daily_at else None
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _last_run_local_date(db: Session, task_key: str):
    latest = db.scalar(
        select(DataScheduledTaskRun)
        .where(DataScheduledTaskRun.task_key == task_key)
        .order_by(desc(DataScheduledTaskRun.id))
        .limit(1)
    )
    if not latest:
        return None
    started_at = latest.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return started_at.astimezone(now_cn().tzinfo).date()


async def _daily_task_loop(task: ScheduledTask) -> None:
    while True:
        should_run = False
        wait_seconds = 30.0
        with SessionLocal() as db:
            enabled, daily_at = get_task_settings(db, task)
            current = now_cn()
            target = current.replace(
                hour=(daily_at or task.daily_at or time()).hour,
                minute=(daily_at or task.daily_at or time()).minute,
                second=0,
                microsecond=0,
            )
            already_ran_today = _last_run_local_date(db, task.key) == current.date()
            should_run = enabled and current >= target and not already_ran_today
            if should_run and task.trading_day_only and not is_trading_day():
                should_run = False
            next_target = target if current < target else target + timedelta(days=1)
            wait_seconds = min(max((next_target - current).total_seconds(), 1), 30)
        if should_run:
            await asyncio.to_thread(run_task_once, task.key)
            continue
        await asyncio.sleep(wait_seconds)


async def _interval_task_loop(task: ScheduledTask) -> None:
    while True:
        await asyncio.sleep(float(task.interval_seconds))
        with SessionLocal() as db:
            enabled, _ = get_task_settings(db, task)
        if enabled and (not task.trading_time_only or is_trading_time()):
            await asyncio.to_thread(run_task_once, task.key)


async def _task_loop(task: ScheduledTask) -> None:
    if task.daily_at:
        await _daily_task_loop(task)
    else:
        await _interval_task_loop(task)


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


def list_premarket_recommendations(db: Session) -> list[DataPremarketRecommendation]:
    latest = db.scalar(select(DataPremarketRecommendation.scan_date).order_by(desc(DataPremarketRecommendation.generated_at)).limit(1))
    if not latest:
        return []
    return db.scalars(
        select(DataPremarketRecommendation)
        .where(DataPremarketRecommendation.scan_date == latest)
        .order_by(DataPremarketRecommendation.rank)
    ).all()
