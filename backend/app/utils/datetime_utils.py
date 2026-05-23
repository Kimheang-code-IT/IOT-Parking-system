from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; normalize for safe arithmetic."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_display_datetime(dt: datetime | None, with_am_pm: bool = False) -> str:
    if not dt:
        return "-"
    local = ensure_utc(dt).astimezone()
    if with_am_pm:
        return local.strftime("%Y-%m-%d %I:%M %p").replace(" 0", " ")
    return local.strftime("%Y-%m-%d %H:%M")


def format_iso(dt: datetime) -> str:
    return ensure_utc(dt).isoformat()


def format_date_only(dt: datetime) -> str:
    return ensure_utc(dt).astimezone().strftime("%Y-%m-%d")


def duration_between(start: datetime, end: datetime) -> tuple[int, str, str]:
    """Returns (total_minutes, short_display, long_display)."""
    start_utc = ensure_utc(start)
    end_utc = ensure_utc(end)
    delta = end_utc - start_utc
    total_minutes = max(int(delta.total_seconds() // 60), 0)
    hours, minutes = divmod(total_minutes, 60)
    short = f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
    if hours and minutes:
        long = f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
    elif hours:
        long = f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        long = f"{minutes} minute{'s' if minutes != 1 else ''}"
    return total_minutes, short, long
