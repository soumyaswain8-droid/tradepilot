#!/usr/bin/env python3
"""
quant/dh_straddle.py — DELTA-HEDGED SHORT STRADDLE on NIFTY weekly options.

THE QUESTION
The variance risk premium is real (+1.55 vol pts, t=2.59). The iron condor built to
harvest it failed on VARIANCE, not on cost: its payoff was so wide that reaching
t=2 on its own returns needed 637 years. A delta-hedged straddle removes the
directional term, which is the dominant variance term. Does that collapse the
variance enough to make the premium detectable in a human timeframe?

EVERY PRICE IS A TRADED PRINT
Option prices are ClsPric from the NSE F&O bhavcopy for the exact expired contract.
Black-Scholes is used ONLY to invert a traded close into an IV, and that IV is used
ONLY to compute a hedge ratio. No price in the P&L path is modelled.

HEDGE FREQUENCY: DAILY CLOSE ONLY. Bhavcopy is end-of-day. Kite historical drops
expired instruments, so no intraday option path exists for these contracts. See the
doc — intraday hedging is NOT testable with obtainable data and is not simulated.

Usage: python3 quant/dh_straddle.py
"""
import math, glob, warnings, json, sys
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).resolve().parent / "data" / "fo_nifty"
R = 0.065
LOT = 75                      # NIFTY contract lot size

# ---- COSTS: current rates, verified against zerodha.com/charges 2026-08-28 ----
# Budget 2026, effective 2026-04-01: options STT 0.10% -> 0.15%, futures 0.02% -> 0.05%
STT_OPT_SELL = 0.0015         # 0.15% of premium, SELL side
STT_FUT_SELL = 0.0005         # 0.05% of turnover, SELL side
TXN_OPT      = 0.0003553      # NSE 0.03553% on premium, both sides
TXN_FUT      = 0.0000183      # NSE 0.00183% on turnover, both sides
SEBI         = 0.000001       # Rs10/crore
STAMP_OPT    = 0.00003        # 0.003% on premium, BUY side
STAMP_FUT    = 0.00002        # 0.002% on turnover, BUY side
GST          = 0.18           # on brokerage + txn + SEBI
BRK_OPT      = 20.0           # flat Rs20 per executed order
def brk_fut(turnover):        # Rs20 or 0.03%, whichever is LOWER
    return min(20.0, 0.0003 * turnover)

# bid-ask, in INDEX POINTS of half-spread (cost of crossing, one side)
HS_OPT = 0.50                 # NIFTY ATM weekly: tick 0.05, typical spread ~1.0pt
HS_FUT = 0.25                 # NIFTY near future: typical spread ~0.5pt

CAPITAL = 200_000.0           # Rs margin blocked per 1-lot hedged straddle


# ------------------------------------------------------------------ load
def load():
    o, f = [], []
    for fp in sorted(glob.glob(str(D / "nifty_*.csv"))):
        df = pd.read_csv(fp, low_memory=False)
        if "TradDt" not in df.columns:
            continue
        df["dt"] = pd.to_datetime(df.TradDt)
        df["exp"] = pd.to_datetime(df.XpryDt)
        opt = df[df.OptnTp.isin(["CE", "PE"])]
        if len(opt):
            o.append(pd.DataFrame({
                "dt": opt.dt, "exp": opt.exp, "K": opt.StrkPric.astype(float),
                "cp": opt.OptnTp, "close": opt.ClsPric.astype(float),
                "spot": opt.UndrlygPric.astype(float),
                "oi": opt.OpnIntrst.astype(float), "vol": opt.TtlTradgVol.astype(float)}))
        # UDiFF instrument codes: IDO = index option, IDF = index future
        fut = df[df.FinInstrmTp.astype(str).str.strip() == "IDF"]
        if len(fut):
            f.append(pd.DataFrame({
                "dt": fut.dt, "exp": fut.exp, "close": fut.ClsPric.astype(float),
                "spot": fut.UndrlygPric.astype(float)}))
    return pd.concat(o, ignore_index=True), pd.concat(f, ignore_index=True)


