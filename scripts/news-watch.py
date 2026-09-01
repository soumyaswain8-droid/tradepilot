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
FEEDS = [
    ("https://news.google.com/rss/search?q=nse+india+company+results+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "results"),
    ("https://news.google.com/rss/search?q=india+company+order+win+contract+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "order"),
    ("https://news.google.com/rss/search?q=india+stock+brokerage+target+upgrade+downgrade+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "rating"),
    ("https://news.google.com/rss/search?q=sebi+rbi+india+company+regulatory+when:1d&hl=en-IN&gl=IN&ceid=IN:en", "regulatory"),
    ("https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en", "business"),
]

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

    for url, bucket in FEEDS:
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
            if not syms:
                continue                    # macro news is already covered elsewhere
            have.add(h)
            rows.append({
                # OUR clock. The only timestamp in this record that cannot be
                # re-stamped by the publisher, and therefore the only one a forward
                # study may use.
                "first_seen_utc": _now(),
                "hash": h,
                "symbols": syms,
                "catalyst": classify(title),
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
        print(f"  {datetime.now():%H:%M:%S}  feeds {feeds_ok}/{len(FEEDS)}  "
              f"new matched items: {len(rows)}", flush=True)
        for r in rows[:6]:
            print(f"    {','.join(r['symbols'])[:22]:<22} [{r['catalyst']:<10}] "
                  f"{r['title'][:64]}", flush=True)
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
    print("  by catalyst :", dict(collections.Counter(r["catalyst"] for r in rows)))
    syms = collections.Counter(s for r in rows for s in r["symbols"])
    print("  distinct symbols:", len(syms))
    print("  most mentioned  :", dict(syms.most_common(6)))


ACTIVE_HOURS = (7, 21)          # IST, inclusive start / exclusive end


def in_active_hours() -> bool:
    """Collect 07:00-21:00 IST, every day including weekends.

    Not restricted to market hours on purpose: results, order wins and regulatory
    orders are routinely announced after the close and over weekends, and the point of
    forward collection is to timestamp WHEN WE COULD FIRST HAVE KNOWN. Skipping the
    overnight window is politeness to the feeds, not a view about when news matters —
    anything published at 03:00 is picked up by the 07:00 pass with an honest
    first_seen a few hours later, which is the correct record of our knowledge.
    """
    return ACTIVE_HOURS[0] <= datetime.now().hour < ACTIVE_HOURS[1]


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
