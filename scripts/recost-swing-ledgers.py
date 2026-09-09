#!/usr/bin/env python3
"""Re-cost historical multi-day (SWING / POSITIONAL / INVESTMENT) paper trades at the
Zerodha delivery schedule. M0 WP-1, spec docs/superpowers/specs/2026-09-10-m0-truth-first-design.md.

For every closed trade in a multi-day pool of docs/paper-trades/<engine>/YYYY-MM-DD.json
this ADDS two keys -- `cost_delivery` and `pnl_net_delivery` -- alongside the existing
fields. Nothing existing is modified; trades already carrying the keys are skipped; files
are written atomically. Intraday trades are untouched.

Usage:
    python3 scripts/recost-swing-ledgers.py            # write + print summary
    python3 scripts/recost-swing-ledgers.py --dry-run  # print summary only

"Old cost" in the summary is what the fleet accounting charged the trade before this
correction: the trade's own `cost` field where the engine wrote one next to `pnl_net`
(v5-family engines: 12 bps of average notional), else the same 12-bps formula applied
now (swing-engine.py ledgers such as v5_swing carry NO fee field -- their `cost` key is
the entry notional, not a fee -- and their `pnl` is gross).
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from prototype.utils.signal_guards import atomic_write_json  # noqa: E402

TRADES_DIR = PROJECT_ROOT / "docs" / "paper-trades"
DATE_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
MULTI_DAY_POOLS = {"SWING", "POSITIONAL", "INVESTMENT"}
INTRADAY_BPS = 12.0


def load_cost_for_trade():
    """Import cost_for_trade from the engine script (it has a __main__ guard).

    ENGINE_NAME is pinned to 'v5' (an existing ledger dir) so the module's
    import-time mkdir(exist_ok=True) creates nothing new on disk.
    """
    os.environ.setdefault("ENGINE_NAME", "v5")
    path = PROJECT_ROOT / "scripts" / "v5-paper-trade.py"
    spec = importlib.util.spec_from_file_location("v5_paper_trade", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.cost_for_trade


def old_cost(trade):
    if "pnl_net" in trade and isinstance(trade.get("cost"), (int, float)):
        return float(trade["cost"])
    return trade["qty"] * (trade["entry_price"] + trade["exit_price"]) / 2 * INTRADAY_BPS / 10000


def ledger_files():
    for engine_dir in sorted(p for p in TRADES_DIR.iterdir() if p.is_dir()):
        for f in sorted(engine_dir.iterdir()):
            if f.is_file() and DATE_FILE.match(f.name):
                yield engine_dir.name, f


def recost(dry_run: bool):
    cost_for_trade = load_cost_for_trade()
    per_engine = defaultdict(lambda: {"n": 0, "old_cost": 0.0, "new_cost": 0.0,
                                      "gross": 0.0, "added": 0, "skipped": 0})
    files_written = 0
    for engine, f in ledger_files():
        try:
            data = json.loads(f.read_text())
        except Exception as e:  # unreadable/non-JSON day file: report, never touch
            print(f"  [skip] {f}: {e}")
            continue
        pools = data.get("pools") if isinstance(data, dict) else None
        if not isinstance(pools, dict):
            continue
        changed = False
        for pool_name, pool in pools.items():
            if pool_name not in MULTI_DAY_POOLS or not isinstance(pool, dict):
                continue
            for t in pool.get("closed", []):
                if not all(k in t for k in ("qty", "entry_price", "exit_price", "pnl")):
                    continue
                stats = per_engine[engine]
                if "cost_delivery" in t and "pnl_net_delivery" in t:
                    new = float(t["cost_delivery"]); stats["skipped"] += 1
                else:
                    new = cost_for_trade(t["qty"], t["entry_price"], t["exit_price"], pool=pool_name)
                    t["cost_delivery"] = new
                    t["pnl_net_delivery"] = round(float(t["pnl"]) - new, 2)
                    stats["added"] += 1; changed = True
                stats["n"] += 1
                stats["old_cost"] += old_cost(t)
                stats["new_cost"] += new
                stats["gross"] += float(t["pnl"])
        if changed and not dry_run:
            atomic_write_json(f, data)
            files_written += 1
    return per_engine, files_written


def print_summary(per_engine, files_written, dry_run):
    hdr = f"{'engine':<12}{'n':>6}{'old cost':>14}{'new cost':>14}{'old net':>14}{'new net':>14}{'added':>7}{'skip':>6}"
    print(("DRY RUN -- " if dry_run else "") + "multi-day pools re-costed at Zerodha delivery schedule")
    print(hdr); print("-" * len(hdr))
    tot = defaultdict(float)
    for engine, s in sorted(per_engine.items()):
        old_net, new_net = s["gross"] - s["old_cost"], s["gross"] - s["new_cost"]
        print(f"{engine:<12}{s['n']:>6}{s['old_cost']:>14,.2f}{s['new_cost']:>14,.2f}"
              f"{old_net:>14,.2f}{new_net:>14,.2f}{s['added']:>7}{s['skipped']:>6}")
        for k in ("n", "old_cost", "new_cost", "gross", "added", "skipped"):
            tot[k] += s[k]
    print("-" * len(hdr))
    print(f"{'FLEET':<12}{int(tot['n']):>6}{tot['old_cost']:>14,.2f}{tot['new_cost']:>14,.2f}"
          f"{tot['gross'] - tot['old_cost']:>14,.2f}{tot['gross'] - tot['new_cost']:>14,.2f}"
          f"{int(tot['added']):>7}{int(tot['skipped']):>6}")
    print(f"gross P&L {tot['gross']:,.2f} | files {'would be ' if dry_run else ''}written: {files_written}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the summary, write nothing")
    args = ap.parse_args()
    per_engine, files_written = recost(args.dry_run)
    print_summary(per_engine, files_written, args.dry_run)


if __name__ == "__main__":
    main()
