from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def local_today() -> date:
    return datetime.now(SHANGHAI).date()


def as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("时间必须包含时区")
    return value.astimezone(UTC).replace(tzinfo=None)


def as_shanghai(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC).astimezone(SHANGHAI)


def period_code(value: datetime) -> str:
    local = as_shanghai(value)
    if local.hour < 12:
        return "morning"
    if local.hour < 17:
        return "afternoon"
    return "sunset"
