from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp.

    Replaces the deprecated ``datetime.utcnow()`` while keeping naive
    datetimes so existing columns and comparisons stay unchanged.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
