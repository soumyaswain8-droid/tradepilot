#!/usr/bin/env python3
"""
audit-universe — check our tradeable universe against NSE's own published lists.

WHY THIS EXISTS
A symbol that has been renamed, delisted or moved to a surveillance series does not
throw an error. It simply returns no quote, and the engine skips it silently forever
— the roster looks full while part of it is dead. TATAMOTORS became TMPV after the
demerger and sat dead in the config until someone went looking. This makes that a
check instead of a discovery.

WHAT IT COMPARES
  NSE published indices   nsearchives.nseindia.com/content/indices/ind_nifty*list.csv
                          the authoritative constituent lists, refreshed by NSE
  Kite instrument dump    what is actually tradeable on the exchange today
  our config              ACTIVE_SYMBOLS_YF and quant/universe_expanded.txt

THE -BE TRAP
A stock moved to the BE (Trade-to-Trade) series still has a live quote under
"SYMBOL-BE", so a naive fix is to rename it and move on. That would be wrong here.
T2T requires every trade to end in delivery — intraday netting is prohibited — so an
intraday engine cannot trade a BE stock in the way it assumes. They are reported as
REMOVE, not RENAME, and the reason is stated in the output rather than left to the
reader.

Run:
    python3 scripts/audit-universe.py              # report
    python3 scripts/audit-universe.py --fix        # rewrite universe_expanded.txt
    python3 scripts/audit-universe.py --json out.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import urllib.request
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INDEX_URLS = {
    "NIFTY 50":  "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
    "NIFTY 100": "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv",
    "NIFTY 200": "https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv",
    "NIFTY 500": "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
EXPANDED = ROOT / "quant" / "universe_expanded.txt"

# NSE series codes that mark a line as NOT ordinary main-board equity:
#   BE/BZ trade-to-trade (delivery only)   SM SME board        SG/GS/TB/GB govt secs
#   ST    securitised debt                 SF  ?               IV/ND other
SERIES_SUFFIXES = {"BE", "BZ", "SM", "SG", "ST", "GS", "TB", "SF", "GB", "IV", "ND"}


def fetch_index(url: str) -> set:
    """Constituents from NSE. Returns an empty set on failure — the caller reports
    'could not check' rather than treating a fetch failure as an empty index."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            text = r.read().decode("utf-8-sig")
        return {(row.get("Symbol") or "").strip().upper()
                for row in csv.DictReader(io.StringIO(text)) if row.get("Symbol")}
    except Exception as e:
        print(f"  ! could not fetch {url.rsplit('/', 1)[-1]}: {type(e).__name__}: {e}",
              file=sys.stderr)
        return set()


def kite_listed() -> tuple:
    """(plain tradeable symbols, all EQ symbols incl. suffixed series)."""
    from prototype.v4 import kite_data as kd
    rows = kd._call(lambda: kd.client().instruments("NSE"), "instruments")
    eq = [r for r in rows
          if r.get("segment") == "NSE" and r.get("instrument_type") == "EQ"]
    allsym = {r["tradingsymbol"].upper() for r in eq}
    # A hyphen does NOT mean "series suffix". BAJAJ-AUTO and NAM-INDIA are ordinary
    # NSE symbols that happen to contain one, and the first version of this filter
    # reported BAJAJ-AUTO — a NIFTY 50 constituent trading at Rs 11,625 — as dead.
    # Only the fixed set of real series codes marks a non-main-board line.
    plain = {s for s in allsym
             if not (("-" in s) and s.rsplit("-", 1)[1] in SERIES_SUFFIXES)}
    return plain, allsym


def read_expanded() -> list:
    if not EXPANDED.exists():
        return []
    return [l.strip().replace(".NS", "").upper()
            for l in EXPANDED.read_text().splitlines()
            if l.strip() and not l.startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="rewrite universe_expanded.txt")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead — cannot verify what is tradeable: {detail}",
              file=sys.stderr)
        return 2

    plain, allsym = kite_listed()
    active = {s.replace(".NS", "").upper()
              for s in __import__("prototype.v4.config", fromlist=["x"]).ACTIVE_SYMBOLS_YF}
    expanded = read_expanded()
    exp_set = set(expanded)

    indices = {name: fetch_index(url) for name, url in INDEX_URLS.items()}

    print(f"\n  UNIVERSE AUDIT vs NSE — {len(plain):,} main-board equities listed today\n")
    print(f"  {'index':<12}{'NSE':>6}{'active':>8}{'+expanded':>11}{'missing':>9}")
    cover = {}
    for name, members in indices.items():
        if not members:
            print(f"  {name:<12}  (could not fetch — NOT verified)")
            continue
        both = members & (active | exp_set)
        cover[name] = {"nse": len(members), "active": len(members & active),
                       "combined": len(both), "missing": sorted(members - (active | exp_set))}
        print(f"  {name:<12}{len(members):>6}{len(members & active):>8}"
              f"{len(both):>11}{len(members - (active | exp_set)):>9}")

    # dead symbols — in our config, not tradeable as spelled
    dead = []
    for s in sorted(active | exp_set):
        if s in plain:
            continue
        alt = [x for x in allsym if x.split("-")[0] == s]
        series = alt[0].split("-")[1] if alt and "-" in alt[0] else None
        dead.append({
            "symbol": s,
            "in_active": s in active,
            "alternative": alt[0] if alt else None,
            "series": series,
            # BE/BZ = Trade-to-Trade. Quotes exist, but every trade must end in
            # delivery, so an INTRADAY engine cannot use them as it assumes.
            "verdict": ("REMOVE — moved to Trade-to-Trade (no intraday netting)"
                        if series in ("BE", "BZ")
                        else "REMOVE — not listed on NSE today"),
        })

    print(f"\n  DEAD SYMBOLS IN OUR CONFIG: {len(dead)}")
    for d in dead:
        where = "ACTIVE" if d["in_active"] else "expanded"
        alt = f"  (exists as {d['alternative']})" if d["alternative"] else ""
        print(f"    {d['symbol']:<14} [{where}] {d['verdict']}{alt}")

    if a.fix and dead:
        drop = {d["symbol"] for d in dead if not d["in_active"]}
        if drop:
            # Preserve comment/provenance lines. The first version of --fix wrote
            # only symbols and silently ate the file's header, losing the record of
            # where the list came from.
            out = []
            for line in EXPANDED.read_text().splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    out.append(line)
                elif s.replace(".NS", "").upper() not in drop:
                    out.append(line)
            kept = [l for l in out if l.strip() and not l.startswith("#")]
            EXPANDED.write_text("\n".join(out) + "\n")
            print(f"\n  --fix: removed {len(drop)} dead symbol(s) from "
                  f"{EXPANDED.relative_to(ROOT)} ({len(expanded)} -> {len(kept)})")
        act_dead = [d["symbol"] for d in dead if d["in_active"]]
        if act_dead:
            print(f"  --fix does NOT touch ACTIVE_SYMBOLS_YF; edit prototype/v4/config.py "
                  f"by hand for: {', '.join(act_dead)}")

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"coverage": cover, "dead": dead, "nse_listed": len(plain)},
            indent=2, default=str))
        print(f"\n  wrote {a.json}")
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
