import pandas as pd, numpy as np, os
from scipy import stats
np.seterr(all='ignore')
D='/Users/soumyaswain/Documents/tinker/projects/tradepilot/'
p_shared = D+'docs/research/overnight/winners_panel.parquet'
p_own    = D+'docs/research/overnight/winners_panel_own.parquet'
path = p_shared if os.path.exists(p_shared) and os.path.getsize(p_shared)>1e6 else p_own
print('PANEL:', os.path.basename(path))
P = pd.read_parquet(path)
FEATS = ['ret1','ret5','ret21','ret63','vol20','turn20','turn_ratio','pos52','vs_sma20']
P = P.dropna(subset=FEATS+['win','ret_today'])
dates = np.sort(P['date'].unique())
print('rows %d  days %d  syms %d  base %.4f' % (len(P), len(dates), P['sym'].nunique(), P['win'].mean()))

# ---------- 1+2. winners vs non-winners, naive vs date-clustered ----------
print('\n=== WINNER vs NON-WINNER (prior-day features) ===')
print('%-11s %10s %10s %8s %9s %9s %9s' % ('feature','win_mean','non_mean','d/sd','t_naive','t_clust','days+'))
rowsout=[]
g = P.groupby('date')
for f in FEATS:
    w = P.loc[P.win==1, f].values; n = P.loc[P.win==0, f].values
    sd = P[f].std()
    tn = stats.ttest_ind(w, n, equal_var=False).statistic
    # date-clustered: daily cross-sectional difference of z-scored feature
    z = P.groupby('date')[f].transform(lambda s: (s - s.mean())/(s.std()+1e-12))
    dd = z.groupby(P['date']).apply(lambda s: 0.0)  # placeholder
    tmp = pd.DataFrame({'d':P['date'],'z':z,'w':P['win']})
    daily = tmp.groupby('d').apply(lambda s: s.z[s.w==1].mean() - s.z[s.w==0].mean())
    tc = stats.ttest_1samp(daily.dropna(), 0).statistic
    frac = (daily>0).mean()
    print('%-11s %10.4f %10.4f %8.3f %9.1f %9.2f %8.1f%%' % (f, w.mean(), n.mean(), (w.mean()-n.mean())/sd, tn, tc, 100*frac))
    rowsout.append((f, w.mean(), n.mean(), (w.mean()-n.mean())/sd, tn, tc, 100*frac, daily.mean()))
pd.DataFrame(rowsout, columns=['feat','win','non','dsd','t_naive','t_clust','days_pos','daily_z']).to_csv(D+'docs/research/overnight/_precursor_stats.csv', index=False)

# ---------- 3. predictive model, train/holdout by DATE ----------
split = dates[int(len(dates)*0.65)]
tr = P[P.date < split]; ho = P[P.date >= split]
print('\n=== MODEL ===\ntrain %s..%s (%d days)  holdout %s..%s (%d days)' %
      (str(dates[0])[:10], str(split)[:10], tr.date.nunique(), str(split)[:10], str(dates[-1])[:10], ho.date.nunique()))

# cross-sectional z-score within date (rank-free, keeps scale comparable)
def zs(df):
    out = df[FEATS].copy()
    for f in FEATS:
        m = df.groupby('date')[f].transform('mean'); s = df.groupby('date')[f].transform('std')
        out[f] = ((df[f]-m)/(s+1e-12)).clip(-5,5)
    return out.values
Xtr = zs(tr); ytr = tr['win'].values
Xho = zs(ho); yho = ho['win'].values

