"""
_winner_anatomy2.py -- the three follow-ups the disk failure killed.

Rebuilds the winner-anatomy panel IN MEMORY (winners_panel_own.parquet was lost
with the volume) using the exact logic of _precursors_build.py, then runs:

  T1. Newey-West / HAC correction of the BREAKOUT t-statistics (h=1,5,10,21)
  T2. Holdout split-half + mom_12_1 control (Fama-MacBeth) for BREAKOUT
  T3. Stop-loss truncated-payoff test
  T4. BREAKOUT decomposition by turnover bucket

Data notes carried forward:
  - sf_turn is in Rs LAKH (tradeable bar = 100.0 == Rs 1 crore)
  - sf_ret is WINSORIZED at +/-50% (fine here; not for extreme-value work)

Writes NO intermediate files. Prints everything.
"""
import numpy as np, pandas as pd, sys
from scipy import stats

np.seterr(all='ignore')
pd.options.mode.chained_assignment = None
B = '/Users/soumyaswain/Documents/tinker/projects/tradepilot/'

# ------------------------------------------------------------------ load
ret = pd.read_parquet(B + 'quant/data/sf_ret.parquet')
turn = pd.read_parquet(B + 'quant/data/sf_turn.parquet')
turn = turn.reindex(index=ret.index, columns=ret.columns)
dates, syms = ret.index, ret.columns
R = ret.values.astype('float32'); T = turn.values.astype('float32')
valid = ~np.isnan(R)
Rz = np.nan_to_num(R, nan=0.0)
px = np.cumprod(1.0 + Rz, axis=0)
lpx = np.log(np.maximum(px, 1e-12))
print(f'[load] ret {R.shape} {dates.min().date()}..{dates.max().date()}', flush=True)


# ------------------------------------------------- rolling helpers (verbatim)
def rsum(A, w):
    C = np.cumsum(np.vstack([np.zeros((1, A.shape[1])), A.astype(np.float64)]), axis=0)
    out = np.full(A.shape, np.nan); out[w - 1:] = C[w:] - C[:-w]; return out


def rstd(A, w):
    m1 = rsum(A, w) / w; m2 = rsum(A * A, w) / w
    return np.sqrt(np.maximum(m2 - m1 * m1, 0))


def rmax(A, w): return pd.DataFrame(A).rolling(w, min_periods=w).max().values
def rmin(A, w): return pd.DataFrame(A).rolling(w, min_periods=w).min().values


# ------------------------------------------------- features (verbatim + mom_12_1)
f = {}
f['ret1'] = Rz.copy()
f['ret5'] = rsum(Rz, 5)
f['ret21'] = rsum(Rz, 21)
f['ret63'] = rsum(Rz, 63)
f['vol20'] = rstd(Rz, 20)
Tz = np.nan_to_num(T, nan=0.0)
turn20 = rsum(Tz, 20) / 20.0
f['turn20'] = np.log10(np.maximum(turn20, 1.0))
f['turn_ratio'] = Tz / np.maximum(turn20, 1e-9)
hi = rmax(lpx, 252); lo = rmin(lpx, 252)
f['pos52'] = (lpx - lo) / np.maximum(hi - lo, 1e-9)
sma20 = rsum(lpx, 20) / 20.0
f['vs_sma20'] = lpx - sma20

# mom_12_1: 12-month return skipping the most recent month (log-price form)
# through day i inclusive => lpx[i-21] - lpx[i-252]
mom = np.full(R.shape, np.nan)
mom[252:] = lpx[231:-21] - lpx[:-252]
f['mom_12_1'] = mom

FEATS = ['ret1', 'ret5', 'ret21', 'ret63', 'vol20', 'turn20', 'turn_ratio',
         'pos52', 'vs_sma20']
ALLF = FEATS + ['mom_12_1']
X = {k: np.vstack([np.full((1, R.shape[1]), np.nan), f[k][:-1]]) for k in ALLF}

