"""Helpers for the Market Intelligence news feed (dashboard /api/bots/geopolitical).

Why this exists (2026-07-12): Google News RSS re-stamps old articles with fresh
pubDates — an April "Good Friday" story surfaced as "4h ago" in July. The feed
route now (a) adds when:1d to the search queries, (b) drops items whose pubDate
is older than max_age_h, and (c) strips HTML from summaries. The pure logic for
(b) and (c) lives here so it is unit-testable (tests/test_news_feed.py).
"""
import html
import re
from email.utils import parsedate_to_datetime

_TAG_RE = re.compile(r"<[^>]+>")


def clean_summary(desc, limit=200):
    """Strip HTML tags, unescape entities, collapse whitespace, truncate."""
    if not desc:
        return ""
    text = _TAG_RE.sub(" ", desc)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def is_recent(pubdate_rfc, now_rfc=None, max_age_h=48):
    """True iff an RFC-2822 pubDate is within max_age_h of now.

    Unparseable/missing dates are NOT recent — Google always supplies a
    pubDate, so a missing one means a malformed item, and the failure mode
    we are guarding against is stale content sneaking in.
    """
    if not pubdate_rfc:
        return False
    try:
        dt = parsedate_to_datetime(pubdate_rfc)
        now = parsedate_to_datetime(now_rfc) if now_rfc else None
        if now is None:
            from datetime import datetime
            now = datetime.now(dt.tzinfo)
        return (now - dt).total_seconds() <= max_age_h * 3600
    except Exception:
        return False
