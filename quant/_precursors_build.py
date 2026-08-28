import pandas as pd, numpy as np, os
np.seterr(all='ignore')
D='/Users/soumyaswain/Documents/tinker/projects/tradepilot/'
r = pd.read_parquet(D+'quant/data/sf_ret.parquet')
t = pd.read_parquet(D+'quant/data/sf_turn.parquet')
t = t.reindex(index=r.index, columns=r.columns)
dates = r.index; syms = r.columns
R = r.values.astype('float32'); T = t.values.astype('float32')
valid = ~np.isnan(R)                      # traded that day
Rz = np.nan_to_num(R, nan=0.0)
px = np.cumprod(1.0+Rz, axis=0)           # synthetic price
lpx = np.log(np.maximum(px,1e-12))

def rsum(A,w):
    C = np.cumsum(np.vstack([np.zeros((1,A.shape[1]),dtype=np.float64),A.astype(np.float64)]),axis=0)
    out = np.full(A.shape, np.nan)
    out[w-1:] = C[w:] - C[:-w]
    return out
def rstd(A,w):
    m1 = rsum(A,w)/w; m2 = rsum(A*A,w)/w
    return np.sqrt(np.maximum(m2-m1*m1,0))
def rmax(A,w):
    return pd.DataFrame(A).rolling(w,min_periods=w).max().values
def rmin(A,w):
    return pd.DataFrame(A).rolling(w,min_periods=w).min().values

# features computed THROUGH day i (inclusive), later shifted by 1
f = {}
f['ret1']  = Rz.copy()
f['ret5']  = rsum(Rz,5)
f['ret21'] = rsum(Rz,21)
f['ret63'] = rsum(Rz,63)
f['vol20'] = rstd(Rz,20)
Tz = np.nan_to_num(T, nan=0.0)
turn20 = rsum(Tz,20)/20.0
f['turn20'] = np.log10(np.maximum(turn20,1.0))
f['turn_ratio'] = Tz/np.maximum(turn20,1e-9)
hi = rmax(lpx,252); lo = rmin(lpx,252)
f['pos52'] = (lpx-lo)/np.maximum(hi-lo,1e-9)
sma20 = rsum(lpx,20)/20.0
f['vs_sma20'] = lpx - sma20

FEATS = ['ret1','ret5','ret21','ret63','vol20','turn20','turn_ratio','pos52','vs_sma20']
# shift down by 1 => observable at previous close
X = {k: np.vstack([np.full((1,R.shape[1]),np.nan), f[k][:-1]]) for k in FEATS}

# label: top-50 gainer today among traded names with real turnover
tradeable = valid & (T>0) & ~np.isnan(T)
feat_ok = np.ones_like(valid)
for k in FEATS: feat_ok &= ~np.isnan(X[k])
# also require the stock traded yesterday
prev_valid = np.vstack([np.zeros((1,R.shape[1]),bool), valid[:-1]])
use = tradeable & feat_ok & prev_valid

RT = np.where(valid, R, np.nan)
win = np.zeros(R.shape, bool)
for i in range(R.shape[0]):
    idx = np.where(use[i])[0]
    if len(idx) < 100: continue
    v = RT[i, idx]
    order = np.argsort(-v)
    win[i, idx[order[:50]]] = True

rows = np.where(use)
di = rows[0]; si = rows[1]
out = {'date': dates.values[di], 'sym': syms.values[si],
       'win': win[use].astype('int8'), 'ret_today': RT[use].astype('float32')}
for k in FEATS: out[k] = X[k][use].astype('float32')
P = pd.DataFrame(out)
P = P[P.groupby('date')['win'].transform('sum')==50]
P.to_parquet(D+'docs/research/overnight/winners_panel_own.parquet', index=False)
print('rows', len(P), 'days', P['date'].nunique(), 'base rate', P['win'].mean())
