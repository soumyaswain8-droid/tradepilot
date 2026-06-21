#!/usr/bin/env python3
"""
quant/factor_zoo_clean.py — test multiple factors on HONEST data.

Momentum died on the survivorship-free + corp-action-adjusted universe (Sharpe 0.31,
IC 0.000). This asks: does ANY standard factor survive on clean Indian data? Tests
reversal (1-week, 1-month), short/3-month momentum, low-vol on the same point-in-time
top-N-liquid universe. Caches the assembled panel (ret/turn) so iteration is fast.

Honest: same survivorship-free adjusted bhavcopy data, net of cost. Verdict scale:
|Sharpe|<0.3 noise, 0.3-0.6 marginal, >0.8 real (and must clear DSR/survivorship,
which momentum failed). Our rules.
Usage: python3 quant/factor_zoo_clean.py [--topn 200] [--rebuild]
"""
import sys, glob, math, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).resolve().parent / "data"
BHAV = D / "bhavcopy"
RET_C, TUR_C = D / "sf_ret.parquet", D / "sf_turn.parquet"
TOPN = int(sys.argv[sys.argv.index("--topn")+1]) if "--topn" in sys.argv else 200
COST=23.0; ANN=252; H=21; Q=0.2

def build_or_load():
    if RET_C.exists() and TUR_C.exists() and "--rebuild" not in sys.argv:
        return pd.read_parquet(RET_C), pd.read_parquet(TUR_C)
    rets=[]; turns=[]
    for f in sorted(glob.glob(str(BHAV/"*.csv"))):
        try:
            df=pd.read_csv(f); df.columns=[c.strip() for c in df.columns]
            df=df[df["SERIES"].str.strip()=="EQ"]
            sym=df["SYMBOL"].str.strip()
            d=pd.to_datetime(df["DATE1"].str.strip(),format="%d-%b-%Y",errors="coerce").iloc[0]
            r=pd.to_numeric(df["CLOSE_PRICE"],errors="coerce")/pd.to_numeric(df["PREV_CLOSE"],errors="coerce")-1
            rets.append(pd.Series(r.values,index=sym,name=d))
            turns.append(pd.Series(pd.to_numeric(df["TURNOVER_LACS"],errors="coerce").values,index=sym,name=d))
        except Exception: continue
    ret=pd.DataFrame(rets).sort_index(); turn=pd.DataFrame(turns).sort_index()
    ret=ret.loc[:,~ret.columns.duplicated()][~ret.index.duplicated()].clip(-0.5,0.5)
    turn=turn.loc[:,~turn.columns.duplicated()][~turn.index.duplicated()]
    try: ret.to_parquet(RET_C); turn.to_parquet(TUR_C)
    except Exception: pass
    return ret, turn

def signal(name, cumlr, ret):
    if name=="mom12_1":   return cumlr.shift(21)-cumlr.shift(252)
    if name=="mom_3m":    return cumlr.shift(5)-cumlr.shift(63)
    if name=="rev_1m":    return -(cumlr-cumlr.shift(21))
    if name=="rev_1w":    return -(cumlr-cumlr.shift(5))
    if name=="lowvol":    return -ret.rolling(60).std()

def bt(ret, turn, name):
    cumlr=np.log1p(ret.fillna(0)).cumsum()
    sigp=signal(name,cumlr,ret); advn=turn.rolling(60).mean()
    rebal=ret.index[252+1::H]; out=[]; ics=[]; prev=pd.Series(0.0,index=ret.columns)
    for i,d in enumerate(rebal[:-1]):
        univ=advn.loc[d].dropna(); univ=univ[univ>0].nlargest(TOPN).index
        s=sigp.loc[d,univ].dropna()
        if len(s)<20: continue
        n=max(1,int(len(s)*Q)); w=pd.Series(0.0,index=ret.columns)
        w[s.nlargest(n).index]=0.5/n; w[s.nsmallest(n).index]=-0.5/n
        nxt=rebal[i+1]; fwd=(cumlr.loc[nxt]-cumlr.loc[d]).apply(np.expm1)
        out.append((w*fwd.reindex(w.index).fillna(0)).sum()-(w-prev).abs().sum()*COST/10000); prev=w
        c=s.index.intersection(fwd.dropna().index)
        if len(c)>10: ics.append(s[c].rank().corr(fwd[c].rank()))
    pr=pd.Series(out); ppy=ANN/H
    if len(pr)<5 or pr.std()==0: return None
    sr=pr.mean()/pr.std()*math.sqrt(ppy); ann=(1+pr).prod()**(ppy/len(pr))-1
    eq=(1+pr).cumprod(); dd=(eq/eq.cummax()-1).min()
    return dict(name=name,sharpe=sr,ann=ann,ic=np.mean(ics) if ics else 0,maxdd=dd)

def main():
    print("loading clean survivorship-free + adjusted panel...")
    ret,turn=build_or_load()
    print(f"  {ret.shape[1]} symbols (incl delisted), {ret.shape[0]} days, top-{TOPN}, net {COST}bps\n")
    print(f"{'factor':10} {'Sharpe':>7} {'annRet':>8} {'rankIC':>7} {'maxDD':>8}")
    rows=[]
    for f in ["mom12_1","mom_3m","rev_1m","rev_1w","lowvol"]:
        r=bt(ret,turn,f)
        if r: rows.append(r); print(f"{r['name']:10} {r['sharpe']:>7.2f} {r['ann']*100:>7.1f}% {r['ic']:>7.3f} {r['maxdd']*100:>7.1f}%")
    if rows:
        best=max(rows,key=lambda x:abs(x['sharpe']))
        print(f"\nBest |Sharpe|: {best['name']} ({best['sharpe']:.2f}, IC {best['ic']:.3f}).")
        print("On clean data, edge needs |IC|>~0.03 AND Sharpe>0.8 to be worth pursuing (must still")
        print("clear DSR/multiple-testing). IC~0 = no cross-sectional skill, like momentum.")

if __name__=="__main__":
    main()
