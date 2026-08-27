#!/usr/bin/env python3
"""
quant/fo_vrp_analysis.py — measure the REAL NIFTY weekly variance risk premium
from expired-contract closes, then price a defined-risk iron condor after costs.

Inputs : quant/data/fo_bhavcopy/fo_YYYY-MM-DD.csv (UDiFF or legacy schema)
Outputs: prints a numeric report.

No VIX. No Black-Scholes forward-pricing. BS is used ONLY to INVERT a traded
close into an implied vol; every price in the P&L path is an actual print.
"""
import sys, math, glob, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).resolve().parent / "data" / "fo_bhavcopy"
R = 0.065                      # India risk-free ~6.5%
UND = "NIFTY"
SDS = [0.75, 1.0, 1.25, 1.5]

# ---------------------------------------------------------------- load
def load():
    rows = []
    for f in sorted(glob.glob(str(D / "fo_*.csv"))):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "TckrSymb" in df.columns:                       # UDiFF
            df = df[(df.TckrSymb == UND) & (df.OptnTp.isin(["CE", "PE"]))]
            if df.empty:
                continue
            out = pd.DataFrame({
                "dt": pd.to_datetime(df.TradDt), "exp": pd.to_datetime(df.XpryDt),
                "K": df.StrkPric.astype(float), "cp": df.OptnTp,
                "close": df.ClsPric.astype(float), "spot": df.UndrlygPric.astype(float),
                "oi": df.OpnIntrst.astype(float), "vol": df.TtlTradgVol.astype(float)})
        elif "SYMBOL" in df.columns:                       # legacy
            df = df[(df.SYMBOL == UND) & (df.OPTION_TYP.isin(["CE", "PE"]))]
            if df.empty:
                continue
            out = pd.DataFrame({
                "dt": pd.to_datetime(df.TIMESTAMP, format="%d-%b-%Y"),
                "exp": pd.to_datetime(df.EXPIRY_DT, format="%d-%b-%Y"),
                "K": df.STRIKE_PR.astype(float), "cp": df.OPTION_TYP,
                "close": df.CLOSE.astype(float), "spot": np.nan,
                "oi": df.OPEN_INT.astype(float), "vol": df.CONTRACTS.astype(float)})
        else:
            continue
        rows.append(out)
    if not rows:
        sys.exit("no NIFTY option rows found")
    return pd.concat(rows, ignore_index=True)

# ---------------------------------------------------------------- BS invert
def bs(S, K, T, s, cp):
    if T <= 0 or s <= 0:
        return max(0.0, S - K) if cp == "CE" else max(0.0, K - S)
    d1 = (math.log(S / K) + (R + s * s / 2) * T) / (s * math.sqrt(T))
    d2 = d1 - s * math.sqrt(T)
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    if cp == "CE":
        return S * N(d1) - K * math.exp(-R * T) * N(d2)
    return K * math.exp(-R * T) * N(-d2) - S * N(-d1)

def iv(px, S, K, T, cp):
    """Bisection on a monotone-in-vol price. Returns nan if px outside bounds."""
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

