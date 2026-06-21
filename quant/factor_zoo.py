#!/usr/bin/env python3
"""
quant/factor_zoo.py — compare several standard cross-sectional factors honestly.

Momentum came back weak (real Sharpe ~0.6, DSR fail). This tests whether a
less-crowded or complementary factor does better on the same NSE cache, and
whether a simple blend improves risk-adjusted return. Same engine: long top
quintile / short bottom quintile, monthly rebalance, net of cost.

Factors (all cross-sectional, computed at each rebalance date):
  mom12_1   12-month momentum, skip last month (the baseline)
  revers_5  short-term reversal: long 5d losers / short 5d winners
  lowvol    long low 60d-realized-vol / short high (low-vol anomaly)
  blend     equal z-score blend of mom12_1 + lowvol (de-correlated combo)

Honest: same survivorship-biased cache, flat cost, daily-close fills. Numbers are
directional (which factor is least-bad), not deployable P&L. Our rules.
Usage: python3 quant/factor_zoo.py [--cost-bps 23]
"""
import sys, glob, math, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

DATA = Path(__file__).resolve().parent / "data" / "eod"
COST = float(sys.argv[sys.argv.index("--cost-bps")+1]) if "--cost-bps" in sys.argv else 23.0
ANN=252; H=21; Q=0.2

def load_panel():
    c={}
    for f in sorted(glob.glob(str(DATA/"*.parquet"))+glob.glob(str(DATA/"*.pkl"))):
        s=Path(f).stem
        if s.startswith("_"): continue
        try:
            df=pd.read_parquet(f) if f.endswith("parquet") else pd.read_pickle(f)
            c[s]=df["Close"]
        except Exception: pass
    return pd.DataFrame(c).sort_index()

def zscore(s):
    return (s - s.mean())/s.std(ddof=0) if s.std(ddof=0)>0 else s*0

def factor(name, panel, d):
    """Return a cross-sectional score Series at date d (higher = prefer LONG)."""
    px=panel.loc[:d]
    if name=="mom12_1":
        return panel.shift(21).loc[d]/panel.shift(252).loc[d]-1.0
    if name=="revers_5":
        return -(panel.loc[d]/panel.shift(5).loc[d]-1.0)              # long losers
    if name=="lowvol":
        vol=panel.pct_change().rolling(60).std().loc[d]
        return -vol                                                   # long low vol
    if name=="blend":
        m=panel.shift(21).loc[d]/panel.shift(252).loc[d]-1.0
        vol=panel.pct_change().rolling(60).std().loc[d]
        return zscore(m.dropna()).add(zscore(-vol.dropna()), fill_value=np.nan)
    raise ValueError(name)

def backtest(panel, name):
    rebal=panel.index[252+1::H]; rets=[]; ics=[]; turn=[]; prev=pd.Series(0.0,index=panel.columns)
    for i,d in enumerate(rebal[:-1]):
        sig=factor(name,panel,d).dropna(); sig=sig[panel.loc[d,sig.index]>5]
        if len(sig)<20: continue
        n=max(1,int(len(sig)*Q)); w=pd.Series(0.0,index=panel.columns)
        w[sig.nlargest(n).index]=0.5/n; w[sig.nsmallest(n).index]=-0.5/n
        nxt=rebal[i+1]; fwd=panel.loc[nxt]/panel.loc[d]-1.0
        gross=(w*fwd.reindex(w.index).fillna(0)).sum()
        rets.append(gross-(w-prev).abs().sum()*COST/10000.0); prev=w; turn.append((w-prev).abs().sum())
        cmn=sig.index.intersection(fwd.dropna().index)
        if len(cmn)>10: ics.append(sig[cmn].rank().corr(fwd[cmn].rank()))
    if len(rets)<5: return None
    pr=pd.Series(rets); ppy=ANN/H
    sr=pr.mean()/pr.std()*math.sqrt(ppy) if pr.std()>0 else 0
    ann=(1+pr).prod()**(ppy/len(pr))-1
    eq=(1+pr).cumprod(); dd=(eq/eq.cummax()-1).min()
    return dict(name=name,sharpe=sr,ann=ann,ic=np.mean(ics) if ics else 0,maxdd=dd,n=len(pr))

def main():
    panel=load_panel()
    print(f"panel {panel.shape[1]} syms x {panel.shape[0]} days, monthly hold, net {COST}bps\n")
    print(f"{'factor':10} {'Sharpe':>7} {'annRet':>8} {'rankIC':>7} {'maxDD':>8} {'n':>4}")
    rows=[]
    for f in ["mom12_1","revers_5","lowvol","blend"]:
        r=backtest(panel,f)
        if r: rows.append(r); print(f"{r['name']:10} {r['sharpe']:>7.2f} {r['ann']*100:>7.1f}% {r['ic']:>7.3f} {r['maxdd']*100:>7.1f}% {r['n']:>4}")
    if rows:
        best=max(rows,key=lambda x:x['sharpe'])
        print(f"\nBest raw Sharpe: {best['name']} ({best['sharpe']:.2f}). NOTE: still survivorship-biased "
              f"upper bound; subtract ~4%/yr + apply multiple-testing (we tested 4) before trusting.")

if __name__=="__main__":
    main()