# ------------------------------------------------------------------ BS
def _N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs(S, K, T, s, cp):
    if T <= 0 or s <= 0:
        return max(0.0, S - K) if cp == "CE" else max(0.0, K - S)
    d1 = (math.log(S / K) + (R + s * s / 2) * T) / (s * math.sqrt(T))
    d2 = d1 - s * math.sqrt(T)
    return (S * _N(d1) - K * math.exp(-R * T) * _N(d2)) if cp == "CE" \
        else (K * math.exp(-R * T) * _N(-d2) - S * _N(-d1))

def iv(px, S, K, T, cp):
    if T <= 0 or px <= 0:
        return np.nan
    intr = max(0.0, S - K) if cp == "CE" else max(0.0, K - S)
    if px <= intr * 1.0001:
        return np.nan
    lo, hi = 1e-4, 5.0
    if bs(S, K, T, hi, cp) < px:
        return np.nan
    for _ in range(60):
        mid = (lo + hi) / 2
        if bs(S, K, T, mid, cp) < px:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def straddle_delta(S, K, T, s):
    """Delta of a SHORT ATM straddle, per unit of index. = 1 - 2N(d1)."""
    if T <= 0 or s <= 0:
        return 0.0 if S == K else (-1.0 if S > K else 1.0)
    d1 = (math.log(S / K) + (R + s * s / 2) * T) / (s * math.sqrt(T))
    return 1.0 - 2.0 * _N(d1)


# ------------------------------------------------------------------ costs
def opt_sell_cost(prem_pts, n_legs, n_lots=1):
    """Rs cost of SELLING n_legs of options with total premium prem_pts (index pts)."""
    turn = prem_pts * LOT * n_lots
    txn = TXN_OPT * turn
    sebi = SEBI * turn
    brk = BRK_OPT * n_legs
    return STT_OPT_SELL * turn + txn + sebi + brk + GST * (brk + txn + sebi)

def fut_trade_cost(dqty_units, F):
    """Rs cost of trading |dqty_units| index-units of futures at price F.
    dqty>0 = BUY, dqty<0 = SELL. Includes half-spread slippage."""
    if abs(dqty_units) < 1e-12:
        return 0.0
    turn = abs(dqty_units) * F
    txn = TXN_FUT * turn
    sebi = SEBI * turn
    brk = brk_fut(turn)
    stt = STT_FUT_SELL * turn if dqty_units < 0 else 0.0
    stamp = STAMP_FUT * turn if dqty_units > 0 else 0.0
    slip = abs(dqty_units) * HS_FUT
    return stt + stamp + txn + sebi + brk + GST * (brk + txn + sebi) + slip


