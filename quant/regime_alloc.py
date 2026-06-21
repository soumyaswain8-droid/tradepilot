#!/usr/bin/env python3
"""
quant/regime_alloc.py — does regime-gating improve the momentum book?

Factor zoo showed momentum is the only positive factor but regime-exposed (low-vol
inverted in the bull). The standard fix is a market-regime filter: hold the momentum
book only when the index is in an up-trend (NIFTY > 200-DMA) and/or vol is not
elevated; go to cash otherwise. Tests whether that cuts drawdown + lifts Sharpe.

Compares: momentum standalone vs (a) 200-DMA-gated, (b) vol-gated, (c) both.
Reads the local EOD cache (NIFTY = _NSEI). Honest: still survivorship-biased,
single 5y-mostly-bull sample (so the gate has few bear days to prove itself).
Usage: python3 quant/regime_alloc.py [--cost-bps 23]
"""
import sys, glob, math, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

DATA = Path(__file__).resolve().parent / "data" / "eod"
COST = float(sys.argv[sys.argv.index("--cost-bps")+1]) if "--cost-bps" in sys.argv else 23.0
ANN=252; H=21; Q=0.2; LB=252

def load():
    closes={}; nifty=None
    for f in sorted(glob.glob(str(DATA/"*.parquet"))+glob.glob(str(DATA/"*.pkl"))):
        s=Path(f).stem
        try: df=pd.read_parquet(f) if f.endswith("parquet") else pd.read_pickle(f)
        except Exception: continue
        if s=="_NSEI": nifty=df["Close"]
        elif not s.startswith("_"): closes[s]=df["Close"]
    return pd.DataFrame(closes).sort_index(), nifty

def mom_series(panel):
    """Per-rebalance momentum return series + the rebalance dates."""
    mom=panel.shift(21)/panel.shift(LB)-1.0
    rebal=panel.index[LB+1::H]; rets=[]; dates=[]; prev=pd.Series(0.0,index=panel.columns)
    for i,d in enumerate(rebal[:-1]):
        sig=mom.loc[d].dropna(); sig=sig[panel.loc[d,sig.index]>5]
        if len(sig)<20: continue
        n=max(1,int(len(sig)*Q)); w=pd.Series(0.0,index=panel.columns)
        w[sig.nlargest(n).index]=0.5/n; w[sig.nsmallest(n).index]=-0.5/n
        nxt=rebal[i+1]; fwd=panel.loc[nxt]/panel.loc[d]-1.0
        rets.append((w*fwd.reindex(w.index).fillna(0)).sum()-(w-prev).abs().sum()*COST/10000.0)
        dates.append(d); prev=w
    return pd.Series(rets,index=pd.DatetimeIndex(dates))

def stats(pr, ppy=ANN/H):
    if len(pr)<5 or pr.std()==0: return (0,0,0)
    sr=pr.mean()/pr.std()*math.sqrt(ppy)
    ann=(1+pr).prod()**(ppy/len(pr))-1
    eq=(1+pr).cumprod(); dd=(eq/eq.cummax()-1).min()
    return sr,ann,dd

def main():
    panel,nifty=load()
    if nifty is None: print("NIFTY (_NSEI) not in cache"); return
    pr=mom_series(panel)
    # regime signals evaluated at each rebalance date (point-in-time, no lookahead)
    dma200=nifty.rolling(200).mean()
    nret=nifty.pct_change()
    vol60=nret.rolling(60).std()*math.sqrt(ANN)
    vol_med=vol60.median()
    up=(nifty>dma200)             # trend up
    calm=(vol60<vol_med*1.3)      # vol not elevated
    def gate(mask):
        # at rebalance date d, hold book only if mask true at d (else cash=0)
        g=pd.Series(index=pr.index,dtype=float)
        for d in pr.index:
            m=mask.reindex([d],method="ffill").iloc[0]
            g[d]=pr[d] if (m==True) else 0.0
        return g
    variants={
        "momentum (ungated)": pr,
        "200DMA-gated": gate(up),
        "vol-gated": gate(calm),
        "200DMA + vol": gate(up & calm),
    }
    print(f"panel {panel.shape[1]} syms, {len(pr)} rebals, net {COST}bps\n")
    print(f"{'variant':22} {'Sharpe':>7} {'annRet':>8} {'maxDD':>8} {'%inMkt':>7}")
    for name,s in variants.items():
        sr,ann,dd=stats(s)
        inmkt=100*(s!=0).mean()
        print(f"{name:22} {sr:>7.2f} {ann*100:>7.1f}% {dd*100:>7.1f}% {inmkt:>6.0f}%")
    print("\nNOTE: 5y-mostly-bull sample => the gate has few bear days to prove itself;")
    print("real value of regime-gating shows in bear/correction periods absent here.")
    print("Honest read: if gating lifts Sharpe / cuts maxDD even a little here, it's worth")
    print("keeping; the bigger payoff needs an out-of-sample bear stretch to confirm.")

if __name__=="__main__":
    main()
