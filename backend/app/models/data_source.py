from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DataProvider(Base):
    __tablename__ = "data_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(40), default="http")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_type: Mapped[str] = mapped_column(String(40), default="none")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    test_url: Mapped[str] = mapped_column(String(500), default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    rate_limit_json: Mapped[str] = mapped_column(Text, default="{}")
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, default=60)
    health_status: Mapped[str] = mapped_column(String(40), default="unknown")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataProviderCredential(Base):
    __tablename__ = "data_provider_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), index=True)
    credential_type: Mapped[str] = mapped_column(String(40))
    encrypted_value: Mapped[str] = mapped_column(Text)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40), default="unknown")


class DataRoute(Base):
    __tablename__ = "data_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    data_category: Mapped[str] = mapped_column(String(80), index=True)
    tool_name: Mapped[str] = mapped_column(String(120), default="")
    provider_chain_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    fallback_policy: Mapped[str] = mapped_column(String(80), default="explicit_chain")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataFetchLog(Base):
    __tablename__ = "data_fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_key: Mapped[str] = mapped_column(String(80), index=True)
    data_category: Mapped[str] = mapped_column(String(80), default="")
    tool_name: Mapped[str] = mapped_column(String(120), default="")
    symbol: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    error_type: Mapped[str] = mapped_column(String(80), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataWatchlistItem(Base):
    __tablename__ = "data_watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    period: Mapped[str] = mapped_column(String(40), default="daily")
    snapshot_type: Mapped[str] = mapped_column(String(80), default="analysis_context")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataContentRecord(Base):
    __tablename__ = "data_content_records"
    __table_args__ = (UniqueConstraint("content_type", "source", "external_id", name="uq_data_content_record"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_type: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    external_id: Mapped[str] = mapped_column(String(240))
    symbol: Mapped[str] = mapped_column(String(40), default="", index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[str] = mapped_column(String(64), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DataScheduledTaskRun(Base):
    __tablename__ = "data_scheduled_task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_key: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DataScheduledTaskConfig(Base):
    __tablename__ = "data_scheduled_task_configs"

    task_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DataPremarketRecommendation(Base):
    __tablename__ = "data_premarket_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scan_date: Mapped[str] = mapped_column(String(10), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="watchlist_premarket_scan")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