# ---------------------------------------------------------------- main
def main():
    df = load()
    df = df[df.close > 0]
    spot = df.dropna(subset=["spot"]).groupby("dt").spot.median()
    sessions = np.array(sorted(df.dt.unique()))
    print(f"loaded {len(df):,} NIFTY option rows, {len(sessions)} sessions "
          f"{pd.Timestamp(sessions[0]).date()}..{pd.Timestamp(sessions[-1]).date()}")
    print(f"spot series: {len(spot)} days\n")

    # daily log returns of NIFTY spot -> realised vol source
    lr = np.log(spot).diff()

    # expiry universe: every expiry that actually settled inside our window
    exps = np.array(sorted(df.exp.unique()))
    exps = exps[(exps >= sessions[0]) & (exps <= sessions[-1])]

    recs = []
    for E in exps:
        # entry = last session that is >=5 and <=9 calendar days before expiry
        # (i.e. the prior weekly expiry / roll day) -> a true ~1-week hold
        cand = sessions[(E - sessions >= np.timedelta64(5, "D")) &
                        (E - sessions <= np.timedelta64(9, "D"))]
        if len(cand) == 0:
            continue
        t = cand[-1]
        ch = df[(df.dt == t) & (df.exp == E) & (df.vol > 0) & (df.oi > 0)]
        if len(ch) < 20 or t not in spot.index or E not in spot.index:
            continue
        S, SE = float(spot[t]), float(spot[E])
        T = (pd.Timestamp(E) - pd.Timestamp(t)).days / 365.0
        Tn = int(((sessions > t) & (sessions <= E)).sum())          # trading days
        if Tn < 3:
            continue

        # --- ATM implied vol, from the actual traded close ---
        ks = np.sort(ch.K.unique())
        Katm = ks[np.argmin(np.abs(ks - S))]
        ivs = []
        for cp in ("CE", "PE"):
            r_ = ch[(ch.K == Katm) & (ch.cp == cp)]
            if len(r_):
                v = iv(float(r_.close.iloc[0]), S, Katm, T, cp)
                if v == v and 0.02 < v < 2.0:
                    ivs.append(v)
        if not ivs:
            continue
        iv_atm = float(np.mean(ivs))

        # --- realised vol over the exact hold window ---
        seg = lr[(lr.index > t) & (lr.index <= E)].dropna()
        if len(seg) < 3:
            continue
        rv = float(seg.std(ddof=1) * math.sqrt(252))
        # close-to-close realised move actually delivered
        move = abs(SE / S - 1)

        # --- iron condor, short strikes at NSD sigma, wings +5 strike steps ---
        step = float(np.median(np.diff(ks))) if len(ks) > 3 else 50.0
        sig_pts = S * iv_atm * math.sqrt(T)          # 1-sd expected move, priced-in

        def intr(K_, cp):
            return max(0.0, SE - K_) if cp == "CE" else max(0.0, K_ - SE)

        rec = dict(exp=pd.Timestamp(E).date(), t=pd.Timestamp(t).date(),
                   S=S, SE=SE, Tn=Tn, iv=iv_atm, rv=rv, move=move)
        for nsd in SDS:
            Kc = step * round((S + nsd * sig_pts) / step)
            Kp = step * round((S - nsd * sig_pts) / step)
            width = 5 * step
            legs, ok = {}, True
            for K_, cp, side in ((Kc, "CE", -1), (Kc + width, "CE", +1),
                                 (Kp, "PE", -1), (Kp - width, "PE", +1)):
                r_ = ch[(ch.K == K_) & (ch.cp == cp)]
                if not len(r_):
                    ok = False
                    break
                legs[(K_, cp)] = (float(r_.close.iloc[0]), side)
            if not ok:
                continue
            credit = sum(-side * px for px, side in legs.values())
            if credit <= 0 or credit >= width:
                continue
            settle = sum(side * intr(K_, cp) for (K_, cp), (px, side) in legs.items())
            rec[f"credit{nsd}"] = credit
            rec[f"gross{nsd}"] = credit + settle      # credit kept + net settlement
            rec[f"maxrisk{nsd}"] = width - credit
        recs.append(rec)

    r = pd.DataFrame(recs)
    if r.empty:
        sys.exit("no usable expiries")
    print(f"=== VARIANCE RISK PREMIUM, n={len(r)} weekly expiries ===")
    print(f"  mean ATM implied vol (inverted from traded close): {r.iv.mean()*100:6.2f}%")
    print(f"  mean realised vol over the same window          : {r.rv.mean()*100:6.2f}%")
    print(f"  mean VRP (IV - RV)                              : {(r.iv-r.rv).mean()*100:6.2f} vol pts")
    d = r.iv - r.rv
    print(f"  VRP t-stat = {d.mean()/d.std(ddof=1)*math.sqrt(len(d)):.2f}   "
          f"share of weeks IV>RV = {(d>0).mean()*100:.1f}%")
    print(f"  median IV = {r.iv.median()*100:.2f}%   median RV = {r.rv.median()*100:.2f}%")

    print("\n=== IRON CONDOR, wings +5 strike steps, held to expiry ===")
    print("  short   cost                       n   mean%maxrisk    t   win%    maxDD%   worst%")
    for nsd in SDS:
        g, c, m = f"gross{nsd}", f"credit{nsd}", f"maxrisk{nsd}"
        if g not in r.columns:
            continue
        s = r.dropna(subset=[g, c, m])
        s = s[s[m] > 0]
        if len(s) < 20:
            continue
        for cf, lbl in ((0.0, "gross"), (0.006, "0.60% prem (brief)"),
                        (0.02, "+2% slip"), (0.05, "+5% slip")):
            ret = (s[g] - cf * s[c]) / s[m]
            eq = ret.cumsum()
            dd = float((eq - eq.cummax()).min())
            t_ = ret.mean() / ret.std(ddof=1) * math.sqrt(len(ret))
            print(f"  {nsd:>4.2f}sd  {lbl:22s} {len(s):4d} {ret.mean()*100:9.2f}   "
                  f"{t_:6.2f} {(ret>0).mean()*100:6.1f} {dd*100:9.1f} {ret.min()*100:8.1f}")
        print(f"        mean credit={s[c].mean():6.1f}pts  mean maxrisk={s[m].mean():6.1f}pts  "
              f"0.60% cost={0.006*s[c].mean():.2f}pts = {0.006*s[c].mean()/s[m].mean()*100:.3f}% of capital")
    r.to_csv(D.parent / "nifty_weekly_vrp.csv", index=False)
    print(f"\n  wrote {D.parent/'nifty_weekly_vrp.csv'}")


if __name__ == "__main__":
    main()