# ------------------------------------------------------------------ backtest
def run(hedge=True, integer_lots=False, n_lots=1, hs_opt=HS_OPT, hs_fut=HS_FUT):
    global HS_OPT, HS_FUT
    HS_OPT, HS_FUT = hs_opt, hs_fut
    opt, fut = OPT, FUT

    spot = opt.dropna(subset=["spot"]).groupby("dt").spot.median()
    sessions = np.array(sorted(opt.dt.unique()))
    exps = np.array(sorted(opt.exp.unique()))
    exps = exps[(exps >= sessions[0]) & (exps <= sessions[-1])]

    recs = []
    for E in exps:
        cand = sessions[(E - sessions >= np.timedelta64(5, "D")) &
                        (E - sessions <= np.timedelta64(9, "D"))]
        if len(cand) == 0:
            continue
        t0 = cand[-1]
        ch = opt[(opt.dt == t0) & (opt.exp == E) & (opt.vol > 0) & (opt.oi > 0)]
        if len(ch) < 20 or t0 not in spot.index or E not in spot.index:
            continue
        S0 = float(spot[t0])
        ks = np.sort(ch.K.unique())
        K = float(ks[np.argmin(np.abs(ks - S0))])

        path = sessions[(sessions >= t0) & (sessions <= E)]
        if len(path) < 3:
            continue

        # ---- daily marks for the two legs on the exact strike K ----
        legs = {}
        ok = True
        for cp in ("CE", "PE"):
            s_ = opt[(opt.exp == E) & (opt.K == K) & (opt.cp == cp)].set_index("dt").close
            s_ = s_[~s_.index.duplicated()]
            if t0 not in s_.index:
                ok = False
                break
            legs[cp] = s_
        if not ok:
            continue

        # ---- futures series: the contract expiring on/after E, nearest ----
        fx = fut[fut.exp >= E]
        if fx.empty:
            continue
        fexp = fx.exp.min()
        fs = fut[fut.exp == fexp].set_index("dt").close
        fs = fs[~fs.index.duplicated()]
        if not all(d in fs.index for d in path):
            continue

        # ---- ENTRY: sell 1 straddle ----
        prem0 = float(legs["CE"].get(t0, np.nan)) + float(legs["PE"].get(t0, np.nan))
        if not np.isfinite(prem0) or prem0 <= 0:
            continue
        # received premium, net of crossing the spread on both legs
        prem_rec_pts = prem0 - 2 * HS_OPT
        cash = prem_rec_pts * LOT * n_lots - opt_sell_cost(prem0, 2, n_lots)

        # ---- hedge path ----
        H = 0.0                       # current futures position, index-units (per n_lots)
        ivs, hedge_trades, hedge_units = [], 0, 0.0
        last_iv = np.nan
        for i, d in enumerate(path):
            Sd = float(spot[d]) if d in spot.index else np.nan
            Fd = float(fs[d])
            T = (pd.Timestamp(E) - pd.Timestamp(d)).days / 365.0
            # mark-to-market of the hedge over the step
            if i > 0:
                Fprev = float(fs[path[i - 1]])
                cash += H * (Fd - Fprev)
            if d == E or not hedge:
                if d == E:
                    break
                if not hedge:
                    continue
            # re-invert IV from today's traded closes on strike K
            vs = []
            for cp in ("CE", "PE"):
                px = legs[cp].get(d, np.nan)
                if np.isfinite(px) and np.isfinite(Sd) and T > 0:
                    v = iv(float(px), Sd, K, T, cp)
                    if np.isfinite(v) and 0.02 < v < 2.0:
                        vs.append(v)
            v = float(np.mean(vs)) if vs else last_iv
            if not np.isfinite(v):
                continue
            last_iv = v
            if i == 0:
                ivs.append(v)
            # target hedge = -(short straddle delta), in index-units
            tgt = -straddle_delta(Sd, K, T, v) * LOT * n_lots
            if integer_lots:
                tgt = LOT * round(tgt / LOT)
            dq = tgt - H
            cash -= fut_trade_cost(dq, Fd)
            if abs(dq) > 1e-9:
                hedge_trades += 1
                hedge_units += abs(dq)
            H = tgt

        # ---- EXPIRY settlement ----
        SE = float(spot[E])
        intr = max(0.0, SE - K) + max(0.0, K - SE)
        n_itm = int(max(0.0, SE - K) > 0) + int(max(0.0, K - SE) > 0)
        cash -= intr * LOT * n_lots
        cash -= BRK_OPT * n_itm * n_lots * (1 + GST)   # brokerage on assigned legs
        # close the residual hedge at expiry settlement
        cash -= fut_trade_cost(-H, float(fs[E]))

        cap = CAPITAL * n_lots
        recs.append(dict(exp=pd.Timestamp(E).date(), t0=pd.Timestamp(t0).date(),
                         S0=S0, K=K, SE=SE, prem=prem0, iv0=(ivs[0] if ivs else np.nan),
                         move=abs(SE / S0 - 1), n_days=len(path),
                         hedges=hedge_trades, hedge_units=hedge_units,
                         pnl=cash, ret=cash / cap))
    return pd.DataFrame(recs)