from sklearn.linear_model import LogisticRegression
clf = LogisticRegression(max_iter=400, C=1.0, solver='lbfgs')
clf.fit(Xtr, ytr)
print('coefs:', dict(zip(FEATS, np.round(clf.coef_[0],3))))
for name, Xs, ys, sub in [('TRAIN',Xtr,ytr,tr), ('HOLDOUT',Xho,yho,ho)]:
    s = clf.decision_function(Xs)
    d = pd.DataFrame({'date':sub['date'].values,'s':s,'w':ys,'r':sub['ret_today'].values,
                      'turn20':sub['turn20'].values})
    d['rk'] = d.groupby('date')['s'].rank(ascending=False, method='first')
    top = d[d.rk<=50]
    base = ys.mean()
    hit = top['w'].mean()
    # per-day hit rate -> clustered t
    dh = top.groupby('date')['w'].mean()
    t_hit = stats.ttest_1samp(dh-base, 0).statistic
    dr = top.groupby('date')['r'].mean()
    print('%-8s base=%.4f  top50_hit=%.4f  lift=%.2fx  t_clust=%.2f | ret/day gross=%+.4f%% t=%.2f' %
          (name, base, hit, hit/base, t_hit, 100*dr.mean(), stats.ttest_1samp(dr,0).statistic))
    if name=='HOLDOUT':
        HO = d; DR = dr
        # AUC
        from sklearn.metrics import roc_auc_score
        print('         holdout AUC = %.4f' % roc_auc_score(ys, s))

# ---------- 4. net returns of predicted top-50 basket ----------
print('\n=== NET RETURNS, holdout predicted-top-50 (equal weight, daily) ===')
mkt = P.groupby('date')['ret_today'].mean()
for cost, lbl in [(0.00107,'intraday 0.107%'), (0.0024,'delivery 0.24%')]:
    net = DR - cost
    n = len(net); t = stats.ttest_1samp(net,0).statistic
    cum = (1+net).cumprod(); dd = (cum/cum.cummax()-1).min()
    # market-neutral version
    nm = DR - mkt.reindex(DR.index).values - cost
    print('%-18s n=%d  net/day=%+.4f%%  t=%.2f  ann=%+.1f%%  maxDD=%.1f%% | mkt-neutral net=%+.4f%% t=%.2f' %
          (lbl, n, 100*net.mean(), t, 100*((1+net.mean())**252-1), 100*dd, 100*np.mean(nm), stats.ttest_1samp(nm,0).statistic))
print('market avg ret/day = %+.4f%%' % (100*mkt.reindex(DR.index).mean()))

# ---------- 5. liquidity segmentation ----------
print('\n=== BY LIQUIDITY (turn20 tercile, computed within date) ===')
P['liq'] = P.groupby('date')['turn20'].transform(lambda s: pd.qcut(s, 3, labels=['low','mid','high'], duplicates='drop'))
ho2 = P[P.date>=split].copy()
for lv in ['low','mid','high']:
    sub = ho2[ho2.liq==lv]
    if len(sub)<1000: continue
    Xs = zs(sub); ys = sub['win'].values
    s = clf.decision_function(Xs)
    d = pd.DataFrame({'date':sub['date'].values,'s':s,'w':ys,'r':sub['ret_today'].values})
    d['rk'] = d.groupby('date')['s'].rank(ascending=False, method='first')
    top = d[d.rk<=17]
    base = ys.mean(); hit = top['w'].mean()
    dh = top.groupby('date')['w'].mean(); dr = top.groupby('date')['r'].mean()
    print('%-5s n=%7d  win_base=%.4f  top_hit=%.4f  lift=%.2fx  t=%.2f | gross/day=%+.4f%%  net_intraday=%+.4f%% t=%.2f' %
          (lv, len(sub), base, hit, hit/base, stats.ttest_1samp(dh-base,0).statistic,
           100*dr.mean(), 100*(dr.mean()-0.00107), stats.ttest_1samp(dr-0.00107,0).statistic))
# where do winners actually live?
print('\nwinner share by liquidity tercile:', P.groupby('liq')['win'].mean().round(4).to_dict())
print('mean ret_today of actual winners: %.3f%%' % (100*P.loc[P.win==1,'ret_today'].mean()))
