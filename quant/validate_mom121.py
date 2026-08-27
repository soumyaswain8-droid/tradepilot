"""Rigorous validation of mom_12_1 on the survivorship-free panel.

Tests:
 1. Walk-forward (rolling train -> next-month OOS), distribution of OOS monthly returns
 2. N-instability: is the N-curve smooth (effect) or zig-zag (noise)?
 3. Sub-period stability: by year, and by market regime (EW benchmark up/down months)
 4. Real delivery costs incl. flat Rs18.80 DP fee, at Rs25k / Rs1L / Rs5L
 5. Benchmark = equal-weight SAME universe (buy-and-hold-everything)
 6. t-stat of EXCESS over equal-weight
"""
import numpy as np, pandas as pd, sys

D = '/Users/soumyaswain/Documents/tinker/projects/tradepilot/quant/data/'
ret = pd.read_parquet(D + 'sf_ret.parquet')
turn = pd.read_parquet(D + 'sf_turn.parquet')

# ---- monthly compounding -------------------------------------------------
mkey = ret.index.to_period('M')
# monthly return: product of (1+r) over available days; NaN if no data that month
def mret(df):
    g = (1.0 + df).groupby(mkey)
    prod = g.apply(lambda x: x.prod(min_count=1)) - 1.0
    cnt = df.notna().groupby(mkey).sum()
    prod[cnt < 5] = np.nan          # need >=5 trading days to count as tradeable
    return prod
M = mret(ret)
NDAYS = ret.notna().groupby(mkey).sum()
TURN = turn.groupby(mkey).median()          # median daily turnover in the month
M = M.iloc[1:-1]                            # drop partial first/last months
NDAYS = NDAYS.loc[M.index]; TURN = TURN.loc[M.index]
months = M.index
T = len(months)
print(f'months {T}  {months[0]} .. {months[-1]}  symbols {M.shape[1]}', flush=True)

# ---- signal: 12-1 momentum ----------------------------------------------
# at end of month t: cum return over months t-11..t-1 (skip most recent month t)
L1 = (1.0 + M)
SIG = np.full(M.shape, np.nan)
VALID = np.zeros(M.shape, bool)
A = L1.values
for t in range(12, T):
    w = A[t - 11:t, :]                       # 11 months, ending t-1  (skips month t)
    ok = np.isfinite(w).sum(0) >= 10
    ww = np.where(np.isfinite(w), w, 1.0)
    SIG[t, ok] = ww[:, ok].prod(0) - 1.0
    VALID[t, :] = ok
SIG = pd.DataFrame(SIG, index=months, columns=M.columns)

# ---- eligibility: tradeable now, tradeable next month, liquid -------------
LIQ_LAKH = 100.0                             # >= ~Rs1 crore median daily turnover
elig = np.zeros(M.shape, bool)
Mv = M.values; Tv = TURN.values
for t in range(12, T - 1):
    e = VALID[t] & np.isfinite(Mv[t]) & np.isfinite(Mv[t + 1]) & (Tv[t] >= LIQ_LAKH)
    elig[t] = e
print('median eligible universe:', int(np.median(elig[12:T-1].sum(1))), flush=True)

FWD = np.vstack([Mv[1:], np.full((1, M.shape[1]), np.nan)])   # month t -> return of t+1

# ---- cost model (delivery / CNC) ----------------------------------------
STT_SELL, STAMP_BUY, DP_FEE = 0.0020, 0.00015, 18.80

def run(N, t0=12, t1=T - 1, capital=100000.0, charge=True):
    """Returns (dates, net monthly returns, EW benchmark monthly returns, gross)."""
    prev = set(); dates = []; nets = []; gross = []; bench = []
    for t in range(t0, t1):
        e = elig[t]
        if e.sum() < 30:
            continue
        idx = np.where(e)[0]
        s = SIG.values[t, idx]
        pick = idx[np.argsort(-s)[:N]]
        r = np.nanmean(FWD[t, pick])
        b = np.nanmean(FWD[t, idx])
        cur = set(pick.tolist())
        c = 0.0
        if charge:
            pos = capital / N
            sold = len(prev - cur); bought = len(cur - prev)
            c = (sold * (STT_SELL * pos + DP_FEE) + bought * (STAMP_BUY * pos)) / capital
        prev = cur
        dates.append(months[t + 1]); gross.append(r); nets.append(r - c); bench.append(b)
    return (pd.PeriodIndex(dates), np.array(nets), np.array(bench), np.array(gross))

