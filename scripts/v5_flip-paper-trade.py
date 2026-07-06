#!/usr/bin/env python3
"""
v5_flip — fast intraday regime-flip shadow (TP-RCA, 2026-06-30).

WHY (validated today against all data since April):
  The engine sets regime ONCE at launch off slow daily indicators and never re-checks,
  so its short-share stays flat ~45% on a +0.5% green day AND a -1% red day — it does NOT
  lean into the tape, which is why it bleeds on red mornings while its shorts are green.

WHAT THIS IS:
  Same v5 code (NIFTY-200, long+short, all the safeguards), with the FAST_FLIP hook on:
  every 5 min it re-checks the live tape and, on a CONFIRMED hard-down (NIFTY < -0.6% over
  2 reads — the validated threshold; mild-down still favours longs), activates the engine's
  EXISTING BEAR slot split (8L/12S) intraday. Bidirectional: reverts to SIDEWAYS on a
  confirmed green reversal so it captures the 2nd-half up-trend (validated: post-1pm entries
  are where v5's profit is). Keeps both legs always (longs earn +49/trade even on hard-down).
  Re-arm winners on TARGET works both directions already (COALINDIA x6 = +Rs23,197 pattern).

WHAT THIS IS *NOT* (yet):
  Not the full dynamic per-stock-trend allocation / net-exposure cap — that needs the
  conviction->P&L validation, which is unblocked only now that we log score on closed trades
  (started 2026-06-30). This is the data-justified "fast activation of the existing 8/12 tilt"
  stepping stone. Compare risk-adjusted + red-day behaviour vs live v5 over >=2 red days.

Runs as a shadow alongside v5; own state/log, telegram silent. Re-comment to end.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v5_flip"
os.environ["FAST_FLIP"]            = "1"      # enable the intraday fast-flip hook
os.environ["SCAN_INTERVAL_MIN"]    = "5"      # 5-min scan (don't miss the candle/trend signal)
os.environ["RESCORE_INTERVAL_MIN"] = "15"     # re-deploy faster so the tilt takes effect sooner
os.environ["TELEGRAM_DISABLE"]     = "1"
# NO UNIVERSE_FILE -> stays NIFTY-200. long+short kept; the flip tilts the ratio, never all-in.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
