#!/usr/bin/env python3
"""Universe hygiene: resolve stale/renamed NSE tickers in stock_universe.py.

NSE renames/demerges/drops tickers; the hardcoded universe drifts. This verifies
each stale symbol's candidate replacement against Yahoo (must return data with a
recent last bar) and only applies CONFIRMED mappings — a wrong mapping would load
the wrong company's data, worse than a missing symbol.

Usage:
  python3 scripts/fix-stale-tickers.py            # dry-run: verify + print
  python3 scripts/fix-stale-tickers.py --apply    # edit stock_universe.py + download
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "prototype" / "data"
UNIVERSE = ROOT / "prototype" / "stock_universe.py"
FRESH_CUTOFF = "2026-06-01"

# old NSE symbol -> ordered candidate replacements (first verified one wins).
# Includes the original (retry) in case the earlier failure was transient.
CANDIDATES = {
    "AARTI":      ["AARTIIND"],
    "AMARAJABAT": ["ARE&M"],
    "BIRLACORP":  ["BIRLACORPN"],
    "BIRLASOFT":  ["BSOFT"],
    "CADILAHC":   ["ZYDUSLIFE"],
    "GMRINFRA":   ["GMRAIRPORT"],
    "GSPL":       ["GSPL"],            # likely transient — retry same
    "IIFLWAM":    ["360ONE"],
    "JSPL":       ["JINDALSTEL"],
    "KALPATPOWR": ["KPIL"],
    "KAMEDICA":   ["KAMEDICA"],        # uncertain — retry only
    "L&TFH":      ["LTF"],
    "LTIM":       ["LTIM"],            # correct ticker — retry
    "MAHINDCIE":  ["CIEINDIA"],
    "MAZAGON":    ["MAZDOCK"],
    "MCDOWELL-N": ["UNITDSPR"],
    "MINDA":      ["UNOMINDA"],
    "NALCO":      ["NATIONALUM"],
    "PI":         ["PIIND"],
    "PRISMJOINS": ["PRSMJOHNSN"],
    "SPICEJET":   ["SPICEJET"],        # retry
    "SUNDARMHLD": ["SUNDARMHLD"],      # uncertain — retry
    "SUVENPHAR":  ["SUVENPHAR"],       # correct — retry
    "TATAMOTORS": ["TATAMOTORS", "TMPV", "TATAMTRDVR"],  # demerger — retry + guesses
    "VEDANTFASH": ["MANYAVAR"],
    "VINATIORG":  ["VINATIORG"],       # retry
    "VRL":        ["VRLLOG"],
    "ZENSAR":     ["ZENSARTECH"],
    "ZOMATO":     ["ETERNAL"],
}


def _nm(sym):
    return sym.replace(".", "_").replace("&", "_").replace("=", "_").replace("-", "_")


def verify(ticker):
    """Return (ok, last_date) — ok only if Yahoo returns data with a recent last bar."""
    import yfinance as yf
    try:
        df = yf.Ticker(f"{ticker}.NS").history(period="1mo", interval="1d")
        if df is None or len(df) < 5:
            return False, None
        last = str(df.index[-1].date())
        return last >= FRESH_CUTOFF, last
    except Exception:
        return False, None


def download_full(ticker):
    import yfinance as yf
    df = yf.Ticker(f"{ticker}.NS").history(period="2y", interval="1d")
    if df is None or len(df) < 20:
        return False
    df.index = df.index.tz_localize(None)
    df.to_csv(DATA / f"{_nm(ticker + '.NS')}.csv")
    return True


def audit():
    """Rot-guard: flag NIFTY_500 symbols with missing or stale (>10 trading days
    behind the freshest) CSVs, so universe drift is caught before it rots silently.
    Run periodically (e.g. weekly) or after any data refresh."""
    sys.path.insert(0, str(ROOT / "prototype"))
    from stock_universe import NIFTY_500
    last_dates, missing, stale = [], [], []
    for s in NIFTY_500:
        p = DATA / f"{_nm(s)}.csv"
        if not p.exists():
            missing.append(s); continue
        try:
            last_dates.append((s, p.read_text().strip().splitlines()[-1].split(",")[0]))
        except Exception:
            missing.append(s)
    freshest = max((d for _, d in last_dates), default="")
    for s, d in last_dates:
        if d < freshest[:8] + "01" and d < freshest:  # crude: a full month behind
            stale.append((s, d))
    print(f"Universe audit — NIFTY_500: {len(NIFTY_500)} symbols, freshest bar {freshest}")
    print(f"  MISSING CSV ({len(missing)}): {missing}")
    print(f"  STALE ({len(stale)}): {[f'{s}:{d}' for s, d in stale]}")
    if missing or stale:
        print("  -> run: python3 scripts/fix-stale-tickers.py  (resolve renames)")
        print("  ->  or: python3 scripts/download-all-data.py  (refresh)")


def main():
    if "--audit" in sys.argv:
        audit()
        return
    apply = "--apply" in sys.argv
    confirmed = {}   # old -> new
    unresolved = []
    for old, cands in CANDIDATES.items():
        hit = None
        for c in cands:
            ok, last = verify(c)
            if ok:
                hit = (c, last)
                break
        if hit:
            confirmed[old] = hit[0]
            tag = "(same/transient)" if hit[0] == old else f"-> {hit[0]}"
            print(f"  CONFIRMED {old:12s} {tag:22s} last={hit[1]}")
        else:
            unresolved.append(old)
            print(f"  UNRESOLVED {old:12s} (tried {cands}) — leave out (engine FLATs safely)")

    renames = {o: n for o, n in confirmed.items() if n != o}
    retries = {o for o, n in confirmed.items() if n == o}
    print(f"\nSummary: {len(confirmed)} confirmed ({len(renames)} renames, {len(retries)} transient), "
          f"{len(unresolved)} unresolved")

    if not apply:
        print("\n(dry-run — re-run with --apply to edit stock_universe.py + download)")
        return

    # 1) download CSVs for every confirmed ticker (renames + transient retries)
    print("\nDownloading confirmed tickers...")
    for old, new in confirmed.items():
        print(f"  {new}: {'OK' if download_full(new) else 'FAILED'}")

    # 2) rewrite stock_universe.py for renames only (string replace "OLD.NS" -> "NEW.NS")
    text = UNIVERSE.read_text()
    for old, new in renames.items():
        text = text.replace(f'"{old}.NS"', f'"{new}.NS"')
    UNIVERSE.write_text(text)
    print(f"\nUpdated {UNIVERSE} with {len(renames)} renames.")
    if unresolved:
        print(f"Unresolved (still in universe, will read as missing -> FLAT): {unresolved}")


if __name__ == "__main__":
    main()