def stats(r, label):
    x = r.ret.values
    n = len(x)
    mu, sd = x.mean(), x.std(ddof=1)
    t = mu / sd * math.sqrt(n)
    sr_w = mu / sd
    sr_ann = sr_w * math.sqrt(52)
    eq = np.cumsum(x)
    dd = float((eq - np.maximum.accumulate(eq)).min())
    yrs = (2.0 / sr_ann) ** 2 if sr_ann > 0 else float("inf")
    return dict(label=label, n=n, mean_pnl=r.pnl.mean(), mean_ret=mu, sd=sd,
                t=t, sharpe_ann=sr_ann, years_to_t2=yrs, win=(x > 0).mean(),
                worst=x.min(), worst_pnl=r.pnl.min(), maxdd=dd,
                total=eq[-1], hedges=r.hedges.mean())


if __name__ == "__main__":
    OPT, FUT = load()
    print(f"loaded {len(OPT):,} NIFTY option rows, {len(FUT):,} futures rows, "
          f"{OPT.dt.nunique()} sessions "
          f"{OPT.dt.min().date()}..{OPT.dt.max().date()}\n", flush=True)

    out = []
    base = run(hedge=True)
    out.append((stats(base, "delta-hedged daily (fractional)"), base))
    unh = run(hedge=False)
    out.append((stats(unh, "UNHEDGED short straddle"), unh))
    intl = run(hedge=True, integer_lots=True, n_lots=1)
    out.append((stats(intl, "delta-hedged, INTEGER lots, 1 lot"), intl))
    intl5 = run(hedge=True, integer_lots=True, n_lots=5)
    out.append((stats(intl5, "delta-hedged, INTEGER lots, 5 lots"), intl5))
    cheap = run(hedge=True, hs_opt=0.25, hs_fut=0.10)
    out.append((stats(cheap, "hedged, OPTIMISTIC spreads"), cheap))
    wide = run(hedge=True, hs_opt=1.00, hs_fut=0.50)
    out.append((stats(wide, "hedged, WIDE spreads"), wide))

    hdr = f"{'variant':38s} {'n':>4} {'meanRs':>9} {'mean%':>7} {'t':>6} {'SR_ann':>7} {'yrs->t2':>9} {'win%':>6} {'worstRs':>10} {'maxDD%':>8}"
    print(hdr)
    print("-" * len(hdr))
    for s, _ in out:
        print(f"{s['label']:38s} {s['n']:4d} {s['mean_pnl']:9.0f} {s['mean_ret']*100:7.3f} "
              f"{s['t']:6.2f} {s['sharpe_ann']:7.2f} {s['years_to_t2']:9.1f} "
              f"{s['win']*100:6.1f} {s['worst_pnl']:10.0f} {s['maxdd']*100:8.1f}")

    b = base
    print(f"\nGROSS check (no costs is not simulated; premium/costs breakdown):")
    print(f"  mean premium sold      : {b.prem.mean():8.1f} pts = Rs{b.prem.mean()*LOT:,.0f}")
    print(f"  mean hedge adjustments : {b.hedges.mean():8.2f} per week")
    print(f"  mean hedge turnover    : {b.hedge_units.mean():8.1f} index-units/week")
    print(f"  mean entry ATM IV      : {b.iv0.mean()*100:8.2f}%")
    print(f"\nTAIL, delta-hedged daily:")
    w = b.nsmallest(5, "pnl")[["exp", "S0", "SE", "prem", "move", "pnl", "ret"]]
    print(w.to_string(index=False))
    print(f"\nBEST 3:")
    print(b.nlargest(3, "pnl")[["exp", "move", "pnl", "ret"]].to_string(index=False))

    base.to_csv(Path(__file__).resolve().parent / "data" / "dh_straddle_weekly.csv", index=False)
    json.dump([s for s, _ in out], open(Path(__file__).resolve().parent / "data" / "dh_straddle_stats.json", "w"),
              indent=1, default=str)
    print(f"\nwrote quant/data/dh_straddle_weekly.csv")
