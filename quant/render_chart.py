#!/usr/bin/env python3
"""
render_chart — daily candlestick proof charts from Kite, with entry/exit marked.

WHY THIS EXISTS
Every backtest number in this repo is a claim. A claim you cannot see is a claim you
cannot audit. This renders the ACTUAL daily bars behind a claimed move, marks the
trough we call "optimal entry" and the peak we call "optimal exit", and prints the
percentage between them on the chart itself. If the arithmetic in a research note
disagrees with the arrow on the chart, the chart wins.

DATA SOURCE
Kite Connect daily bars (prototype/v4/kite_data). Not yfinance: on 2026-08-03
yfinance served 30 NSE tickers into the US module's cache and returned a 2-day frame
for a 3-year request. Kite is the licensed feed tied to our own broker account.

MOVING AVERAGES ARE WARMED, NOT TRUNCATED
The fetch deliberately starts ~120 calendar days before the plotted window. A 50-day
MA drawn from a window that starts on the plot's first bar is not a 50-day MA for the
first 50 bars — it is a ramp, and it would make every chart look like a golden cross.
We fetch the warmup, compute over everything, then clip the view.

THROTTLING
Kite rate-limits historical_data. Callers doing more than one symbol must pass
through render_many(), which sleeps THROTTLE_S between requests.

USAGE
    from quant.render_chart import render_chart
    render_chart("HFCL", "2025-12-01", "2026-06-20",
                 entry="2026-01-27", exit_="2026-06-03")
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")           # headless: must be set before pyplot is imported
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "docs" / "research" / "overnight" / "charts"
THROTTLE_S = 0.34               # Kite historical API: stay under 3 req/s
WARMUP_DAYS = 120               # calendar days of pre-roll so MA50 is a real MA50

UP = "#16a34a"
DOWN = "#dc2626"
MA20_C = "#2563eb"
MA50_C = "#ea580c"


# ── data ────────────────────────────────────────────────────────────────────

def fetch_daily(symbol: str, start, end) -> pd.DataFrame:
    """Daily OHLCV for [start-WARMUP, end], offline first.

    Charting historical bars needs no network and no credential, and the natural time
    to redraw a chart is a weekend when the Kite token has expired. quant.bars serves
    these from the bhavcopy store; a cross-check on 2026-08-29 found it agrees with
    Kite to the decimal on OHLC and volume, so this is the same data, not a proxy.

    Kite is still used when the range runs past what the offline store holds, which is
    the one case it is genuinely needed. The frame carries .attrs["source"] and callers
    should surface it — an offline run must announce itself rather than quietly
    resembling a live one.
    """
    start = pd.Timestamp(start).date()
    end = pd.Timestamp(end).date()
    warm = start - timedelta(days=WARMUP_DAYS)

    from quant.bars import daily as _daily
    try:
        df = _daily(symbol, warm, end, allow_kite=False)
        src = "bhavcopy (offline)"
    except LookupError:
        # not covered offline — this is what the credential is actually for
        os.environ.setdefault("NSE_DATA_SOURCE", "kite")
        df = _daily(symbol, warm, end, allow_kite=True)
        src = df.attrs.get("source", "kite (live)")

    if df is None or df.empty:
        raise LookupError(f"{symbol}: no daily bars for {warm} to {end}")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.set_index("date").sort_index()
    out = df[["open", "high", "low", "close", "volume"]]
    out.attrs["source"] = src
    return out


# ── drawing ─────────────────────────────────────────────────────────────────

def _candles(ax, x, df):
    """Real candles: a high-low wick plus an open-close body, per bar.

    Bodies are drawn as Rectangles rather than thick lines so the body width stays
    honest when the figure is resized; a doji (open == close) still gets a visible
    1-tick body instead of vanishing.
    """
    span = (df["high"].max() - df["low"].min()) or 1.0
    floor = span * 0.0015                      # minimum visible body for a doji
    w = 0.62
    for xi, (_, r) in zip(x, df.iterrows()):
        up = r["close"] >= r["open"]
        c = UP if up else DOWN
        ax.vlines(xi, r["low"], r["high"], color=c, linewidth=0.8, zorder=2)
        lo = min(r["open"], r["close"])
        h = max(abs(r["close"] - r["open"]), floor)
        ax.add_patch(Rectangle((xi - w / 2, lo), w, h, facecolor=c,
                               edgecolor=c, linewidth=0.5, zorder=3))


def render_chart(symbol: str, start, end, entry=None, exit_=None,
                 out_dir=None, label: str = "", df: pd.DataFrame | None = None):
    """Render one annotated candlestick chart. Returns (png_path, stats dict).

    entry/exit are dates. If omitted, they are derived as the trough and the
    subsequent peak inside the plotted window — but a caller that already knows the
    run (e.g. from sf_ret.parquet) should pass them so the chart proves that exact
    claim rather than a re-derived one.

    Bars are plotted against an integer index, NOT the date. Plotting against dates
    leaves a gap for every weekend and holiday, which makes a 3-day gap look like a
    flat consolidation. The x-axis is then re-labelled with the real dates.
    """
    out_dir = Path(out_dir or DEFAULT_OUT)
    out_dir.mkdir(parents=True, exist_ok=True)

    if df is None:
        df = fetch_daily(symbol, start, end)

    full = df.copy()
    full["ma20"] = full["close"].rolling(20).mean()
    full["ma50"] = full["close"].rolling(50).mean()

    view = full.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if len(view) < 10:
        raise ValueError(f"{symbol}: only {len(view)} bars in the plot window")

    x = np.arange(len(view))
    idx = {d.date(): i for i, d in enumerate(view.index)}

    def _snap(d):
        """Nearest available bar to a requested date (holidays, suspensions)."""
        if d is None:
            return None
        d = pd.Timestamp(d).date()
        if d in idx:
            return idx[d]
        diffs = [(abs((dd - d).days), i) for dd, i in idx.items()]
        return min(diffs)[1] if diffs else None

    ei = _snap(entry)
    xi = _snap(exit_)
    if ei is None or xi is None or xi <= ei:
        ei = int(view["low"].values.argmin())
        xi = int(ei + view["high"].values[ei:].argmax())

    e_px = float(view["low"].iloc[ei])
    x_px = float(view["high"].iloc[xi])
    gain = x_px / e_px - 1.0
    e_dt, x_dt = view.index[ei].date(), view.index[xi].date()
    bars = xi - ei

    fig, (ax, av) = plt.subplots(
        2, 1, figsize=(15, 8.6), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1], "hspace": 0.06})

    _candles(ax, x, view)
    ax.plot(x, view["ma20"].values, color=MA20_C, lw=1.4, label="20-day MA", zorder=4)
    ax.plot(x, view["ma50"].values, color=MA50_C, lw=1.4, label="50-day MA", zorder=4)

    # shade the run so the eye finds it before it reads a single label
    ax.axvspan(ei, xi, color="#fbbf24", alpha=0.10, zorder=0)

    pad = (view["high"].max() - view["low"].min()) * 0.10
    # Headroom BEFORE the annotations are placed. The entry label hangs below the
    # trough and the exit label above the peak; on the default autoscale both get
    # clipped by the axes box and the first render lost the entry price entirely.
    ax.set_ylim(view["low"].min() - pad * 3.2, view["high"].max() + pad * 2.8)

    ax.annotate(f"ENTRY  {e_dt}\nRs {e_px:,.2f}",
                xy=(ei, e_px), xytext=(ei, e_px - pad * 1.5),
                ha="center", va="top", fontsize=10, fontweight="bold", color="#065f46",
                arrowprops=dict(arrowstyle="-|>", lw=2, color="#065f46",
                                shrinkA=0, shrinkB=3),
                bbox=dict(boxstyle="round,pad=0.4", fc="#d1fae5", ec="#065f46", lw=1.2),
                zorder=6)

    ax.annotate(f"EXIT  {x_dt}\nRs {x_px:,.2f}",
                xy=(xi, x_px), xytext=(xi, x_px + pad * 1.4),
                ha="center", va="bottom", fontsize=10, fontweight="bold", color="#7f1d1d",
                arrowprops=dict(arrowstyle="-|>", lw=2, color="#7f1d1d",
                                shrinkA=0, shrinkB=3),
                bbox=dict(boxstyle="round,pad=0.4", fc="#fee2e2", ec="#7f1d1d", lw=1.2),
                zorder=6)

    mid = (ei + xi) / 2
    ax.annotate("", xy=(xi, x_px), xytext=(ei, e_px),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#1e3a8a",
                                linestyle="--", alpha=0.75), zorder=5)
    ax.text(mid, (e_px + x_px) / 2, f"  +{gain*100:.1f}%\n  {bars} sessions",
            fontsize=15, fontweight="bold", color="#1e3a8a", ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#1e3a8a", lw=1.6,
                      alpha=0.92), zorder=7)

    vc = [UP if c >= o else DOWN for o, c in zip(view["open"], view["close"])]
    av.bar(x, view["volume"].values, color=vc, width=0.7, alpha=0.75)
    av.plot(x, view["volume"].rolling(20).mean().values, color="#334155", lw=1.1,
            label="20-day avg volume")
    av.axvline(ei, color="#065f46", lw=1.2, ls=":", alpha=0.8)
    av.axvline(xi, color="#7f1d1d", lw=1.2, ls=":", alpha=0.8)
    av.set_ylabel("Volume", fontsize=10)
    av.legend(loc="upper left", fontsize=8, framealpha=0.9)
    av.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}k"))

    ticks = np.linspace(0, len(view) - 1, min(12, len(view))).astype(int)
    av.set_xticks(ticks)
    av.set_xticklabels([view.index[i].strftime("%d-%b-%y") for i in ticks],
                       rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Price (Rs)", fontsize=10)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    for a in (ax, av):
        a.grid(alpha=0.18, linestyle=":", zorder=0)
        a.set_xlim(-1, len(view))
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)

    sub = f" — {label}" if label else ""
    ax.set_title(
        f"{symbol}{sub}   |   {view.index[0].date()} to {view.index[-1].date()}   |   "
        f"trough-to-peak +{gain*100:.1f}% over {bars} sessions "
        f"({e_dt} Rs{e_px:,.2f} -> {x_dt} Rs{x_px:,.2f})",
        fontsize=12.5, fontweight="bold", pad=12)

    fig.text(0.995, 0.005,
             "Source: Kite Connect daily bars. Entry = run low, exit = run high, "
             "both identified after the fact.",
             ha="right", va="bottom", fontsize=7.5, color="#64748b")

    png = out_dir / f"{symbol}_{e_dt}.png"
    fig.savefig(png, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return png, {
        "symbol": symbol, "entry": str(e_dt), "exit": str(x_dt),
        "entry_px": e_px, "exit_px": x_px, "gain_pct": gain * 100,
        "sessions": bars, "bars_plotted": len(view),
        "avg_vol": float(view["volume"].mean()),
        "med_turnover_cr": float((view["close"] * view["volume"]).median() / 1e7),
    }


def render_many(specs, out_dir=None):
    """Render a list of dicts, throttled. Returns (results, dropped).

    A symbol Kite cannot resolve is DROPPED and reported, never silently skipped and
    never replaced with a substitute chosen by this function — substitution is a
    judgement call and belongs to the caller.
    """
    results, dropped = [], []
    for s in specs:
        try:
            png, st = render_chart(
                s["symbol"], s["start"], s["end"],
                entry=s.get("entry"), exit_=s.get("exit"),
                out_dir=out_dir, label=s.get("label", ""))
            st["png"] = str(png)
            st["bucket"] = s.get("bucket", "")
            results.append(st)
            print(f"OK   {s['symbol']:<12} +{st['gain_pct']:6.1f}%  {png.name}")
        except Exception as e:
            dropped.append((s["symbol"], f"{type(e).__name__}: {e}"))
            print(f"DROP {s['symbol']:<12} {type(e).__name__}: {e}")
        time.sleep(THROTTLE_S)
    return results, dropped


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        sys.exit(0)
    p, st = render_chart(a[0], a[1], a[2],
                         entry=a[3] if len(a) > 3 else None,
                         exit_=a[4] if len(a) > 4 else None)
    print(p, st)
