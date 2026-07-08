from app.services.trading_time import is_trading_time


TTL_POLICY_SECONDS = {
    "realtime_quote": {"trading": 10, "closed": 180},
    "minute_kline": {"trading": 45, "closed": 86_400},
    "daily_kline": {"trading": 180, "closed": 86_400},
    "market_news": {"trading": 120, "closed": 900},
    "announcement": {"trading": 900, "closed": 3_600},
    "fundamental_snapshot": {"trading": 3_600, "closed": 86_400},
    "financial_statement": {"trading": 86_400, "closed": 86_400},
    "fund_flow": {"trading": 60, "closed": 3_600},
    "sector_snapshot": {"trading": 60, "closed": 3_600},
    "northbound_flow": {"trading": 300, "closed": 3_600},
    "research_report": {"trading": 21_600, "closed": 21_600},
    "dragon_tiger": {"trading": 86_400, "closed": 86_400},
    "lockup_expiry": {"trading": 86_400, "closed": 86_400},
    "margin_trading": {"trading": 3_600, "closed": 86_400},
    "macro_indicator": {"trading": 86_400, "closed": 86_400},
    "health_check": {"trading": 300, "closed": 1_800},
}


def resolve_cache_ttl(data_category: str, provider_default_seconds: int) -> int:
    policy = TTL_POLICY_SECONDS.get(data_category)
    if not policy:
        return max(provider_default_seconds, 1)
    mode = "trading" if is_trading_time() else "closed"
    return max(policy[mode], 1)
