#!/usr/bin/env python3
"""
v5-capacity-study.py (TP-CLN-002) — how much capital can v5 absorb before slippage
eats the edge?

v5 is validated at avg notional Rs 12k/trade (slippage negligible). As position size
grows, market impact grows non-linearly. We re-price every v5 trade at scaled sizes
using a square-root market-impact model calibrated with each stock's REAL liquidity,
then re-run the NIFTY alpha-beta regression at each capital level to find where the
alpha t-stat drops below 2 (edge no longer significant).

IMPACT MODEL (Almgren-style, standard practitioner form):
  one-way impact_bps = C1 * daily_vol_bps * sqrt(participation)
     participation = order_notional / ADV_rupees   (per leg)
     C1 = 0.5  (typical calibration; conservative-to-moderate)
  round-trip cost_bps = BASE_BPS (reg+brokerage, both legs) + 2 * impact_oneway
  P&L scales linearly with size; cost scales super-linearly (size * sqrt(size)).

ASSUMPTIONS / LIMITATIONS (stated):
  - proportional scaling: every position * S (keeps the same trade selection).
  - ADV = median daily turnover over the sample (yfinance daily volume*close).
  - C1=0.5 is a model choice; results reported as a curve, not a point estimate.
  - flags trades exceeding 10% of ADV as practically infeasible (you can't be >10%
    of a day's volume without large additional impact / signalling).
"""
import pickle, math, statistics as st
import warnings; warnings.filterwarnings("ignore")
import yfinance as yf, pandas as pd

BASE_BPS = 11.0     # regulatory + brokerage round-trip (from cost stress test)
C1 = 0.5            # square-root impact coefficient
INFEASIBLE_PARTICIPATION = 0.10   # >10% of ADV per trade = flag infeasible

trades = pickle.load(open('/tmp/v5_trades.pkl','rb'))
syms = pickle.load(open('/tmp/v5_syms.pkl','rb'))
print(f"v5: {len(trades)} trades, {len(syms)} symbols\n")

# ---- fetch daily ADV (rupees) + daily vol (bps) per symbol ----
print("fetching daily liquidity for symbols ...")
tickers=[f"{s}.NS" for s in syms]
dl=yf.download(tickers, start="2026-04-01", end="2026-06-12", interval="1d",
               progress=False, auto_adjust=False, group_by="ticker")
adv={}; volbps={}
for s in syms:
    try:
        sub=dl[f"{s}.NS"][["Close","Volume"]].dropna()
        if len(sub)<5: continue
        turn=(sub["Close"]*sub["Volume"])
        adv[s]=float(turn.median())
        rets=sub["Close"].pct_change().dropna()
        volbps[s]=float(rets.std()*10000) if len(rets)>1 else 150.0
    except Exception:
        pass
print(f"  liquidity resolved for {len(adv)}/{len(syms)} symbols")
med_adv=st.median(list(adv.values()))
# fallback for missing
for s in syms:
    adv.setdefault(s, med_adv); volbps.setdefault(s, 150.0)

# ---- NIFTY intraday returns ----
nf=yf.download("^NSEI", start="2026-04-01", end="2026-06-12", progress=False, auto_adjust=False)
nf.index=pd.to_datetime(nf.index)
def col(n):
    c=nf[n]; return c.iloc[:,0] if getattr(c,'ndim',1)>1 else c
op,cl=col('Open'),col('Close'); ni={}
for ts in nf.index:
    o=float(op.loc[ts]);c=float(cl.loc[ts])
    if not(math.isnan(o) or math.isnan(c)): ni[ts.strftime("%Y-%m-%d")]=100*(c-o)/o

def ols(pts):
    pts=[(x,y) for x,y in pts if None not in (x,y) and not(math.isnan(x) or math.isnan(y))]
    n=len(pts);xs=[p[0] for p in pts];ys=[p[1] for p in pts]
    mx=sum(xs)/n;my=sum(ys)/n
    sxx=sum((x-mx)**2 for x in xs);sxy=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    b=sxy/sxx;a=my-b*mx
    sse=sum((y-(a+b*x))**2 for x,y in zip(xs,ys));sst=sum((y-my)**2 for y in ys)
    s2=sse/(n-2);ta=a/math.sqrt(s2*(1/n+mx*mx/sxx));tb=b/math.sqrt(s2/sxx)
    return a,ta,b,tb

def rt_cost_bps(notional, sym):
    part=notional/adv.get(sym, med_adv)
    impact_oneway=C1*volbps.get(sym,150.0)*math.sqrt(max(part,0))
    return BASE_BPS + 2*impact_oneway, part

base_mean_notional=st.mean([t['notional'] for t in trades])
print(f"\nbase avg notional Rs {base_mean_notional:,.0f}/trade\n")
print(f"{'per-trade':>11} {'~AUM*':>10} {'eff cost':>9} {'NET total':>11} {'alpha/day':>10} {'t_a':>5} {'infeasible%':>11}")
SCALES=[1,2,4,8,12,20,40,80]
ceiling=None
for S in SCALES:
    daily={}; infeas=0; eff_costs=[]
    for t in trades:
        notS=t['notional']*S
        rt,part=rt_cost_bps(notS, t['sym']); eff_costs.append(rt)
        if part>INFEASIBLE_PARTICIPATION: infeas+=1
        grossS=t['gross']*S
        net=grossS - notS*rt/10000
        daily[t['date']]=daily.get(t['date'],0)+net
    a,ta,b,tb=ols([(ni.get(d),daily[d]) for d in daily])
    tot=sum(daily.values())
    per=base_mean_notional*S
    # rough AUM: avg concurrent deployed ~ per-trade * typical concurrent (use 30)
    aum=per*30
    infpct=100*infeas/len(trades)
    print(f"{per:>11,.0f} {aum:>10,.0f} {st.mean(eff_costs):>7.1f}bp {tot:>11,.0f} {a:>10,.0f} {ta:>5.2f} {infpct:>10.0f}%")
    if ceiling is None and ta<2.0: ceiling=(per,aum,ta)

print()
if ceiling:
    print(f"CAPACITY CEILING (alpha t-stat < 2): per-trade ~Rs {ceiling[0]:,.0f}  =>  ~AUM Rs {ceiling[1]:,.0f}")
else:
    print("Alpha t-stat stays > 2 across all tested scales (capacity not reached in range).")
print("*AUM ~ per-trade notional x ~30 concurrent positions (rough).")
print(f"impact model: one-way bps = {C1} * daily_vol_bps * sqrt(notional/ADV); round-trip = {BASE_BPS} + 2*impact.")
