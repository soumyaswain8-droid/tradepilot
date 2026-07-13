"""Market Intelligence feed hygiene — tests for prototype/news_utils.py.

Bug (2026-07-12): Google News RSS re-stamps old articles with fresh pubDates,
so the dashboard showed an April "Good Friday" story as "4h ago" in July, and
raw <a href=...> HTML leaked into summaries.

Run with: python3 -m pytest tests/test_news_feed.py -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "prototype"))

from news_utils import clean_summary, is_recent


class TestCleanSummary(unittest.TestCase):
    def test_strips_anchor_tags(self):
        raw = '<a href="https://news.google.com/rss/x?oc=5" target="_blank">Sensex rises</a>'
        self.assertEqual(clean_summary(raw), "Sensex rises")

    def test_unescapes_entities(self):
        self.assertEqual(clean_summary("M&amp;M rallies &gt; 5%"), "M&M rallies > 5%")

    def test_truncates_to_limit(self):
        self.assertEqual(len(clean_summary("x" * 500, limit=200)), 200)

    def test_empty_and_none_safe(self):
        self.assertEqual(clean_summary(""), "")
        self.assertEqual(clean_summary(None), "")


class TestIsRecent(unittest.TestCase):
    NOW = "Sun, 12 Jul 2026 12:00:00 GMT"

    def test_same_day_is_recent(self):
        self.assertTrue(is_recent("Sun, 12 Jul 2026 08:00:00 GMT", now_rfc=self.NOW))

    def test_yesterday_is_recent(self):
        self.assertTrue(is_recent("Sat, 11 Jul 2026 13:00:00 GMT", now_rfc=self.NOW))

    def test_three_months_old_is_not_recent(self):
        # the actual Good Friday regression
        self.assertFalse(is_recent("Fri, 03 Apr 2026 09:00:00 GMT", now_rfc=self.NOW))

    def test_older_than_max_age_is_not_recent(self):
        self.assertFalse(is_recent("Wed, 08 Jul 2026 12:00:00 GMT",
                                   now_rfc=self.NOW, max_age_h=48))

    def test_unparseable_pubdate_is_not_recent(self):
        self.assertFalse(is_recent("garbage", now_rfc=self.NOW))
        self.assertFalse(is_recent("", now_rfc=self.NOW))
        self.assertFalse(is_recent(None, now_rfc=self.NOW))


if __name__ == "__main__":
    unittest.main()
