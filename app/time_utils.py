"""UTC persistence and Korean display helpers."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def utc_now():
    return datetime.now(timezone.utc)


def to_kst(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KST)


def format_kst(value, fmt="%Y.%m.%d %H:%M"):
    converted = to_kst(value)
    return converted.strftime(fmt) if converted else "-"