def stats(x):
    x = np.asarray(x, float); n = len(x)
    m = x.mean(); sd = x.std(ddof=1)
    t = m / (sd / np.sqrt(n)) if sd > 0 else np.nan
    ann = (1 + m) ** 12 - 1
    eq = np.cumprod(1 + x); dd = (eq / np.maximum.accumulate(eq) - 1).min()
    return dict(n=n, mean=m, ann=ann, t=t, sd_ann=sd * np.sqrt(12), mdd=dd)

# =========================================================================
print('\n' + '=' * 78)
print('1) FULL-SAMPLE N-CURVE  (net @ Rs1,00,000, vs equal-weight same universe)')
print('=' * 78)
print(f'{"N":>4} {"gross%":>8} {"net%":>8} {"bench%":>8} {"exc%":>8} {"t_exc":>7} {"MDD%":>7}')
Ns = [1,2,3,4,5,6,7,8,10,12,15,20,25,30,40,50]
curve = {}
for N in Ns:
    d, net, ben, gr = run(N)
    exc = net - ben
    sn, sb, se, sg = stats(net), stats(ben), stats(exc), stats(gr)
    curve[N] = (net, ben, exc, d)
    print(f'{N:>4} {sg["ann"]*100:8.1f} {sn["ann"]*100:8.1f} {sb["ann"]*100:8.1f} '
          f'{se["mean"]*1200:8.1f} {se["t"]:7.2f} {sn["mdd"]*100:7.1f}')
print(f'\nBenchmark (equal-weight, gross, no costs): {stats(curve[10][1])["ann"]*100:.1f}%/yr, '
      f'MDD {stats(curve[10][1])["mdd"]*100:.1f}%, n={len(curve[10][1])}')

# =========================================================================
print('\n' + '=' * 78)
print('2) N-INSTABILITY TEST  -- is the N-curve smooth or noise?')
print('=' * 78)
grid = list(range(1, 51))
annc = []; excm = []
for N in grid:
    d, net, ben, gr = run(N)
    annc.append(stats(net)['ann'] * 100); excm.append((net - ben))
annc = np.array(annc)
# roughness: mean |second difference| of the N-curve vs its own level spread
d2 = np.abs(np.diff(annc, 2))
print(f'N-curve (net ann%) N=1..50 roughness: mean|2nd diff| = {d2.mean():.2f} pp, '
      f'curve range = {annc.max()-annc.min():.1f} pp')
# split-half replication of the N-curve shape
half = len(months) // 2
c1 = []; c2 = []
for N in grid:
    d, net, ben, gr = run(N, t0=12, t1=half)
    c1.append(stats(net - ben)['mean'] * 1200)
    d, net, ben, gr = run(N, t0=half, t1=T - 1)
    c2.append(stats(net - ben)['mean'] * 1200)
c1, c2 = np.array(c1), np.array(c2)
from scipy.stats import spearmanr, pearsonr
rs = spearmanr(c1, c2); rp = pearsonr(c1, c2)
print(f'Split-half N-curve shape replication (excess ann% vs N):')
print(f'  Spearman rho = {rs.statistic:+.3f} (p={rs.pvalue:.3f})   Pearson r = {rp.statistic:+.3f}')
print(f'  best N in 1st half = {grid[int(np.argmax(c1))]}, in 2nd half = {grid[int(np.argmax(c2))]}')
# noise scale: SE of the excess mean at a typical N
se_typ = np.std(curve[10][2], ddof=1) / np.sqrt(len(curve[10][2])) * 1200
print(f'  1-sigma noise band on any single N estimate: +/- {se_typ:.1f} pp/yr '
      f'-- vs N-curve spread {annc.max()-annc.min():.1f} pp')

# =========================================================================
print('\n' + '=' * 78)
print('3) WALK-FORWARD  (24m rolling train picks N in 1..30, applied to next month)')
print('=' * 78)
cache = {N: run(N)[1] for N in range(1, 31)}
dref, _, bref, _ = run(10)
nm = len(dref); TRAIN = 24
wf = []; wb = []; wd = []; picks = []
for i in range(TRAIN, nm):
    sc = [cache[N][i - TRAIN:i].mean() for N in range(1, 31)]
    Nb = int(np.argmax(sc)) + 1
    picks.append(Nb); wf.append(cache[Nb][i]); wb.append(bref[i]); wd.append(dref[i])
