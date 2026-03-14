from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_published_at(value: str | int | float | None) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_published_at(value: str | int | float | None) -> str | None:
    parsed = parse_published_at(value)
    return parsed.isoformat() if parsed else None


def filter_recent_items(
    items: list[dict],
    max_age_hours: int = 24,
    now: datetime | None = None,
    limit: int | None = None,
) -> list[dict]:
    reference_now = now or utc_now()
    cutoff = reference_now - timedelta(hours=max_age_hours)
    recent_items: list[tuple[datetime, dict]] = []

    for item in items:
        published_at = parse_published_at(item.get("published_at"))
        if not published_at:
            continue
        if published_at < cutoff:
            continue
        normalized_item = dict(item)
        normalized_item["published_at"] = published_at.isoformat()
        recent_items.append((published_at, normalized_item))

    recent_items.sort(key=lambda pair: pair[0], reverse=True)
    filtered = [item for _, item in recent_items]
    if limit is not None:
        return filtered[:limit]
    return filtered
