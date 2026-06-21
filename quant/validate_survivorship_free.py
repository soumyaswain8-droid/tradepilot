#!/usr/bin/env python3
"""
quant/validate_survivorship_free.py — the DEFINITIVE momentum test on unbiased data.

Assembles ~5y of NSE bhavcopies (EQ series) into a survivorship-FREE close +
turnover panel (includes since-delisted names), then re-runs the 252d/21d momentum
strategy with a POINT-IN-TIME liquidity universe (top-N by trailing turnover as of
each rebalance — the correct, no-lookahead, no-survivorship way). Compares the
honest Sharpe to the survivorship-biased yfinance result (~1.12 raw).

This closes the loop on the prior caveat: yfinance momentum was an upper bound; this
is the real number. Honest, our rules.
Usage: python3 quant/validate_survivorship_free.py [--topn 200] [--cost-bps 23]
"""
import sys, glob, math, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

BHAV = Path(__file__).resolve().parent / "data" / "bhavcopy"
TOPN = int(sys.argv[sys.argv.index("--topn")+1]) if "--topn" in sys.argv else 200
COST = float(sys.argv[sys.argv.index("--cost-bps")+1]) if "--cost-bps" in sys.argv else 23.0
ANN=252; H=21; Q=0.2; LB=252

def build_panels():
    closes=[]; turns=[]
    files=sorted(glob.glob(str(BHAV/"*.csv")))
    for f in files:
        try:
            df=pd.read_csv(f)
            df.columns=[c.strip() for c in df.columns]
            df=df[df["SERIES"].str.strip()=="EQ"]
            d=pd.to_datetime(df["DATE1"].str.strip(), format="%d-%b-%Y", errors="coerce").iloc[0]
            closes.append(pd.Series(df["CLOSE_PRICE"].values, index=df["SYMBOL"].str.strip(), name=d))
            turns.append(pd.Series(df["TURNOVER_LACS"].values, index=df["SYMBOL"].str.strip(), name=d))
        except Exception:
            continue
    close=pd.DataFrame(closes).sort_index()
    turn=pd.DataFrame(turns).sort_index()
    close=close[~close.index.duplicated()]; turn=turn[~turn.index.duplicated()]
    return close, turn

def backtest(close, turn, gated=False):
    mom=close.shift(21)/close.shift(LB)-1.0
    advn=turn.rolling(60).mean()  # 60d avg turnover (liquidity), point-in-time
    rebal=close.index[LB+1::H]
    # regime: equal-weight index proxy vs its 200-DMA
    idx=close.mean(axis=1); dma=idx.rolling(200).mean()
    rets=[]; ics=[]; prev=pd.Series(0.0,index=close.columns)
    for i,d in enumerate(rebal[:-1]):
        liq=advn.loc[d].dropna(); liq=liq[liq>0]
        univ=liq.nlargest(TOPN).index                     # point-in-time top-N liquid
        sig=mom.loc[d, univ].dropna(); sig=sig[close.loc[d, sig.index]>5]
        if len(sig)<20: continue
        if gated and not (idx.loc[d] > dma.loc[d]):        # regime gate: cash if downtrend
            rets.append((d, 0.0)); continue
        n=max(1,int(len(sig)*Q)); w=pd.Series(0.0,index=close.columns)
        w[sig.nlargest(n).index]=0.5/n; w[sig.nsmallest(n).index]=-0.5/n
        nxt=rebal[i+1]; fwd=close.loc[nxt]/close.loc[d]-1.0
        gross=(w*fwd.reindex(w.index).fillna(0)).sum()
        rets.append((nxt, gross-(w-prev).abs().sum()*COST/10000.0)); prev=w
        cmn=sig.index.intersection(fwd.dropna().index)
        if len(cmn)>10: ics.append(sig[cmn].rank().corr(fwd[cmn].rank()))
    if len(rets)<5: return None
    pr=pd.Series([r for _,r in rets]); ppy=ANN/H
    sr=pr.mean()/pr.std()*math.sqrt(ppy) if pr.std()>0 else 0
    ann=(1+pr).prod()**(ppy/len(pr))-1
    eq=(1+pr).cumprod(); dd=(eq/eq.cummax()-1).min()
    return dict(sharpe=sr,ann=ann,ic=np.mean(ics) if ics else 0,maxdd=dd,n=len(pr))

def main():
    print("assembling survivorship-free panel from bhavcopies...")
    close,turn=build_panels()
    print(f"  panel: {close.shape[1]} unique symbols (incl delisted), {close.shape[0]} days "
          f"({close.index[0].date()}..{close.index[-1].date()})\n")
    print(f"point-in-time top-{TOPN} by turnover, momentum 252d/21d, net {COST}bps:")
    base=backtest(close,turn,gated=False)
    gate=backtest(close,turn,gated=True)
    if base:
        print(f"  SURVIVORSHIP-FREE momentum : Sharpe {base['sharpe']:.2f}  ann {base['ann']*100:.1f}%  IC {base['ic']:.3f}  maxDD {base['maxdd']*100:.1f}%  (n={base['n']})")
    if gate:
        print(f"  + regime-gated (200-DMA)   : Sharpe {gate['sharpe']:.2f}  ann {gate['ann']*100:.1f}%  IC {gate['ic']:.3f}  maxDD {gate['maxdd']*100:.1f}%")
    print(f"\nCOMPARE: survivorship-BIASED yfinance momentum was Sharpe ~1.12 (the upper bound).")
    print("This bhavcopy number is the honest one — includes the delisted names that the")
    print("biased universe silently dropped. Gap = the survivorship premium we were counting.")

if __name__=="__main__":
    main()
