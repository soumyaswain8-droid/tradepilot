#!/usr/bin/env python3
"""
quant/validate_sf_adjusted.py — DEFINITIVE momentum test: survivorship-free AND
corporate-action-adjusted.

Resolves the confound in validate_survivorship_free.py (bhavcopy CLOSE_PRICE is raw
/ unadjusted -> splits corrupt momentum). Fix WITHOUT new data: NSE sets bhavcopy
PREV_CLOSE to the adjusted reference on ex-dates, so daily return = CLOSE/PREV_CLOSE
is corporate-action-adjusted. We build momentum from chained log-returns (split-safe)
on the survivorship-free universe with a point-in-time liquidity filter.

If momentum is STILL ~0 here, the edge was a survivorship mirage (verdict: do not
build the positional book on it). Honest, our rules.
Usage: python3 quant/validate_sf_adjusted.py [--topn 200]
"""
import sys, glob, math, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

BHAV = Path(__file__).resolve().parent / "data" / "bhavcopy"
TOPN = int(sys.argv[sys.argv.index("--topn")+1]) if "--topn" in sys.argv else 200
COST = 23.0; ANN=252; H=21; Q=0.2; LB=252

def build():
    rets=[]; turns=[]
    for f in sorted(glob.glob(str(BHAV/"*.csv"))):
        try:
            df=pd.read_csv(f); df.columns=[c.strip() for c in df.columns]
            df=df[df["SERIES"].str.strip()=="EQ"].copy()
            sym=df["SYMBOL"].str.strip()
            d=pd.to_datetime(df["DATE1"].str.strip(), format="%d-%b-%Y", errors="coerce").iloc[0]
            r=pd.to_numeric(df["CLOSE_PRICE"],errors="coerce")/pd.to_numeric(df["PREV_CLOSE"],errors="coerce")-1.0
            rets.append(pd.Series(r.values, index=sym, name=d))
            turns.append(pd.Series(pd.to_numeric(df["TURNOVER_LACS"],errors="coerce").values, index=sym, name=d))
        except Exception: continue
    ret=pd.DataFrame(rets).sort_index(); turn=pd.DataFrame(turns).sort_index()
    ret=ret.loc[:,~ret.columns.duplicated()]; turn=turn.loc[:,~turn.columns.duplicated()]
    ret=ret[~ret.index.duplicated()]; turn=turn[~turn.index.duplicated()]   # dedup dates too
    # clip absurd daily returns (bad ticks / unadjusted residual) to +-50%
    ret=ret.clip(-0.5,0.5)
    return ret, turn

def run(ret, turn, gated=False):
    lr=np.log1p(ret.fillna(0.0))            # adjusted log-returns, missing=0
    cumlr=lr.cumsum()
    mom=cumlr.shift(21)-cumlr.shift(LB)     # 12-1 momentum from chained adj returns
    advn=turn.rolling(60).mean()
    idx_lr=lr.mean(axis=1); idx=idx_lr.cumsum(); dma=idx.rolling(200).mean()
    rebal=ret.index[LB+1::H]; out=[]; ics=[]; prev=pd.Series(0.0,index=ret.columns)
    for i,d in enumerate(rebal[:-1]):
        liq=advn.loc[d].dropna(); univ=liq[liq>0].nlargest(TOPN).index
        sig=mom.loc[d,univ].dropna()
        if len(sig)<20: continue
        if gated and not (idx.loc[d]>dma.loc[d]): out.append(0.0); continue
        n=max(1,int(len(sig)*Q)); w=pd.Series(0.0,index=ret.columns)
        w[sig.nlargest(n).index]=0.5/n; w[sig.nsmallest(n).index]=-0.5/n
        nxt=rebal[i+1]
        fwd=(cumlr.loc[nxt]-cumlr.loc[d]).apply(np.expm1)   # adj forward return d->nxt
        gross=(w*fwd.reindex(w.index).fillna(0)).sum()
        out.append(gross-(w-prev).abs().sum()*COST/10000.0); prev=w
        cmn=sig.index.intersection(fwd.dropna().index)
        if len(cmn)>10: ics.append(sig[cmn].rank().corr(fwd[cmn].rank()))
    pr=pd.Series(out); ppy=ANN/H
    sr=pr.mean()/pr.std()*math.sqrt(ppy) if pr.std()>0 else 0
    ann=(1+pr).prod()**(ppy/len(pr))-1 if len(pr) else 0
    eq=(1+pr).cumprod(); dd=(eq/eq.cummax()-1).min() if len(pr) else 0
    return dict(sharpe=sr,ann=ann,ic=np.mean(ics) if ics else 0,maxdd=dd,n=len(pr))

def main():
    print("building survivorship-free + corp-action-adjusted panel from bhavcopy PREV_CLOSE...")
    ret,turn=build()
    print(f"  {ret.shape[1]} symbols (incl delisted), {ret.shape[0]} days\n")
    b=run(ret,turn,False); g=run(ret,turn,True)
    print(f"ADJUSTED + survivorship-free, top-{TOPN}, momentum 252d/21d, net {COST}bps:")
    print(f"  momentum        : Sharpe {b['sharpe']:.2f}  ann {b['ann']*100:.1f}%  IC {b['ic']:.3f}  maxDD {b['maxdd']*100:.1f}%  (n={b['n']})")
    print(f"  + regime-gated  : Sharpe {g['sharpe']:.2f}  ann {g['ann']*100:.1f}%  IC {g['ic']:.3f}  maxDD {g['maxdd']*100:.1f}%")
    print(f"\nVERDICT scale: |Sharpe|<0.3 = no edge; 0.3-0.6 marginal; >0.8 real.")
    print("vs survivorship-BIASED yfinance 1.12 and raw-unadjusted SF -0.07.")

if __name__=="__main__":
    main()
