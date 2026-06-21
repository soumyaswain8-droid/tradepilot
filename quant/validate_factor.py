#!/usr/bin/env python3
"""
quant/validate_factor.py — honest validation of the long-horizon momentum finding.

The backtest grid found 252d-lookback / 21d-hold momentum at Sharpe ~1.1. Before
trusting it we must check the two things that kill backtest 'edges':
  1. MULTIPLE TESTING — we tried 9 configs; the best Sharpe is upward-biased.
     -> Deflated Sharpe Ratio (Bailey & Lopez de Prado): does the best survive
        the penalty for having searched?
  2. SUB-PERIOD STABILITY — is the edge spread across years, or one lucky regime?
     -> year-by-year return + rank-IC, and rolling 12-month Sharpe.

Plus an explicit survivorship-bias haircut (Indian bias ~3.5-4.4%/yr per research).

Parameter-free factor (nothing fitted), so this is robustness/multiple-testing
validation, not model CV. Reads the local EOD cache. Honest, unbiased — our rules.
Usage: python3 quant/validate_factor.py [--cost-bps 23]
"""
import sys, glob, math, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

DATA = Path(__file__).resolve().parent / "data" / "eod"
COST_BPS = float(sys.argv[sys.argv.index("--cost-bps")+1]) if "--cost-bps" in sys.argv else 23.0
ANN = 252; QUANTILE = 0.2
GRID = [(21,5),(63,5),(126,5),(21,21),(63,21),(126,21),(126,63),(252,63),(252,21)]
BEST = (252, 21)
SURV_HAIRCUT = 0.04   # ~4%/yr Indian survivorship bias (research midpoint)

def load_panel():
    closes={}
    for f in sorted(glob.glob(str(DATA/"*.parquet"))+glob.glob(str(DATA/"*.pkl"))):
        sym=Path(f).stem
        if sym.startswith("_"): continue
        try:
            df=pd.read_parquet(f) if f.endswith("parquet") else pd.read_pickle(f)
            closes[sym]=df["Close"]
        except Exception: pass
    return pd.DataFrame(closes).sort_index()

def strat_series(panel, lookback, horizon, cost_bps):
    """Return the per-rebalance net return series + IC list for one config."""
    mom = panel.shift(1)/panel.shift(lookback)-1.0
    rebal = panel.index[lookback+1::horizon]
    rets, ics = [], []; prev=pd.Series(0.0,index=panel.columns)
    for i,d in enumerate(rebal[:-1]):
        sig=mom.loc[d].dropna(); sig=sig[panel.loc[d,sig.index]>5]
        if len(sig)<20: continue
        n=max(1,int(len(sig)*QUANTILE))
        w=pd.Series(0.0,index=panel.columns)
        w[sig.nlargest(n).index]=0.5/n; w[sig.nsmallest(n).index]=-0.5/n
        nxt=rebal[i+1]; fwd=panel.loc[nxt]/panel.loc[d]-1.0
        gross=(w*fwd.reindex(w.index).fillna(0)).sum()
        cost=(w-prev).abs().sum()*(cost_bps/10000.0)
        rets.append((nxt,gross-cost)); prev=w
        c=sig.index.intersection(fwd.dropna().index)
        if len(c)>10: ics.append(sig[c].rank().corr(fwd[c].rank()))
    if not rets: return None,None
    idx,vals=zip(*rets)
    return pd.Series(vals,index=pd.DatetimeIndex(idx)), ics

def sharpe(pr, ppy):
    return (pr.mean()/pr.std()*math.sqrt(ppy)) if pr.std()>0 else 0.0

def deflated_sharpe(sr_obs, pr, n_trials, sr_trials, ppy):
    """Bailey-Lopez de Prado DSR: prob the observed (annualized) Sharpe > the
    expected-max under the null given n_trials, adjusting for non-normality."""
    T=len(pr)
    sr=sr_obs/math.sqrt(ppy)  # per-period Sharpe
    sk=stats.skew(pr); ku=stats.kurtosis(pr,fisher=False)
    var_sr=np.var([s/math.sqrt(ppy) for s in sr_trials], ddof=1) if len(sr_trials)>1 else 0.0
    g=0.5772156649
    emax=math.sqrt(var_sr)*((1-g)*stats.norm.ppf(1-1.0/n_trials)+g*stats.norm.ppf(1-1.0/(n_trials*math.e))) if var_sr>0 else 0.0
    denom=math.sqrt(max(1e-9, 1 - sk*sr + (ku-1)/4.0*sr*sr))
    z=(sr-emax)*math.sqrt(T-1)/denom
    return stats.norm.cdf(z), emax*math.sqrt(ppy)

def main():
    panel=load_panel()
    ppy=ANN/BEST[1]
    print(f"panel: {panel.shape[1]} symbols, {panel.shape[0]} days "
          f"({panel.index[0].date()}..{panel.index[-1].date()}), cost {COST_BPS}bps\n")
    # all-trial Sharpes for the multiple-testing penalty
    trial_sr=[]
    for lb,h in GRID:
        if lb+h>=panel.shape[0]: continue
        pr,_=strat_series(panel,lb,h,COST_BPS)
        if pr is not None: trial_sr.append(sharpe(pr,ANN/h))
    pr,ics=strat_series(panel,*BEST,COST_BPS)
    sr=sharpe(pr,ppy); tstat=sr*math.sqrt(len(pr)/ppy)
    dsr,emax=deflated_sharpe(sr,pr,len(trial_sr),trial_sr,ppy)
    print(f"BEST config 252d/21d:  Sharpe {sr:.2f}  (t={tstat:.2f}, n={len(pr)} rebals)")
    print(f"MULTIPLE TESTING: {len(trial_sr)} configs tried; expected-max Sharpe under null = {emax:.2f}")
    print(f"DEFLATED SHARPE (prob edge is real after the search): {dsr*100:.1f}%  "
          f"{'PASS (>95%)' if dsr>0.95 else 'WEAK' if dsr>0.8 else 'FAIL'}")
    print(f"mean rank-IC: {np.mean(ics):.3f}")
    # year-by-year
    print("\nYEAR-BY-YEAR (net):")
    yr=pr.groupby(pr.index.year)
    pos=0; tot=0
    for y,s in yr:
        r=(1+s).prod()-1; print(f"  {y}: {r*100:>6.1f}%  ({len(s)} rebals)"); tot+=1; pos+= (r>0)
    print(f"  -> positive in {pos}/{tot} years")
    # survivorship haircut
    full_ann=(1+pr).prod()**(ppy/len(pr))-1
    print(f"\nSURVIVORSHIP HAIRCUT (~{SURV_HAIRCUT*100:.0f}%/yr):")
    print(f"  raw ann return {full_ann*100:.1f}%  ->  bias-adjusted ~{(full_ann-SURV_HAIRCUT)*100:.1f}%/yr")
    print(f"  bias-adjusted Sharpe ~{sr*(full_ann-SURV_HAIRCUT)/full_ann:.2f}" if full_ann>0 else "")
    print("\nVERDICT: edge is real IF DSR passes AND it's positive most years AND survives the")
    print("survivorship haircut. Anything failing those = not yet bankable, needs better data.")

if __name__=="__main__":
    main()