wf, wb = np.array(wf), np.array(wb)
swf, swb, swe = stats(wf), stats(wb), stats(wf - wb)
print(f'OOS months n={swf["n"]}  ({wd[0]} .. {wd[-1]})')
print(f'  walk-forward momentum : {swf["ann"]*100:6.1f}%/yr  MDD {swf["mdd"]*100:6.1f}%')
print(f'  equal-weight benchmark: {swb["ann"]*100:6.1f}%/yr  MDD {swb["mdd"]*100:6.1f}%')
print(f'  EXCESS: {swe["mean"]*1200:+.2f} pp/yr   t = {swe["t"]:+.2f}   n = {swe["n"]}')
q = np.percentile(wf, [5, 25, 50, 75, 95]) * 100
print(f'  OOS monthly net return distribution: p5 {q[0]:.1f} p25 {q[1]:.1f} med {q[2]:.1f} '
      f'p75 {q[3]:.1f} p95 {q[4]:.1f}  (mean {wf.mean()*100:.2f}, sd {wf.std(ddof=1)*100:.2f})')
print(f'  months beating benchmark: {(wf>wb).sum()}/{len(wf)} = {(wf>wb).mean()*100:.0f}%')
print(f'  N chosen by walk-forward: {sorted(set(picks))}  (changes {sum(1 for a,b in zip(picks,picks[1:]) if a!=b)}x in {len(picks)} months)')
# fixed-N walk-forward comparison (no N selection at all)
for N in (5, 10, 20):
    x = cache[N][TRAIN:]; e = x - wb
    s = stats(e)
    print(f'  fixed N={N:<2} OOS excess {s["mean"]*1200:+6.2f} pp/yr  t={s["t"]:+.2f}')

# =========================================================================
print('\n' + '=' * 78)
print('4) COST SENSITIVITY BY CAPITAL (fixed N, full sample)')
print('=' * 78)
print(f'{"N":>4} {"cap":>10} {"gross%":>8} {"net%":>8} {"DPdrag%":>8} {"exc%":>8} {"t":>6}')
for N in (5, 10, 20):
    for cap in (25000.0, 100000.0, 500000.0):
        d, net, ben, gr = run(N, capital=cap)
        e = net - ben; s = stats(e)
        drag = (stats(gr)['ann'] - stats(net)['ann']) * 100
        print(f'{N:>4} {cap:>10,.0f} {stats(gr)["ann"]*100:8.1f} {stats(net)["ann"]*100:8.1f} '
              f'{drag:8.2f} {s["mean"]*1200:8.1f} {s["t"]:6.2f}')

# =========================================================================
print('\n' + '=' * 78)
print('5) SUB-PERIOD STABILITY (N=10, net @ Rs1L)')
print('=' * 78)
net, ben, exc, dts = curve[10]
yr = np.array([d.year for d in dts])
print(f'{"year":>6} {"n":>3} {"mom%":>8} {"bench%":>8} {"exc pp":>8} {"t":>6}')
for y in sorted(set(yr)):
    m = yr == y
    if m.sum() < 3: continue
    print(f'{y:>6} {m.sum():>3} {stats(net[m])["ann"]*100:8.1f} {stats(ben[m])["ann"]*100:8.1f} '
          f'{exc[m].mean()*1200:8.1f} {stats(exc[m])["t"]:6.2f}')
up = ben > 0
print(f'\nRegime split (by benchmark month sign):')
for lab, m in (('UP  ', up), ('DOWN', ~up)):
    print(f'  {lab} n={m.sum():>3}  mom {net[m].mean()*100:+6.2f}%/mo  bench {ben[m].mean()*100:+6.2f}%/mo '
          f' excess {exc[m].mean()*100:+6.2f}%/mo  t={stats(exc[m])["t"]:+.2f}')
# beta check
b, a = np.polyfit(ben, net, 1)
resid = net - (a + b * ben)
sa = a / (resid.std(ddof=1) / np.sqrt(len(resid)))
print(f'\nMarket regression: beta = {b:.2f}, alpha = {a*1200:+.2f} pp/yr, t(alpha) = {sa:+.2f}')

# =========================================================================
print('\n' + '=' * 78)
print('6) NO-LIQUIDITY-FILTER variant (what the original 26% probably was)')
print('=' * 78)
elig_bak = elig.copy()
elig = np.zeros(M.shape, bool)
for t in range(12, T - 1):
    elig[t] = VALID[t] & np.isfinite(Mv[t]) & np.isfinite(Mv[t + 1])
print('median eligible universe:', int(np.median(elig[12:T-1].sum(1))))
print(f'{"N":>4} {"gross%":>8} {"net%":>8} {"bench%":>8} {"exc%":>8} {"t_exc":>7}')
for N in (1, 2, 3, 5, 10, 20):
    d, net2, ben2, gr2 = run(N)
    s = stats(net2 - ben2)
    print(f'{N:>4} {stats(gr2)["ann"]*100:8.1f} {stats(net2)["ann"]*100:8.1f} '
          f'{stats(ben2)["ann"]*100:8.1f} {s["mean"]*1200:8.1f} {s["t"]:7.2f}')
elig = elig_bak
print('\nDONE')