# ------------------------------------------------- panel rows (verbatim)
tradeable_raw = valid & (T > 0) & ~np.isnan(T)
feat_ok = np.ones_like(valid)
for k in FEATS:            # NOTE: mom_12_1 deliberately NOT in the gate,
    feat_ok &= ~np.isnan(X[k])   # so row counts match the original panel
prev_valid = np.vstack([np.zeros((1, R.shape[1]), bool), valid[:-1]])
use = tradeable_raw & feat_ok & prev_valid

RT = np.where(valid, R, np.nan)
win = np.zeros(R.shape, bool)
for i in range(R.shape[0]):
    idx = np.where(use[i])[0]
    if len(idx) < 100: continue
    order = np.argsort(-RT[i, idx])
    win[i, idx[order[:50]]] = True

di_all, si_all = np.where(use)
P = pd.DataFrame({'date': dates.values[di_all], 'sym': syms.values[si_all],
                  'di': di_all, 'si': si_all,
                  'win': win[use].astype('int8')})
for k in ALLF: P[k] = X[k][use].astype('float32')
P = P[P.groupby('date')['win'].transform('sum') == 50].reset_index(drop=True)
print(f'[panel] rows {len(P):,} days {P.date.nunique()} base {P.win.mean():.4f}', flush=True)

# ------------------------------------------------- forward returns (verbatim)
lr = np.log1p(np.clip(R, -0.9, None))
lrz = np.nan_to_num(lr, nan=0.0)
cum = np.vstack([np.zeros((1, R.shape[1])), np.cumsum(lrz.astype(np.float64), axis=0)])
validc = np.vstack([np.zeros((1, R.shape[1])), np.cumsum(valid.astype(np.float64), axis=0)])


def fwd(k):
    """return over days i .. i+k-1 (inclusive of the event day), NaN unless all k traded"""
    out = np.full(R.shape, np.nan)
    n = R.shape[0]
    e = n - k + 1
    out[:e] = np.expm1(cum[k:k + e] - cum[:e])
    cnt = np.full(R.shape, 0.0); cnt[:e] = validc[k:k + e] - validc[:e]
    return np.where(cnt >= k, out, np.nan)


F = {1: np.where(valid, R, np.nan).astype(float), 5: fwd(5), 10: fwd(10), 21: fwd(21)}

# tradeable mask: 20d MEDIAN turnover >= Rs 1 crore (turn is in LAKH)
t20 = turn.rolling(20, min_periods=15).median().values
trad = t20 >= 100.0

MKT = {k: np.nanmean(np.where(trad, F[k], np.nan), axis=1) for k in F}

di = P.di.values; si = P.si.values
for k in F:
    P[f'f{k}'] = F[k][di, si]
    P[f'x{k}'] = P[f'f{k}'].values - MKT[k][di]
P['tradeable'] = trad[di, si]
print(f'[panel] tradeable frac {P.tradeable.mean():.3f}', flush=True)


# ------------------------------------------------- classification (verbatim)
def classify(d):
    t = pd.Series('OTHER', index=d.index, dtype=object)
    t[(d.ret21.abs() < 0.05) & (d.ret5.abs() < 0.03) & (d.vol20 < 0.025)] = 'FROM-NOWHERE'
    t[(d.ret21 >= 0.20) & (d.pos52 < 0.95)] = 'CONTINUATION'
    t[(d.pos52 <= 0.10) & (d.ret21 <= -0.15)] = 'REVERSAL'
    t[d.pos52 >= 0.95] = 'BREAKOUT'
    return t


P['type'] = classify(P)
SPLIT = pd.Timestamp('2025-01-20')
P['period'] = np.where(P.date < SPLIT, 'train', 'holdout')
sub = P[P.tradeable].copy()
print('[panel] type counts (tradeable):'); print(sub.type.value_counts().to_string(), flush=True)


# ------------------------------------------------- HAC machinery
def nw_var(g, L):
    """Newey-West long-run variance of the mean of series g, Bartlett kernel, lag L."""
    g = np.asarray(g, float); n = len(g); e = g - g.mean()
    s = (e @ e) / n
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1.0)
        s += 2.0 * w * (e[l:] @ e[:-l]) / n
    return max(s, 1e-18)


