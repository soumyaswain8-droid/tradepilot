#!/usr/bin/env python3
"""Fetch upcoming corporate actions from NSE and merge into prototype/data/corp_actions.json.

Run nightly (or manually) to keep the calendar fresh. Failure is non-fatal — the
existing JSON remains in place. RiskManager.load_corp_actions_file() reads the file
on every init, so the engine stays protected with whatever data is on disk.

Usage:
    python3 scripts/fetch_corp_actions.py            # fetch + merge, keep manual entries
    python3 scripts/fetch_corp_actions.py --dry-run  # show what would be added, don't write
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CORP_ACTIONS_FILE = ROOT / "prototype" / "data" / "corp_actions.json"

NSE_URL = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
NSE_HOME = "https://www.nseindia.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_HOME,
}

# NSE returns "subject" strings like "INTERIM DIVIDEND - RS 5 PER SHARE",
# "STOCK SPLIT FROM RS 10 TO RS 1", "BONUS 1:1", "SCHEME OF ARRANGEMENT" (demerger).
# We map a few — anything else stays "OTHER".
ACTION_KEYWORDS = [
    ("DEMERGER",       ["DEMERGER", "SCHEME OF ARRANGEMENT", "ARRANGEMENT"]),
    ("SPLIT",          ["SPLIT", "SUB-DIVISION", "SUBDIVISION"]),
    ("BONUS",          ["BONUS"]),
    ("DIVIDEND",       ["DIVIDEND"]),
    ("RIGHTS",         ["RIGHTS"]),
    ("BUYBACK",        ["BUYBACK", "BUY-BACK"]),
]


def classify(subject: str) -> str:
    s = (subject or "").upper()
    for label, keys in ACTION_KEYWORDS:
        if any(k in s for k in keys):
            return label
    return "OTHER"


def fetch_nse() -> list:
    """Return list of NSE corp-action records, or [] on any failure."""
    try:
        # Prime the session — NSE blocks API calls without a homepage cookie
        import http.cookiejar
        from urllib.request import build_opener, HTTPCookieProcessor
        cj = http.cookiejar.CookieJar()
        opener = build_opener(HTTPCookieProcessor(cj))
        opener.addheaders = list(HEADERS.items())
        opener.open(NSE_HOME, timeout=10).read(1024)  # warm cookies
        resp = opener.open(NSE_URL, timeout=15)
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        print(f"[fetch_corp_actions] NSE fetch failed: {e}", file=sys.stderr)
        return []


def normalize(records: list, lookahead_days: int = 14) -> list:
    """Convert NSE records into our event schema, keeping ex-dates within window."""
    today = date.today()
    horizon = today + timedelta(days=lookahead_days)
    events = []
    for rec in records:
        ex_str = rec.get("exDate") or rec.get("ex_date") or ""
        symbol = rec.get("symbol") or rec.get("Symbol") or ""
        subject = rec.get("subject") or rec.get("purpose") or ""
        if not ex_str or not symbol:
            continue
        # NSE date format: "30-Apr-2026"
        for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                ex_date = datetime.strptime(ex_str, fmt).date()
                break
            except ValueError:
                continue
        else:
            continue
        if ex_date < today - timedelta(days=1) or ex_date > horizon:
            continue
        events.append({
            "symbol": symbol.strip().upper(),
            "ex_date": ex_date.isoformat(),
            "action_type": classify(subject),
            "note": subject.strip()[:160],
        })
    return events


def merge(existing: dict, new_events: list) -> dict:
    """Merge new events into existing JSON, dedup on (symbol, ex_date)."""
    key = lambda e: (e["symbol"], e["ex_date"])
    have = {key(e): e for e in existing.get("events", [])}
    added = 0
    for e in new_events:
        if key(e) not in have:
            have[key(e)] = e
            added += 1
    existing["events"] = sorted(have.values(), key=lambda e: (e["ex_date"], e["symbol"]))
    existing["_updated"] = date.today().isoformat()
    existing["_last_fetch"] = datetime.now().isoformat()
    existing["_last_fetch_added"] = added
    return existing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Show diff without writing")
    ap.add_argument("--lookahead", type=int, default=14, help="Days ahead to keep")
    args = ap.parse_args()

    records = fetch_nse()
    new_events = normalize(records, args.lookahead)
    print(f"[fetch_corp_actions] NSE returned {len(records)} records, {len(new_events)} in window")

    if not CORP_ACTIONS_FILE.exists():
        existing = {"_doc": "auto-created", "events": []}
    else:
        existing = json.loads(CORP_ACTIONS_FILE.read_text())

    before = len(existing.get("events", []))
    merged = merge(existing, new_events)
    after = len(merged.get("events", []))

    if args.dry_run:
        print(f"[dry-run] Would change events: {before} -> {after} (added {merged.get('_last_fetch_added', 0)})")
        for e in new_events[:10]:
            print(f"  + {e['symbol']:12} {e['ex_date']}  {e['action_type']:10} {e['note'][:50]}")
        return

    CORP_ACTIONS_FILE.write_text(json.dumps(merged, indent=2))
    print(f"[fetch_corp_actions] events {before} -> {after}, added {merged.get('_last_fetch_added', 0)}")


if __name__ == "__main__":
    main()
