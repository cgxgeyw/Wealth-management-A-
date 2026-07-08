from datetime import datetime, time
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def is_trading_day(value: datetime | None = None) -> bool:
    current = value.astimezone(CN_TZ) if value else now_cn()
    return current.weekday() < 5


def is_trading_time(value: datetime | None = None) -> bool:
    current = value.astimezone(CN_TZ) if value else now_cn()
    if not is_trading_day(current):
        return False
    current_time = current.time()
    return time(9, 30) <= current_time <= time(11, 30) or time(13, 0) <= current_time <= time(15, 0)