def auto_lag(n):
    """Newey-West (1994) rule-of-thumb bandwidth."""
    return int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def tstats(g, h):
    """naive (iid) t and HAC t at lag h, h-1 and auto."""
    g = np.asarray(pd.Series(g).dropna(), float); n = len(g)
    if n < 20: return dict(n=n)
    m = g.mean()
    t_naive = m / (g.std(ddof=1) / np.sqrt(n))
    out = dict(n=n, mean=m, t_naive=t_naive)
    for tag, L in [('h', h), ('h-1', max(h - 1, 0)), ('auto', auto_lag(n))]:
        out[f't_{tag}'] = m / np.sqrt(nw_var(g, L) / n)
        out[f'L_{tag}'] = L
    return out


def dseries(d, col):
    return d.groupby('date')[col].mean().dropna()


def show(label, r):
    if 'mean' not in r: print(f'  {label:<34} n={r.get("n")} -- too few'); return
    print(f'  {label:<34} nd={r["n"]:>4}  mean={r["mean"]*100:+.3f}%  '
          f't_naive={r["t_naive"]:+.2f}   t_NW(L={r["L_h"]})={r["t_h"]:+.2f}   '
          f't_NW(L={r["L_h-1"]})={r["t_h-1"]:+.2f}   t_NW(auto L={r["L_auto"]})={r["t_auto"]:+.2f}   '
          f'infl={abs(r["t_naive"])/max(abs(r["t_h"]),1e-9):.2f}x', flush=True)


# ================================================== T0. reproduction check
print('\n' + '=' * 100)
print('T0. REPRODUCTION CHECK -- must match winner-anatomy.md before anything else is trusted')
print('=' * 100)
for typ in ['BREAKOUT', 'REVERSAL', 'CONTINUATION']:
    for per in ['train', 'holdout']:
        d = sub[(sub.period == per) & (sub.type == typ)]
        n1 = d.dropna(subset=['x1'])
        line = f'  {typ:<13} {per:<8} n(h=1)={len(n1):>7,}'
        for h in [1, 5, 10, 21]:
            g = dseries(d.dropna(subset=[f'x{h}']), f'x{h}')
            line += f'   h{h}: {g.mean()*100:+.3f}% t={g.mean()/(g.std(ddof=1)/np.sqrt(len(g))):+.2f}'
        print(line, flush=True)

# ================================================== T1. HAC correction
print('\n' + '=' * 100)
print('T1. NEWEY-WEST / HAC CORRECTION -- BREAKOUT, holdout, market-neutral')
print('=' * 100)
hold_bo = sub[(sub.period == 'holdout') & (sub.type == 'BREAKOUT')]
for h in [1, 5, 10, 21]:
    g = dseries(hold_bo.dropna(subset=[f'x{h}']), f'x{h}')
    show(f'BREAKOUT holdout MN h={h}', tstats(g, h))
print('  -- control: same for RAW (not market-neutral) --')
for h in [1, 21]:
    g = dseries(hold_bo.dropna(subset=[f'f{h}']), f'f{h}')
    show(f'BREAKOUT holdout RAW h={h}', tstats(g, h))
print('  -- control: TRAIN period (the zero-signal side) --')
tr_bo = sub[(sub.period == 'train') & (sub.type == 'BREAKOUT')]
for h in [5, 21]:
    g = dseries(tr_bo.dropna(subset=[f'x{h}']), f'x{h}')
    show(f'BREAKOUT train MN h={h}', tstats(g, h))
print('  -- control: REVERSAL holdout (the significant-negative result) --')
rv = sub[(sub.period == 'holdout') & (sub.type == 'REVERSAL')]
for h in [1, 5, 21]:
    g = dseries(rv.dropna(subset=[f'x{h}']), f'x{h}')
    show(f'REVERSAL holdout MN h={h}', tstats(g, h))

