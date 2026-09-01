#!/usr/bin/env python3
"""
news-watch — collect stock-specific catalysts and timestamp them HONESTLY.

WHAT THIS IS FOR. Every edge this project has tested is price-derived, and all of
them are dead: sustained runners, cap segments, winner anatomy, breakout — four lanes,
four negatives. News is the one input class never tried systematically. It is also the
only plausible entry signal for a multi-week hold, because a real catalyst (an order
win, a results surprise, a regulatory change) has a mechanism for persisting over weeks
in a way that "the stock rose 5% yesterday" demonstrably does not.

WHY IT ONLY OBSERVES, AND WHY THAT IS NOT TIMIDITY. Google News RSS re-stamps old
articles with fresh pubDates — an April story surfaced as "4h ago" in July, which is
why prototype/news_utils.py exists. That means NO HISTORICAL NEWS BACKTEST IS
TRUSTWORTHY: you cannot establish when the information actually became public, so any
edge you measure may be pure look-ahead. The one timestamp nobody can re-stamp is our
own observation. `first_seen_utc` is this file's whole point — everything else is
supporting detail. Forward collection is not the cautious option, it is the only honest
one.

ARCHITECTURE. Polling ~890 symbols individually would be slow and rate-limited. Instead
pull a handful of broad feeds often and MATCH article text against a symbol -> company
name map built from the Kite instrument dump. One fetch covers the whole universe.

    python3 scripts/news-watch.py            # one pass, appends to the ledger
    python3 scripts/news-watch.py --loop 300 # poll every 5 minutes
    python3 scripts/news-watch.py --stats    # what has been collected so far

Ledger: docs/sarathi/knowledge/news/YYYY-MM-DD.jsonl, one JSON object per matched item.
Deliberately append-only and deduplicated on a content hash — feeds repeat the same
story for hours and a naive collector would record one event fifty times, which would
then look like fifty independent confirmations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LEDGER = ROOT / "docs" / "sarathi" / "knowledge" / "news"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) TradePilot/news-watch"

# Broad feeds, deliberately not per-symbol. `when:1d` is load-bearing — without it
# Google returns evergreen items with today's pubDate (see news_utils.py).
# India: symbol-level catalysts. Items here are kept ONLY if they name a listed company.
FEEDS_IN = [
    ("https://news.google.com/rss/search?q=nse+india+company+results+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "results"),
    ("https://news.google.com/rss/search?q=india+company+order+win+contract+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "order"),
    ("https://news.google.com/rss/search?q=india+stock+brokerage+target+upgrade+downgrade+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "rating"),
    ("https://news.google.com/rss/search?q=sebi+rbi+india+company+regulatory+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "regulatory"),
    ("https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en", "business"),
]

# GLOBAL: the overnight edge. India trades 09:15-15:30 IST; the US session runs roughly
# 19:00-01:30 IST and Europe 12:30-21:00 IST, so the single largest block of
# price-forming information for an Indian open arrives while nobody here is awake. By
# 09:15 it is already in the gap — the only way to have it BEFORE the open is to have
# been collecting through the night.
#
# These are kept WITHOUT requiring an Indian symbol match. That is the whole point: a
# Fed decision, a crude spike or an Nvidia miss names no NSE company and would be
# dropped by the symbol filter, yet moves the Indian open more reliably than most
# company news does.
FEEDS_GLOBAL = [
    ("https://news.google.com/rss/search?q=federal+reserve+interest+rate+decision+when:1d&hl=en-US&gl=US&ceid=US:en", ("US", "macro")),
    ("https://news.google.com/rss/search?q=us+stocks+dow+nasdaq+s%26p+500+close+when:1d&hl=en-US&gl=US&ceid=US:en", ("US", "equity")),
    ("https://news.google.com/rss/search?q=crude+oil+brent+price+when:1d&hl=en-US&gl=US&ceid=US:en", ("GLOBAL", "commodity")),
    ("https://news.google.com/rss/search?q=gold+copper+metals+price+when:1d&hl=en-US&gl=US&ceid=US:en", ("GLOBAL", "commodity")),
    ("https://news.google.com/rss/search?q=dollar+index+rupee+currency+when:1d&hl=en-US&gl=US&ceid=US:en", ("GLOBAL", "fx")),
    ("https://news.google.com/rss/search?q=asian+markets+nikkei+hang+seng+when:1d&hl=en-US&gl=US&ceid=US:en", ("ASIA", "equity")),
    ("https://news.google.com/rss/search?q=europe+stocks+ecb+dax+ftse+when:1d&hl=en-US&gl=US&ceid=US:en", ("EU", "equity")),
    ("https://news.google.com/rss/search?q=semiconductor+chip+nvidia+tsmc+when:1d&hl=en-US&gl=US&ceid=US:en", ("US", "sector")),
    ("https://news.google.com/rss/search?q=global+trade+tariff+geopolitics+oil+supply+when:1d&hl=en-US&gl=US&ceid=US:en", ("GLOBAL", "geopolitics")),
]

# A global headline is only worth recording if it plausibly moves an Indian open.
# Without this the macro feeds bury the ledger in generic business copy.
GLOBAL_RELEVANT = re.compile(
    r"\b(fed|federal reserve|rate (cut|hike|decision)|inflation|cpi|payroll|"
    r"treasury|yield|recession|tariff|sanction|opec|crude|brent|wti|"
    r"gold|copper|nikkei|hang seng|shanghai|dax|ftse|ecb|boj|"
    r"dollar|rupee|yuan|yen|semiconductor|chip|nvidia|tsmc|"
    r"rally|selloff|plunge|surge|slump|record high|correction|war|strike)\b", re.I)

# Rule-based, NOT an LLM. Auditable, deterministic, free, and reproducible six months
# from now — an LLM classification cannot be re-derived once the model changes, which
# makes it unusable as the label in a study. Upgrade only if these prove too coarse.
CATALYST = [
    ("results",    r"\b(q[1-4]|quarter|results|profit|revenue|earnings|pat|ebitda)\b"),
    ("order",      r"\b(order|contract|bags|wins|awarded|loi|tender|deal worth)\b"),
    ("rating",     r"\b(upgrade|downgrade|target price|buy call|sell call|initiat\w+ coverage)\b"),
    ("regulatory", r"\b(sebi|rbi|cci|nclt|probe|penalty|ban|approval|licence|license)\b"),
    ("corporate",  r"\b(merger|acquisition|acquire|stake|demerger|bonus|split|dividend|buyback|fund ?rais)\b"),
    ("management", r"\b(resign|appoint|ceo|cfo|managing director|board meeting)\b"),
]

# Auto-generated pages that restate the price and carry no information. The first live
# run matched 65 items of which a large share were these — "HCLTECH Share Price Today -
# scanx.com", "HDFC Bank Gains 0.52% to Rs 1,742.30". They are not merely useless: a
# ledger full of them would show catalyst density tracking PRICE MOVEMENT, because these
# pages are generated when a stock moves. That is a manufactured correlation, and it
# would point the exact wrong way — news appearing to predict moves it was produced by.
SPAM = re.compile(
    r"share price (today|live|target)|stock price today|"
    r"\b(gains?|falls?|rises?|drops?|slips?|jumps?|surges?|declines?)\b[^|]*\b\d+(\.\d+)?%"
    r"|scanx|moneycontrol\.com/india/stockpricequote|/quote/|"
    r"live blog|market live updates|closing bell|opening bell|"
    r"top (gainers|losers)|stocks to (watch|buy) today|multibagger",
    re.I)

# Words that are real companies AND common English. Matching on these produces a flood
# of false positives that would swamp the ledger and, worse, look like signal.
STOP_NAMES = {"india", "bank", "power", "steel", "auto", "motors", "finance", "energy",
              "industries", "limited", "ltd", "corporation", "national", "state", "union",
              "central", "eco", "one", "just", "info", "tech", "digital", "global", "max",
              "best", "gold", "silver", "green", "sun", "star", "orient", "trident"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _which_session() -> str:
    """Which market was awake when we saw this, in IST.

    Recorded because it is the field that makes the overnight thesis testable: an item
    first seen in OVERNIGHT_US is information we hold before the Indian open, and its
    value can be measured against the next open's gap. One first seen in IN_SESSION is
    already in the price by the time we act on it.
    """
    h = datetime.now().hour
    if 9 <= h < 16:
        return "IN_SESSION"
    if 16 <= h < 19:
        return "IN_POST"
    if 19 <= h or h < 2:
        return "OVERNIGHT_US"
    if 2 <= h < 7:
        return "OVERNIGHT_LATE"
    return "IN_PRE"                      # 07:00-09:00, the window that matters most


def _english_words() -> set:
    """Common English words, for rejecting generic single-token company names.

    413 companies reduce to a single token, and the ordinary-word ones are poison:
    SIL resolves to 'standard' and matched a headline about Milky Mist because the
    article happened to contain the word. A hand-maintained stoplist will always lag
    the instrument dump, so consult the system dictionary instead — a name that is
    also an English word cannot be matched safely on headline text alone.
    """
    for p in ("/usr/share/dict/words", "/usr/dict/words"):
        f = Path(p)
        if f.exists():
            try:
                return {w.strip().lower() for w in f.read_text(errors="ignore").splitlines()
                        if len(w.strip()) >= 4}
            except Exception:
                break
    return set()


def symbol_names() -> dict:
    """symbol -> a matchable company name, from the Kite instrument dump."""
    from prototype.agents.scouts import ScoutTeam
    raw = ScoutTeam(verbose=False)._instrument_names()
    english = _english_words()
    out = {}
    for sym, name in raw.items():
        if not name or sym.startswith("NIFTY") or " " in sym:
            continue
        n = re.sub(r"\b(ltd|limited|india|indian|corp|corporation|co|company|"
                   r"industries|enterprises|the)\b", " ", str(name).lower())
        n = re.sub(r"[^a-z0-9 ]", " ", n)
        n = re.sub(r"\s+", " ", n).strip()
        # a one-token name that is also an ordinary English word is unmatchable
        if len(n) < 4 or n in STOP_NAMES:
            continue
        if " " not in n and (n in english or n.rstrip("s") in english):
            continue                    # 'standard', 'orient', 'trident' ...
        out[sym] = n
    return out


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def parse_items(xml: str) -> list:
    items = []
    for blk in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def tag(t):
            m = re.search(rf"<{t}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>", blk, re.S)
            return (m.group(1).strip() if m else "")
        items.append({"title": re.sub(r"<[^>]+>", "", tag("title")),
                      "link": tag("link"), "pubdate": tag("pubDate"),
                      "source": tag("source")})
    return items


def classify(text: str) -> str:
    t = text.lower()
    for label, pat in CATALYST:
        if re.search(pat, t):
            return label
    return "other"


def match_symbols(title: str, names: dict) -> list:
    """Which listed companies does this headline name?

    Requires a full multi-word match or a distinctive single token. Substring matching
    on short names is how 'ONE' matches every headline containing the word one.
    """
    t = " " + re.sub(r"[^a-z0-9 ]", " ", title.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    hits = []
    for sym, name in names.items():
        if " " in name:
            if f" {name} " in t:
                hits.append(sym)
        elif len(name) >= 6 and f" {name} " in t:
            hits.append(sym)
    return hits


def seen_hashes(day: str) -> set:
    f = LEDGER / f"{day}.jsonl"
    if not f.exists():
        return set()
    out = set()
    for ln in f.read_text().splitlines():
        try:
            out.add(json.loads(ln)["hash"])
        except Exception:
            continue
    return out


def run_once(names: dict, verbose: bool = True) -> int:
    LEDGER.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    have = seen_hashes(day)
    rows, feeds_ok = [], 0

    sources = ([(u, b, "IN", None) for u, b in FEEDS_IN] +
               [(u, t, r, t) for u, (r, t) in FEEDS_GLOBAL])

    for url, bucket, region, theme in sources:
        try:
            items = parse_items(fetch(url))
            feeds_ok += 1
        except Exception as e:
            if verbose:
                print(f"  feed FAILED ({bucket}): {str(e)[:60]}", flush=True)
            continue
        for it in items:
            title = it["title"]
            if not title:
                continue
            cat = classify(title)
            # Spam only applies to headlines with no catalyst in them. The movement
            # pattern ("rises 34%") also fires on real news — "Tata Motors Q2 results:
            # profit rises 34%" was being discarded as a price page. Losing a genuine
            # catalyst is far worse than admitting a scraper headline, so a recognised
            # catalyst always wins.
            if cat == "other" and (SPAM.search(title) or SPAM.search(it.get("link", ""))):
                continue
            h = hashlib.sha1(title.lower().encode()).hexdigest()[:16]
            if h in have:
                continue
            syms = match_symbols(title, names)

            # Two admission rules, because the two feed sets answer different questions.
            # India: keep only what names a listed company — unattributed Indian macro
            # is already served by the dashboard's existing feed.
            # Global: keep it WITHOUT a symbol, because the value is precisely that it
            # moves the whole market before we open. Requiring an NSE name here would
            # discard every Fed decision and crude spike, which is the overnight edge.
            if region == "IN":
                if not syms:
                    continue
            elif not (syms or GLOBAL_RELEVANT.search(title)):
                continue

            have.add(h)
            rows.append({
                # OUR clock. The only timestamp in this record that cannot be
                # re-stamped by the publisher, and therefore the only one a forward
                # study may use.
                "first_seen_utc": _now(),
                "hash": h,
                "symbols": syms,
                "catalyst": cat,
                # region/theme carry the overnight context: an item with no symbols and
                # region != IN is market-level information that landed while India slept
                "region": region,
                "theme": theme,
                "session": _which_session(),
                "feed_bucket": bucket,
                "title": title,
                "link": it["link"],
                "source": it["source"],
                # kept for comparison, explicitly NOT trusted — see module docstring
                "publisher_pubdate": it["pubdate"],
            })

    if rows:
        with (LEDGER / f"{day}.jsonl").open("a") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    if verbose:
        print(f"  {datetime.now():%H:%M:%S}  feeds {feeds_ok}/{len(sources)}  "
              f"session {_which_session()}  new items: {len(rows)}", flush=True)
        for r in rows[:8]:
            who = ",".join(r["symbols"])[:20] or f"[{r['region']}/{r['theme']}]"
            print(f"    {who:<22} [{r['catalyst']:<10}] {r['title'][:60]}", flush=True)
    return len(rows)


def stats() -> None:
    import collections
    files = sorted(LEDGER.glob("*.jsonl"))
    if not files:
        print("  no news collected yet")
        return
    rows = []
    for f in files:
        for ln in f.read_text().splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    print(f"  {len(rows)} items across {len(files)} day(s)")
    print("  by region   :", dict(collections.Counter(r.get("region", "?") for r in rows)))
    print("  by session  :", dict(collections.Counter(r.get("session", "?") for r in rows)))
    print("  by catalyst :", dict(collections.Counter(r["catalyst"] for r in rows)))
    print("  by theme    :", dict(collections.Counter(
        r["theme"] for r in rows if r.get("theme"))))
    syms = collections.Counter(s for r in rows for s in r["symbols"])
    print("  distinct symbols:", len(syms))
    print("  most mentioned  :", dict(syms.most_common(6)))
    # the overnight count is the number this whole change exists to make non-zero
    on = sum(1 for r in rows if r.get("session", "").startswith("OVERNIGHT"))
    print(f"  collected while India slept: {on}")


def in_active_hours() -> bool:
    """Always true. Collection runs 24/7, weekends included.

    It briefly did not, and that was a mistake worth recording: an earlier version
    slept 21:00-07:00 IST "to be polite to the feeds", which switched the collector off
    for the ENTIRE US session (roughly 19:00-01:30 IST) — the single largest block of
    price-forming information ahead of an Indian open. It would have collected only
    news that was already in the price by the time we could act on it, and the whole
    argument for watching global markets is that the value lives in the hours nobody
    here is awake.

    The cost of running through the night is nine HTTP fetches every fifteen minutes,
    almost all of which dedupe to nothing. That is not worth optimising against the
    thing the collector exists to capture.
    """
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="seconds between passes")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--scheduled", action="store_true",
                    help="exit quietly outside active hours (for launchd)")
    a = ap.parse_args()
    if a.stats:
        stats()
        return 0
    if a.scheduled and not in_active_hours():
        return 0
    names = symbol_names()
    print(f"  matching against {len(names)} listed companies", flush=True)
    if not a.loop:
        run_once(names)
        return 0
    print(f"  polling every {a.loop}s — observer only, places no trades", flush=True)
    while True:
        try:
            run_once(names)
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print(f"  pass failed: {str(e)[:80]}", flush=True)
        time.sleep(a.loop)


if __name__ == "__main__":
    sys.exit(main())
