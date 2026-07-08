from datetime import datetime, timezone
from time import perf_counter

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data_source import DataFetchLog, DataProvider, DataProviderCredential
from app.schemas.data_source import HealthCheckResult


def _has_credential(db: Session, provider_key: str) -> bool:
    stmt = select(DataProviderCredential).where(DataProviderCredential.provider_key == provider_key)
    return db.scalar(stmt) is not None


def check_provider_health(db: Session, provider: DataProvider) -> HealthCheckResult:
    now = datetime.now(timezone.utc)

    if not provider.enabled:
        provider.health_status = "disabled"
        db.add(provider)
        db.add(
            DataFetchLog(
                provider_key=provider.key,
                data_category="health_check",
                status="disabled",
                error_message="Provider is disabled.",
            )
        )
        db.commit()
        return HealthCheckResult(
            provider_key=provider.key,
            status="disabled",
            message="数据源已禁用。",
        )

    if provider.auth_type != "none" and not _has_credential(db, provider.key):
        provider.health_status = "auth_required"
        provider.last_failure_at = now
        db.add(provider)
        db.add(
            DataFetchLog(
                provider_key=provider.key,
                data_category="health_check",
                status="auth_required",
                error_type="missing_credential",
                error_message="Credential is required but not configured.",
            )
        )
        db.commit()
        return HealthCheckResult(
            provider_key=provider.key,
            status="auth_required",
            message="需要配置密钥后才能检测。",
        )

    if not provider.test_url:
        provider.health_status = "degraded"
        provider.last_failure_at = now
        db.add(provider)
        db.add(
            DataFetchLog(
                provider_key=provider.key,
                data_category="health_check",
                status="degraded",
                error_type="missing_test_url",
                error_message="No health-check URL configured.",
            )
        )
        db.commit()
        return HealthCheckResult(
            provider_key=provider.key,
            status="degraded",
            message="未配置检测地址。",
        )

    started = perf_counter()
    http_status: int | None = None
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            response = client.get(
                provider.test_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
                    )
                },
            )
            http_status = response.status_code
        latency_ms = int((perf_counter() - started) * 1000)

        if 200 <= http_status < 400:
            provider.health_status = "healthy"
            provider.last_success_at = now
            status = "healthy"
            message = "检测通过。"
            error_type = ""
            error_message = ""
        else:
            provider.health_status = "degraded"
            provider.last_failure_at = now
            status = "degraded"
            message = f"HTTP 状态异常：{http_status}"
            error_type = "http_status"
            error_message = message

        db.add(provider)
        db.add(
            DataFetchLog(
                provider_key=provider.key,
                data_category="health_check",
                status=status,
                http_status=http_status,
                latency_ms=latency_ms,
                error_type=error_type,
                error_message=error_message,
            )
        )
        db.commit()
        return HealthCheckResult(
            provider_key=provider.key,
            status=status,
            http_status=http_status,
            latency_ms=latency_ms,
            message=message,
        )
    except httpx.TimeoutException as exc:
        return _record_failure(db, provider, now, "timeout", str(exc), http_status)
    except httpx.HTTPError as exc:
        return _record_failure(db, provider, now, "http_error", str(exc), http_status)


def _record_failure(
    db: Session,
    provider: DataProvider,
    now: datetime,
    error_type: str,
    error_message: str,
    http_status: int | None,
) -> HealthCheckResult:
    provider.health_status = "unavailable"
    provider.last_failure_at = now
    db.add(provider)
    db.add(
        DataFetchLog(
            provider_key=provider.key,
            data_category="health_check",
            status="unavailable",
            http_status=http_status,
            error_type=error_type,
            error_message=error_message,
        )
    )
    db.commit()
    return HealthCheckResult(
        provider_key=provider.key,
        status="unavailable",
        http_status=http_status,
        message=error_message,
    )
