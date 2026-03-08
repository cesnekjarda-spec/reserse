import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser


def build_guid_hash(url: str, title: str, published_at: datetime | None, external_guid: str | None) -> str:
    raw = external_guid or f"{url}|{title}|{published_at.isoformat() if published_at else ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_published(entry) -> datetime | None:
    if getattr(entry, "published", None):
        try:
            dt = parsedate_to_datetime(entry.published)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def clean_summary(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def parse_feed(rss_url: str):
    return feedparser.parse(rss_url)