# ================================================== T2a. holdout split-half
print('\n' + '=' * 100)
print('T2a. HOLDOUT SPLIT-HALF -- does BREAKOUT show in both halves?')
print('=' * 100)
hd = np.sort(hold_bo.date.unique())
mid = hd[len(hd) // 2]
print(f'  holdout spans {pd.Timestamp(hd[0]).date()} .. {pd.Timestamp(hd[-1]).date()}, '
      f'{len(hd)} sessions, midpoint {pd.Timestamp(mid).date()}', flush=True)
for h in [1, 5, 10, 21]:
    for tag, m in [('H1', hold_bo.date < mid), ('H2', hold_bo.date >= mid)]:
        g = dseries(hold_bo[m].dropna(subset=[f'x{h}']), f'x{h}')
        show(f'BREAKOUT {tag} h={h}', tstats(g, h))

print('\n  -- year by year (calendar), BREAKOUT MN, full sample --')
allbo = sub[sub.type == 'BREAKOUT'].copy()
allbo['yr'] = pd.DatetimeIndex(allbo.date).year
for yr, d in allbo.groupby('yr'):
    line = f'  {yr}  n={len(d):>7,}'
    for h in [5, 10, 21]:
        g = dseries(d.dropna(subset=[f'x{h}']), f'x{h}')
        r = tstats(g, h)
        line += (f'   h{h}: {r["mean"]*100:+.3f}% t={r["t_naive"]:+.2f}/NW{r["t_h"]:+.2f}'
                 if 'mean' in r else f'   h{h}: --')
    print(line, flush=True)

# ================================================== T2b. mom_12_1 control
print('\n' + '=' * 100)
print('T2b. FAMA-MACBETH with mom_12_1 CONTROL -- what survives?')
print('=' * 100)
fm = sub[(sub.period == 'holdout')].dropna(subset=['mom_12_1']).copy()
fm['bo'] = (fm.type == 'BREAKOUT').astype(float)
print(f'  cross-section: {len(fm):,} rows, mom_12_1 available; '
      f'corr(bo, mom_12_1) = {np.corrcoef(fm.bo, fm.mom_12_1)[0,1]:+.3f}', flush=True)


def fmb(df, h, cols):
    """daily cross-sectional OLS of x_h on [1] + cols; return dict col -> daily coef series"""
    d = df.dropna(subset=[f'x{h}'] + cols)
    out = {c: [] for c in cols}; ds = []
    for dt, gg in d.groupby('date'):
        if len(gg) < 30: continue
        A = np.column_stack([np.ones(len(gg))] + [gg[c].values.astype(float) for c in cols])
        y = gg[f'x{h}'].values.astype(float)
        try:
            b = np.linalg.lstsq(A, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        for i, c in enumerate(cols): out[c].append(b[i + 1])
        ds.append(dt)
    return {c: pd.Series(v, index=ds) for c, v in out.items()}


for h in [5, 10, 21]:
    r1 = fmb(fm, h, ['bo'])
    show(f'h={h} BO dummy (no control)', tstats(r1['bo'], h))
    r2 = fmb(fm, h, ['bo', 'mom_12_1'])
    show(f'h={h} BO dummy | mom_12_1', tstats(r2['bo'], h))
    show(f'h={h} mom_12_1 slope', tstats(r2['mom_12_1'], h))
    r3 = fmb(fm, h, ['bo', 'mom_12_1', 'vol20', 'turn20'])
    show(f'h={h} BO | mom,vol,turn', tstats(r3['bo'], h))

# ================================================== T3. stop-loss truncation
print('\n' + '=' * 100)
print('T3. STOP-LOSS TRUNCATED PAYOFF -- does cutting the down-tail monetise the up-tail?')
print('=' * 100)


def stopped(h, s):
    """exit at close of first day j<=h where cum return from entry <= -s, else hold to h.
       cum over days i..i+j-1 (entry at close of i-1 in feature time == our f-convention)."""
    n = R.shape[0]
    e = n - h + 1
    out = np.full(R.shape, np.nan); alive = np.zeros(R.shape, bool); alive[:e] = True
    final = np.full(R.shape, np.nan)
    for j in range(1, h + 1):
        c = np.full(R.shape, np.nan)
        c[:e] = np.expm1(cum[j:j + e] - cum[:e])
        hit = alive & (c <= -s) & ~np.isnan(c)
        final = np.where(hit, c, final)
        alive = alive & ~hit
    still = alive & ~np.isnan(F[h])
    final = np.where(still, F[h], final)
    return np.where(np.isnan(F[h]), np.nan, final)   # keep the same valid set


for h in [10, 21]:
    print(f'  --- horizon h={h} (holdout, RAW returns, gross) ---')
    base = {}
    for typ in ['BREAKOUT', 'REVERSAL', 'CONTINUATION', 'ALL']:
        d = sub[sub.period == 'holdout']
        if typ != 'ALL': d = d[d.type == typ]
        d = d.dropna(subset=[f'f{h}'])
        base[typ] = (d[f'f{h}'].mean(), stats.skew(d[f'f{h}'].values), len(d))
        print(f'    {typ:<13} no stop      mean={base[typ][0]*100:+.3f}%  '
              f'skew={base[typ][1]:+.2f}  n={base[typ][2]:,}', flush=True)
    for s in [0.05, 0.10, 0.15]:
        S = stopped(h, s)
        col = f'st{h}_{int(s*100)}'
        sub[col] = S[sub.di.values, sub.si.values]
        for typ in ['BREAKOUT', 'REVERSAL', 'CONTINUATION', 'ALL']:
            d = sub[sub.period == 'holdout']
            if typ != 'ALL': d = d[d.type == typ]
            d = d.dropna(subset=[col, f'f{h}'])
            m = d[col].mean(); b = d[f'f{h}'].mean()
            g = d.groupby('date')[col].mean().dropna()
            r = tstats(g, h)
            print(f'    {typ:<13} stop -{int(s*100):>2}%    mean={m*100:+.3f}%  '
                  f'(delta {(m-b)*100:+.3f}%)  skew={stats.skew(d[col].values):+.2f}  '
                  f'hit={(d[col]<=-s+1e-9).mean()*100:.1f}%  t_NW={r.get("t_h",np.nan):+.2f}', flush=True)
        sub.drop(columns=[col], inplace=True)

# ================================================== T4. turnover buckets
print('\n' + '=' * 100)
print('T4. BREAKOUT BY TURNOVER BUCKET (turn20 = log10 avg 20d turnover in LAKH)')
print('=' * 100)
bo = sub[(sub.type == 'BREAKOUT') & (sub.period == 'holdout')].copy()
qs = bo.turn20.quantile([0, 1 / 3, 2 / 3, 1.0]).values
print(f'  turn20 terciles (log10 lakh): {np.round(qs,2)}  '
      f'== Rs {np.round(10**qs/100,2)} crore/day', flush=True)
bo['tb'] = pd.cut(bo.turn20, bins=qs, labels=['LOW', 'MID', 'HIGH'], include_lowest=True)
for h in [5, 21]:
    print(f'  --- h={h} ---')
    for tb, d in bo.groupby('tb', observed=True):
        g = dseries(d.dropna(subset=[f'x{h}']), f'x{h}')
        r = tstats(g, h); r['nrows'] = len(d)
        show(f'{tb} (n={len(d):,})', r)
    # with momentum control inside each bucket
    for tb, d in bo.groupby('tb', observed=True):
        dd = sub[(sub.period == 'holdout')].copy()
        dd['bo'] = 0.0
        dd.loc[d.index, 'bo'] = 1.0
        dd = dd.dropna(subset=['mom_12_1'])
        rr = fmb(dd, h, ['bo', 'mom_12_1'])
        show(f'{tb} | mom_12_1', tstats(rr['bo'], h))

print('\n[done]', flush=True)
