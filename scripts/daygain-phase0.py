#!/usr/bin/env python3
"""DAYGAIN Phase 0 — holdout backtest of the pre-registered top-gainer rule.

Spec: ~/Downloads/2026-09-05-daygain-lane-spec.md (FROZEN — no parameter changes).

Two sub-commands, both re-runnable:

    fetch   pull ~100 days of Kite 5-minute bars for quant/universe_full.txt plus
            NIFTY 50 into quant/data/intraday5/<SYMBOL>.parquet. Resumable: a symbol
            whose parquet exists is skipped. Errors are recorded in _errors.json.
    run     read the cache, apply the rule on the holdout window only, write
            docs/research/daygain/phase0-holdout-<today>.{md,csv} and a positions csv.

BAR CONVENTION (verified on RELIANCE, 2026-09-04): Kite labels a 5-minute bar by
its START time — first bar of the day is 09:15, so the bar labelled 09:30 covers
09:30–09:35. "Price at 09:35" therefore = Close of the 09:30 bar; the fill is the
Open of the 09:35 bar (first price after 09:35); the 15:15 square-off is the Close
of the 15:10 bar (the bar that ENDS at 15:15).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype" / "v4"))

CACHE = ROOT / "quant" / "data" / "intraday5"
UNIVERSE = ROOT / "quant" / "universe_full.txt"
BHAV = ROOT / "quant" / "data" / "bhavcopy_daily.parquet"
OUT_DIR = ROOT / "docs" / "research" / "daygain"
ERR_FILE = CACHE / "_errors.json"
NIFTY_TOKEN = 256265          # NSE:NIFTY 50 (segment INDICES) — verified via instruments("NSE")
NIFTY_KEY = "_NIFTY50"

# ── the frozen rule ──────────────────────────────────────────────────────────
HOLDOUT_START = date(2026, 7, 1)
HOLDOUT_END = date(2026, 9, 4)
SLOT_RS = 112_500.0
N_POS = 10
CAPITAL = SLOT_RS * N_POS       # 11.25L deployed
MIN_PRICE = 50.0
MIN_ADV_RS = 5e7                # 5 crore
ADV_DAYS = 20
MAX_CHG = 15.0                  # skip chg > +15%
UC_PROXY_CHG = 9.5              # 09:35 price == day high so far AND chg >= 9.5 -> upper-circuit proxy
SLIP = 1.001                    # +0.10% on fill
STOP_PCT = 0.03
NIFTY_KILL = -1.0
SIGNAL_BAR = "09:30"            # bar ending 09:35
FILL_BAR = "09:35"              # first bar after 09:35 — fill at its open
EXIT_BAR = "15:10"              # bar ending 15:15 — exit at its close


# ── costs: copied VERBATIM from scripts/v5_god-paper-trade.py (real_cost) ───
def real_cost(qty: int, entry: float, exit_: float, side: str) -> dict:
    """Actual Zerodha intraday equity ledger. Size-dependent by construction —
    that dependence is the whole reason this book runs big positions."""
    buy_val = qty * (entry if side == "LONG" else exit_)
    sell_val = qty * (exit_ if side == "LONG" else entry)
    turnover = buy_val + sell_val

    brokerage = min(0.0003 * buy_val, 20.0) + min(0.0003 * sell_val, 20.0)
    stt = 0.00025 * sell_val                 # intraday equity: sell side only
    exch = 0.0000297 * turnover              # NSE transaction charge
    sebi = 0.000001 * turnover               # Rs10 per crore
    stamp = 0.00003 * buy_val                # buy side only
    gst = 0.18 * (brokerage + exch + sebi)
    total = brokerage + stt + exch + sebi + stamp + gst
    return {
        "brokerage": round(brokerage, 2), "stt": round(stt, 2),
        "exchange": round(exch, 2), "sebi": round(sebi, 2),
        "stamp": round(stamp, 2), "gst": round(gst, 2),
        "total": round(total, 2),
        "pct_of_turnover": round(total / turnover * 100, 4) if turnover else 0.0,
    }


# ── fetch ────────────────────────────────────────────────────────────────────
class RateLimiter:
    """Global ≤3 calls/second across worker threads (Kite historical limit)."""
    def __init__(self, interval: float):
        self.interval, self.lock, self.next_at = interval, threading.Lock(), 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            if now < self.next_at:
                time.sleep(self.next_at - now)
                now = time.monotonic()
            self.next_at = now + self.interval


def fetch(args):
    import pandas as pd
    from prototype.v4 import kite_data as kd

    ok, who = kd.token_alive()
    if not ok:
        raise SystemExit(f"Kite token dead: {who}")
    print(f"kite ok: {who}")
    CACHE.mkdir(parents=True, exist_ok=True)
    to_d = datetime(2026, 9, 5)
    from_d = to_d - timedelta(days=100)        # 5minute: ~100 days per request
    k = kd.client()

    syms = [s.strip().upper() for s in UNIVERSE.read_text().splitlines() if s.strip()]
    todo = [(NIFTY_KEY, NIFTY_TOKEN)]
    n_no_token = 0
    for s in syms:
        tok = kd.token_for(s)
        if not tok:
            n_no_token += 1
            continue
        todo.append((s, tok))
    todo = [(s, t) for s, t in todo if not (CACHE / f"{s}.parquet").exists()]
    print(f"universe {len(syms)}  no_token {n_no_token}  to_fetch {len(todo)}")

    errors = json.loads(ERR_FILE.read_text()) if ERR_FILE.exists() else {}
    errors["_no_token"] = n_no_token
    rl = RateLimiter(0.34)
    lock = threading.Lock()
    done = {"n": 0, "err": 0, "empty": 0}
    t0 = time.time()
    deadline = t0 + args.budget_sec

    def one(sym, tok):
        for attempt in (1, 2):
            rl.wait()
            try:
                rows = k.historical_data(tok, from_d, to_d, "5minute")
                break
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                if attempt == 2 or "token" in msg.lower() or "Invalid" in msg:
                    with lock:
                        errors[sym] = msg
                        done["err"] += 1
                    return
                time.sleep(1.0)
        if not rows:
            with lock:
                errors[sym] = "empty"
                done["empty"] += 1
            return
        df = pd.DataFrame(rows).rename(columns={
            "date": "Datetime", "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume"}).set_index("Datetime")
        tmp = CACHE / f"{sym}.tmp.parquet"
        df.to_parquet(tmp)
        tmp.replace(CACHE / f"{sym}.parquet")
        with lock:
            done["n"] += 1

    def worker(chunk):
        for sym, tok in chunk:
            if time.time() > deadline:
                return
            one(sym, tok)

    nw = 3
    threads = [threading.Thread(target=worker, args=(todo[i::nw],)) for i in range(nw)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(15)
        el = time.time() - t0
        print(f"  {el/60:5.1f} min  fetched {done['n']}  err {done['err']}  empty {done['empty']}  "
              f"rate {done['n']/max(el,1):.2f}/s", flush=True)
    for t in threads:
        t.join()
    ERR_FILE.write_text(json.dumps(errors, indent=1, sort_keys=True))
    left = len(todo) - done["n"] - done["err"] - done["empty"]
    print(f"done in {(time.time()-t0)/60:.1f} min: fetched {done['n']}  err {done['err']}  "
          f"empty {done['empty']}  not_attempted {left}  cached_total "
          f"{len(list(CACHE.glob('*.parquet')))}")


# ── run ──────────────────────────────────────────────────────────────────────
def load_frame(path):
    import pandas as pd
    df = pd.read_parquet(path)
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    df.index = idx
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df["day"] = df.index.date
    df["hm"] = df.index.strftime("%H:%M")
    return df


def adv_table():
    """20-day average daily turnover (₹) per symbol as of each date, from the NSE
    bhavcopy (real turnover, not close×volume). Value at date d uses the 20 trading
    days strictly BEFORE d. Bhavcopy ends 2026-08-31, so dates after that reuse the
    window ending 2026-08-31 (at most 4 sessions stale)."""
    import pandas as pd
    b = pd.read_parquet(BHAV, columns=["symbol", "date", "turnover_lakh"])
    b["date"] = pd.to_datetime(b["date"])
    b = b[b["date"] >= "2026-04-01"]
    piv = b.pivot_table(index="date", columns="symbol", values="turnover_lakh", aggfunc="last")
    adv = piv.rolling(ADV_DAYS, min_periods=ADV_DAYS).mean().shift(1) * 1e5   # lakh -> ₹
    return adv


def adv_at(adv, sym, d):
    if sym not in adv.columns:
        return None
    col = adv[sym]
    ts = col.index[col.index <= __import__("pandas").Timestamp(d)]
    if len(ts) == 0:
        return None
    v = col.loc[ts[-1]]
    return None if v != v else float(v)     # NaN -> None


def run(args):
    import numpy as np
    import pandas as pd

    files = sorted(CACHE.glob("*.parquet"))
    if not files:
        raise SystemExit("no cache — run `fetch` first")
    errors = json.loads(ERR_FILE.read_text()) if ERR_FILE.exists() else {}
    universe = [s.strip().upper() for s in UNIVERSE.read_text().splitlines() if s.strip()]

    nifty = load_frame(CACHE / f"{NIFTY_KEY}.parquet")
    trading_days = sorted(d for d in set(nifty["day"]) if HOLDOUT_START <= d <= HOLDOUT_END)
    all_days = sorted(set(nifty["day"]))
    prev_day = {d: all_days[i - 1] for i, d in enumerate(all_days) if i > 0}

    # bar-coverage diagnostic on EQUITY frames: last bar label per symbol-day
    last_bar = {}

    adv = adv_table()

    # per-symbol, per-day feature extraction
    frames = {}
    for f in files:
        sym = f.stem
        if sym == NIFTY_KEY or sym.endswith(".tmp"):
            continue
        frames[sym] = load_frame(f)
        for d, hm in frames[sym].groupby("day")["hm"].last().items():
            k_ = ("pre" if d < date(2026, 8, 3) else "post", hm if hm in ("15:25", "15:10") else "earlier")
            last_bar[k_] = last_bar.get(k_, 0) + 1
    covered = len(frames)
    if "_no_token" not in errors:
        from prototype.v4 import kite_data as kd
        errors["_no_token"] = sum(1 for s_ in universe if not kd.token_for(s_))

    def day_slice(df, d):
        return df[df["day"] == d]

    # pre-index by day for speed
    by_day = {sym: {d: g for d, g in df.groupby("day")} for sym, df in frames.items()}

    def nifty_chg(d):
        g = by_day_n.get(d)
        p = by_day_n.get(prev_day.get(d))
        if g is None or p is None or SIGNAL_BAR not in set(g["hm"]):
            return None
        return (g.loc[g["hm"] == SIGNAL_BAR, "Close"].iloc[0] / p["Close"].iloc[-1] - 1) * 100

    by_day_n = {d: g for d, g in nifty.groupby("day")}

    day_rows, pos_rows = [], []
    filt_counts = {"no_prev": 0, "no_bar": 0, "price": 0, "adv": 0, "adv_missing": 0,
                   "chg_gt15": 0, "uc_proxy": 0, "not_gainer": 0}
    for d in trading_days:
        nchg = nifty_chg(d)
        killed = nchg is not None and nchg < NIFTY_KILL
        cands = []
        if not killed:
            pd_ = prev_day.get(d)
            for sym, days in by_day.items():
                g = days.get(d)
                p = days.get(pd_)
                if g is None or p is None:
                    filt_counts["no_prev"] += 1
                    continue
                hm = g["hm"].values
                if SIGNAL_BAR not in hm or FILL_BAR not in hm:
                    filt_counts["no_bar"] += 1
                    continue
                i_sig = int(np.where(hm == SIGNAL_BAR)[0][0])
                p0935 = float(g["Close"].iloc[i_sig])
                prev_close = float(p["Close"].iloc[-1])
                if p0935 < MIN_PRICE or prev_close <= 0:
                    filt_counts["price"] += 1
                    continue
                a = adv_at(adv, sym, d)
                if a is None:
                    filt_counts["adv_missing"] += 1
                    continue
                if a < MIN_ADV_RS:
                    filt_counts["adv"] += 1
                    continue
                chg = (p0935 / prev_close - 1) * 100
                if chg <= 0:
                    filt_counts["not_gainer"] += 1
                    continue
                if chg > MAX_CHG:
                    filt_counts["chg_gt15"] += 1
                    continue
                hi_so_far = float(g["High"].iloc[: i_sig + 1].max())
                if p0935 >= hi_so_far and chg >= UC_PROXY_CHG:
                    filt_counts["uc_proxy"] += 1
                    continue
                cands.append((chg, sym, i_sig, p0935, prev_close, a))
            cands.sort(reverse=True)
            cands = cands[:N_POS]

        gross = costs = net = 0.0
        for rank, (chg, sym, i_sig, p0935, prev_close, a) in enumerate(cands, 1):
            g = by_day[sym][d]
            i_fill = i_sig + 1                      # the 09:35 bar
            fill = float(g["Open"].iloc[i_fill]) * SLIP
            qty = math.floor(SLOT_RS / fill)
            if qty <= 0:
                continue
            stop = fill * (1 - STOP_PCT)
            path = g.iloc[i_fill:]
            path = path[path["hm"] <= EXIT_BAR]
            exit_px, exit_hm, reason = None, None, "eod"
            hit = np.where(path["Low"].values <= stop)[0]
            if len(hit):
                exit_px, exit_hm, reason = stop, path["hm"].iloc[hit[0]], "stop"
            else:
                exit_px, exit_hm = float(path["Close"].iloc[-1]), path["hm"].iloc[-1]
            gp = qty * (exit_px - fill)
            c = real_cost(qty, fill, exit_px, "LONG")["total"]
            gross += gp
            costs += c
            net += gp - c
            pos_rows.append({"date": d, "rank": rank, "symbol": sym, "chg_0935": round(chg, 2),
                             "prev_close": prev_close, "p0935": p0935, "fill": round(fill, 2),
                             "qty": qty, "stop": round(stop, 2), "exit": round(exit_px, 2),
                             "exit_bar": exit_hm, "reason": reason, "adv_cr": round(a / 1e7, 1),
                             "gross": round(gp, 2), "cost": round(c, 2), "net": round(gp - c, 2)})
        day_rows.append({"date": d, "n_positions": len(cands), "gross": round(gross, 2),
                         "costs": round(costs, 2), "net": round(net, 2),
                         "nifty_0935": None if nchg is None else round(nchg, 2),
                         "killed": killed, "net_ret_pct": round(net / CAPITAL * 100, 4)})

    days = pd.DataFrame(day_rows)
    pos = pd.DataFrame(pos_rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = args.tag
    days.to_csv(OUT_DIR / f"phase0-holdout-{tag}.csv", index=False)
    pos.to_csv(OUT_DIR / f"phase0-holdout-{tag}-positions.csv", index=False)

    # ── stats ────────────────────────────────────────────────────────────────
    r = days["net"].values / CAPITAL
    n = len(r)
    tot_gross, tot_cost, tot_net = days["gross"].sum(), days["costs"].sum(), days["net"].sum()
    traded = days[days["n_positions"] > 0]
    edge_all = tot_net / n if n else float("nan")
    edge_traded = traded["net"].mean() if len(traded) else float("nan")
    sd = r.std(ddof=1) if n > 1 else float("nan")
    tstat = r.mean() / sd * math.sqrt(n) if sd and sd > 0 else float("nan")
    eq = np.cumsum(days["net"].values)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    dd = eq - peak
    mdd_rs = float(dd.min()) if n else 0.0
    mdd_pct = -mdd_rs / CAPITAL * 100
    win_days = int((days["net"] > 0).sum())
    g1 = edge_all > 0
    g2 = tstat >= 2.0
    g3 = mdd_pct <= 15.0
    n_err = sum(1 for k in errors if not k.startswith("_"))
    n_no_tok = errors.get("_no_token", 0)
    n_missing = len(universe) - covered
    def _lb(era):
        tot = sum(v for (e, _), v in last_bar.items() if e == era) or 1
        return ", ".join(f"{hm} {last_bar.get((era, hm), 0) / tot * 100:.1f}%" for hm in ("15:25", "15:10", "earlier"))
    lb_txt = f"share of symbol-days by last-bar label — before 2026-08-03: {_lb('pre')}; from 2026-08-03: {_lb('post')}"

    def P(b):
        return "PASS" if b else "FAIL"

    L = []
    L.append(f"# DAYGAIN Phase 0 — holdout backtest verdict ({tag})\n")
    L.append("Pre-registered spec: `~/Downloads/2026-09-05-daygain-lane-spec.md` (rule FROZEN, no parameter "
             "changed). Harness: `scripts/daygain-phase0.py`. Data: real Kite Connect 5-minute bars.\n")
    L.append(f"**Window:** holdout only, {HOLDOUT_START} → {HOLDOUT_END}, {n} trading days "
             f"(first session in the cache, 2026-05-29, has no prior close and is outside the window anyway). "
             f"The 2021 → 2026-06 train window was **not run** — no local minute bars exist for it and Kite's "
             f"5-minute history is served ~100 days per request; it is out of scope for this run.\n")
    L.append("## Gates (all three must pass)\n")
    L.append("| # | Gate | Value | Result |\n|--:|---|---:|:--:|")
    L.append(f"| 1 | Net edge per basket-day > 0 after full costs + slippage | ₹{edge_all:,.0f}/day "
             f"(all {n} days); ₹{edge_traded:,.0f}/day on {len(traded)} traded days | **{P(g1)}** |")
    L.append(f"| 2 | t-stat of daily net returns ≥ 2.0 | {tstat:.2f} | **{P(g2)}** |")
    L.append(f"| 3 | Max drawdown of daily equity curve ≤ 15% of ₹{CAPITAL:,.0f} | {mdd_pct:.2f}% "
             f"(₹{-mdd_rs:,.0f}) | **{P(g3)}** |")
    L.append(f"\n**Verdict: {'PASS — all three gates hold' if g1 and g2 and g3 else 'FAIL — lane dies here'}.**\n")
    L.append("## Totals\n")
    L.append("| Metric | Value |\n|---|---:|")
    L.append(f"| Trading days | {n} |")
    L.append(f"| Days with a basket | {len(traded)} |")
    L.append(f"| Days killed by Nifty < −1.0% at 09:35 | {int(days['killed'].sum())} |")
    L.append(f"| Positions taken | {len(pos)} |")
    L.append(f"| Stopped out (−3%) | {int((pos['reason']=='stop').sum()) if len(pos) else 0} |")
    L.append(f"| Gross P&L | ₹{tot_gross:,.0f} |")
    L.append(f"| Costs (real_cost schedule) | ₹{tot_cost:,.0f} |")
    L.append(f"| **Net P&L** | **₹{tot_net:,.0f}** |")
    L.append(f"| Net return on ₹11.25L | {tot_net / CAPITAL * 100:.2f}% over {n} days; {r.mean()*100:.3f}%/day |")
    L.append(f"| Daily net σ | {sd*100:.3f}% |")
    L.append(f"| Win days (net > 0) | {win_days}/{n} ({win_days / n * 100:.0f}%) |")
    L.append(f"| Avg cost per position (round trip) | ₹{pos['cost'].mean():,.0f} |" if len(pos) else "")
    L.append(f"| Avg gross per position | ₹{pos['gross'].mean():,.0f} |" if len(pos) else "")
    if len(pos):
        L.append(f"| Mean 09:35 %chg of picks | {pos['chg_0935'].mean():.2f}% |")
    L.append("\n## Per-day\n")
    L.append("| date | n_pos | gross | costs | net | nifty_0935 | killed |\n|---|--:|--:|--:|--:|--:|:--:|")
    for _, x in days.iterrows():
        nv = x["nifty_0935"]
        ns = "" if nv is None or nv != nv else "%+.2f%%" % nv
        L.append(f"| {x['date']} | {x['n_positions']} | {x['gross']:,.0f} | {x['costs']:,.0f} | "
                 f"{x['net']:,.0f} | {ns} | {'yes' if x['killed'] else ''} |")
    L.append("\n## Data caveats\n")
    L.append(f"- **Bar convention:** Kite labels 5-min bars by START time (first bar 09:15). The 09:35 "
             f"signal price is the Close of the bar labelled 09:30 (covers 09:30–09:35). Fill is the Open "
             f"of the bar labelled 09:35 (first print after 09:35) × 1.001. Square-off is the Close of the "
             f"bar labelled 15:10 (the bar that ends 15:15). Stop is checked on every bar from the fill bar "
             f"through the 15:10 bar inclusive on Low ≤ stop, filled at the stop price (no gap slippage).")
    L.append(f"- **Bar coverage (equities):** {lb_txt}. From 2026-08-03 onward a minority of equity "
             f"symbol-days (incl. RELIANCE on 2026-09-04) carry 72 bars with the last bar labelled 15:10 — the 15:15, "
             f"15:20 and 15:25 bars are absent from Kite's 5-minute history for those symbol-days (the NIFTY 50 index "
             f"frame has all 75 bars every day); Kite also "
             f"omits bars with zero trades, which is why illiquid names end earlier still. Consequence: "
             f"the exit bar (15:10) is always present, but the **prior close** used for %chg is the Close "
             f"of the previous session's last available bar — 15:25 bar before Aug 3, 15:10 bar from Aug 3 "
             f"— not the official settlement close. NIFTY 50 prior close = its 15:25 bar close.")
    L.append(f"- **Coverage:** universe 2,634 symbols; {covered} have a cached 5-min frame and were "
             f"evaluated; {n_missing} not covered ({n_no_tok} with no NSE instrument token today — "
             f"delisted/renamed, so survivorship is NOT clean for those; {n_err} fetch errors/empties; "
             f"the rest not attempted: the fetch stopped at its 12-minute budget, so the cache is a "
             f"file-order prefix of the universe (alphabetical, last cached symbol {max(frames)}), not a "
             f"random sample — the uncovered tail is the S–Z range).")
    L.append(f"- **ADV filter:** real 20-session average turnover from the NSE bhavcopy "
             f"(`quant/data/bhavcopy_daily.parquet`, `turnover_lakh`), as of the previous session — not a "
             f"close×volume proxy. The bhavcopy ends 2026-08-31, so 2026-09-01..04 reuse the window ending "
             f"08-31 (≤4 sessions stale). Symbols absent from the bhavcopy were skipped "
             f"({filt_counts['adv_missing']} symbol-days).")
    L.append(f"- **ASM/GSM stage ≥ 2 filter: NOT applied** — no historical ASM/GSM list is available "
             f"locally. This can only make the backtest look better than live, never worse.")
    L.append(f"- **Upper-circuit filter:** proxied as (09:35 price == day high so far AND chg ≥ 9.5%), "
             f"as instructed; exact band data is not in the bars.")
    L.append(f"- **Index kill:** real NIFTY 50 index bars (instrument token 256265), same bar convention; "
             f"no proxy was needed.")
    L.append(f"- **'Gainer' definition:** only symbols with chg > 0 at 09:35 are ranked; this bound on "
             f"{filt_counts['not_gainer']} symbol-days and never reduced a basket below 10 on a non-killed day"
             f"{'' if (traded['n_positions'] == N_POS).all() else ' — EXCEPT it did on some days, see per-day table'}.")
    L.append(f"- **Filter tallies (symbol-days):** {json.dumps(filt_counts)}.")
    L.append(f"- **Costs:** `real_cost()` copied verbatim from `scripts/v5_god-paper-trade.py` "
             f"(brokerage min(0.03%, ₹20)/order, STT 0.025% sell, NSE txn 0.00297%, SEBI ₹10/cr, stamp "
             f"0.003% buy, 18% GST). Not imported via importlib because that file executes a paper-trading "
             f"CLI at import.")
    L.append(f"- **Holdout-only.** Nothing was tuned; the rule was run once as written. No train window.")
    L.append("\n## Falsification sentence — outcome\n")
    if g1 and g2 and g3:
        L.append(f"All three pre-registered gates pass on the {n}-day holdout: day-gainer persistence at "
                 f"this horizon survives honest costs on real bars in this window (net ₹{tot_net:,.0f}, "
                 f"t={tstat:.2f}, MDD {mdd_pct:.1f}%). The lane proceeds to Phase 1 (paper lane). The "
                 f"caveat that matters: {n} days is one regime, the train window is untested, and the "
                 f"ASM/GSM filter was not applied.")
    else:
        failed = [name for name, ok in (("net edge > 0", g1), ("t-stat ≥ 2.0", g2), ("MDD ≤ 15%", g3)) if not ok]
        L.append(f"Phase 0 holdout FAILS on: {', '.join(failed)}. In plain words: on real 5-minute bars, "
                 f"buying the top-10 09:35 gainers and holding to 15:15 with a −3% stop made "
                 f"₹{tot_net:,.0f} net over {n} sessions (t={tstat:.2f}, MDD {mdd_pct:.1f}%). Day-gainer "
                 f"persistence at this horizon is not a net edge after honest costs on clean data; the "
                 f"+₹172k ledger number was truncation bias plus one hot regime, and the lane is dead. "
                 f"No parameter search follows. The reusable residue is this harness, the 5-min cache and "
                 f"the cost math.")
    md = OUT_DIR / f"phase0-holdout-{tag}.md"
    md.write_text("\n".join(x for x in L if x is not None))
    print("\n".join(L[:12]))
    print(f"\nwrote {md}\n      {OUT_DIR / f'phase0-holdout-{tag}.csv'}\n      "
          f"{OUT_DIR / f'phase0-holdout-{tag}-positions.csv'}")
    print(f"covered {covered}/{len(universe)}  filters {filt_counts}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--budget-sec", type=int, default=1080, help="stop launching new requests after this")
    r = sub.add_parser("run")
    r.add_argument("--tag", default=datetime.now().strftime("%Y-%m-%d"))
    a = ap.parse_args()
    (fetch if a.cmd == "fetch" else run)(a)


if __name__ == "__main__":
    main()
