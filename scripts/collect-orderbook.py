#!/usr/bin/env python3
"""
collect-orderbook — snapshot NSE order-book depth. Collection only, trades nothing.

WHY THIS EXISTS
v5's entry signal is measurably worse than random: same stocks, same days, same 1.5%
stop, only the entry TIME differs, and random wins by 0.18%/trade across 5 seeds
(t 2.76-4.24). The cause is structural — all six scoring features are backward-looking
(rs_score means it ALREADY outperformed; orb_score fires only AFTER the range breaks;
fii_score is published end-of-day). Leading weight in the current score: 0.0%.

Order-book depth is the one genuinely leading input we can access. Depth BUILDS
BEFORE price moves — that is the hypothesis, and it is only a hypothesis.

THE REASON THIS IS A COLLECTOR AND NOT A SIGNAL
Kite's historical API returns OHLCV only. No bid/ask, no depth, at any interval —
verified directly. So an order-book signal CANNOT be backtested against anything we
own. It has to be collected forward before it can be tested at all. Every day not
collecting is a day added to the wait, which is why this ships before any model.

WHAT IT RECORDS, every SNAPSHOT_SECONDS during market hours
  per symbol: 5 bid levels + 5 ask levels (price, quantity, orders), last price,
  volume, total buy/sell quantity, spread. Written as newline-delimited JSON,
  one file per day, gzipped at the close.

DESIGN NOTES THAT MATTER
  - It NEVER trades and imports nothing from the engines. A collector that could
    place an order is a collector that can lose money.
  - Depth OUTSIDE 09:15-15:30 is meaningless — checked live at 16:20, RELIANCE showed
    0 bid quantity against 14,970 ask, a -100% "imbalance" that is pure artifact.
    The session gate is therefore a correctness requirement, not politeness.
  - Every snapshot is stamped and flushed immediately. A crash costs the last
    snapshot, not the day.
  - Symbols that fail are recorded as absent, never as zero. A zero bid is a real
    market state and must not be confused with a failed fetch.

Run:
    python3 scripts/collect-orderbook.py                 # run the session
    python3 scripts/collect-orderbook.py --once          # one snapshot, for testing
    python3 scripts/collect-orderbook.py --seconds 15
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")
logger = logging.getLogger("orderbook")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "docs" / "research" / "orderbook"

SNAPSHOT_SECONDS = 30
BATCH = 200                      # Kite quote() cap per call, comfortably under 500
MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)


def in_session(now=None) -> bool:
    """NSE cash session only. Depth outside it is an artifact, not data."""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return (MARKET_OPEN[0] * 60 + MARKET_OPEN[1]) <= mins < (MARKET_CLOSE[0] * 60 + MARKET_CLOSE[1])


def universe() -> list:
    """NIFTY-200 — the engines' actual trading universe. Collecting depth for stocks
    we would never trade would cost calls and buy nothing."""
    from prototype.v4.config import ACTIVE_SYMBOLS_YF
    return [s.replace(".NS", "").upper() for s in ACTIVE_SYMBOLS_YF]


def snapshot(symbols: list) -> list:
    """One depth snapshot for every symbol. Returns a list of records."""
    from prototype.v4 import kite_data as kd

    ts = datetime.now().isoformat(timespec="seconds")
    out = []
    for i in range(0, len(symbols), BATCH):
        chunk = symbols[i:i + BATCH]
        keys = [f"NSE:{s}" for s in chunk]
        try:
            res = kd.client().quote(keys)
        except Exception as e:
            logger.error(f"quote batch failed ({chunk[0]}..): {type(e).__name__}: {e}")
            continue
        for s in chunk:
            q = res.get(f"NSE:{s}")
            if not q:
                continue                      # absent, NOT zero — see module docstring
            d = q.get("depth") or {}
            bids = d.get("buy") or []
            asks = d.get("sell") or []
            bq = sum(int(x.get("quantity") or 0) for x in bids)
            aq = sum(int(x.get("quantity") or 0) for x in asks)
            best_bid = float(bids[0]["price"]) if bids else 0.0
            best_ask = float(asks[0]["price"]) if asks else 0.0
            out.append({
                "ts": ts,
                "sym": s,
                "ltp": float(q.get("last_price") or 0),
                "vol": int(q.get("volume") or 0),
                # the candidate leading feature. Stored as raw components too, so a
                # different formulation can be tried later without recollecting.
                "bid_qty": bq,
                "ask_qty": aq,
                "imbalance": round((bq - aq) / (bq + aq), 5) if (bq + aq) else None,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_bps": round((best_ask - best_bid) / best_bid * 10000, 2)
                              if best_bid > 0 else None,
                "total_buy_qty": int(q.get("buy_quantity") or 0),
                "total_sell_qty": int(q.get("sell_quantity") or 0),
                "bids": [[float(x.get("price") or 0), int(x.get("quantity") or 0),
                          int(x.get("orders") or 0)] for x in bids[:5]],
                "asks": [[float(x.get("price") or 0), int(x.get("quantity") or 0),
                          int(x.get("orders") or 0)] for x in asks[:5]],
            })
    return out


def compress_yesterday():
    """Gzip any finished day's file. Raw depth is bulky and never re-written."""
    today = datetime.now().strftime("%Y-%m-%d")
    for f in OUT_DIR.glob("*.ndjson"):
        if f.stem == today:
            continue
        try:
            with open(f, "rb") as src, gzip.open(f.with_suffix(".ndjson.gz"), "wb") as dst:
                shutil.copyfileobj(src, dst)
            f.unlink()
            logger.info(f"compressed {f.name}")
        except Exception as e:
            logger.warning(f"could not compress {f.name}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=SNAPSHOT_SECONDS)
    ap.add_argument("--once", action="store_true", help="one snapshot then exit")
    ap.add_argument("--force", action="store_true",
                    help="run outside market hours (data will be meaningless)")
    a = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="[%(asctime)s] %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        logger.error(f"Kite token dead — cannot collect: {detail}")
        return 2

    syms = universe()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    compress_yesterday()

    if a.once:
        rows = snapshot(syms)
        logger.info(f"one snapshot: {len(rows)}/{len(syms)} symbols")
        if rows:
            r = rows[0]
            logger.info(f"  sample {r['sym']}: ltp {r['ltp']} bid {r['bid_qty']:,} "
                        f"ask {r['ask_qty']:,} imbalance {r['imbalance']}")
        return 0

    # WAIT for the open rather than refusing it (fixed 2026-08-07).
    #
    # THE BUG THIS REPLACES: the launchd job fires at 09:14 so it is warm for the
    # 09:15 open, but this gate rejected anything outside 09:15-15:30 and exited
    # IMMEDIATELY — with code 0. Two full sessions produced zero bytes while launchd
    # recorded "last exit code = 0" and the log said "exiting cleanly". A success
    # code for a job that collected nothing is the worst possible failure mode,
    # because every check for whether it ran said yes.
    #
    # Now: if the session opens soon, sleep until it does. If it is hours away or
    # already over, exit as before. Refusing to run one minute early was never the
    # safe behaviour — it was the silent one.
    if not in_session() and not a.force:
        now = datetime.now()
        if now.weekday() < 5:
            mins_now = now.hour * 60 + now.minute
            open_min = MARKET_OPEN[0] * 60 + MARKET_OPEN[1]
            wait = open_min - mins_now
            if 0 < wait <= 30:
                logger.info(f"{wait} min before the open — waiting rather than exiting")
                time.sleep(wait * 60 + 5)
        if not in_session():
            logger.info("outside 09:15-15:30 — depth is meaningless here, exiting cleanly")
            return 0

    path = OUT_DIR / f"{datetime.now():%Y-%m-%d}.ndjson"
    logger.info(f"collecting {len(syms)} symbols every {a.seconds}s -> {path.name}")
    n_snap = n_rows = 0
    try:
        while in_session() or a.force:
            t0 = time.time()
            rows = snapshot(syms)
            if rows:
                # append + flush every snapshot: a crash costs one snapshot, not a day
                with open(path, "a") as f:
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
                n_snap += 1
                n_rows += len(rows)
            if n_snap % 20 == 0 and n_snap:
                logger.info(f"{n_snap} snapshots, {n_rows:,} rows, "
                            f"{path.stat().st_size/1e6:.1f} MB")
            if a.once or a.force:
                break
            time.sleep(max(0, a.seconds - (time.time() - t0)))
    except KeyboardInterrupt:
        logger.info("interrupted")
    logger.info(f"done: {n_snap} snapshots, {n_rows:,} rows -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
