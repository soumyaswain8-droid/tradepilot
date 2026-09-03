import pandas as pd, numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression
np.seterr(all='ignore')
D='/Users/soumyaswain/Documents/tinker/projects/tradepilot/'
P=pd.read_parquet(D+'docs/research/overnight/winners_panel_own.parquet')
F=['ret1','ret5','ret21','ret63','vol20','turn20','turn_ratio','pos52','vs_sma20']
P=P.dropna(subset=F); dates=np.sort(P.date.unique()); split=dates[int(len(dates)*.65)]
def zs(df):
    o=df[F].copy()
    for f in F:
        m=df.groupby('date')[f].transform('mean'); s=df.groupby('date')[f].transform('std')
        o[f]=((df[f]-m)/(s+1e-12)).clip(-5,5)
    return o.values
tr=P[P.date<split]; ho=P[P.date>=split]
clf=LogisticRegression(max_iter=400).fit(zs(tr),tr.win.values)
d=pd.DataFrame({'date':ho.date.values,'s':clf.decision_function(zs(ho)),'r':ho.ret_today.values,'t20':ho.turn20.values})
mkt=ho.groupby('date').ret_today.mean()
print('=== TURNOVER FLOOR SENSITIVITY (predicted top-50 within eligible set, holdout) ===')
print('%-16s %7s %10s %9s %9s %9s'%('floor(turn units)','names/d','gross%/d','t','net_MIS%','t_net_mn'))
for fl in [0,10,50,100,300,1000,3000]:
    sub=d[10**d.t20>=fl].copy()
    if len(sub)<5000: continue
    sub['rk']=sub.groupby('date')['s'].rank(ascending=False,method='first')
    tp=sub[sub.rk<=50]; dr=tp.groupby('date')['r'].mean()
    nm=dr-mkt.reindex(dr.index).values-0.00107
    print('%-16d %7.0f %+10.4f %9.2f %+9.4f %9.2f'%(fl,sub.groupby('date').size().mean(),100*dr.mean(),
        stats.ttest_1samp(dr,0).statistic,100*(dr.mean()-0.00107),stats.ttest_1samp(nm,0).statistic))
print('\n=== SHORT THE PREDICTED BASKET? (holdout, full model, no floor) ===')
d['rk']=d.groupby('date')['s'].rank(ascending=False,method='first'); tp=d[d.rk<=50]
dr=tp.groupby('date')['r'].mean(); sh=-dr-0.00107
print('short net MIS = %+.4f%%/d  t=%.2f  (mean +%.4f but median %+.4f -> short bleeds on tails)'%(100*sh.mean(),stats.ttest_1samp(sh,0).statistic,100*dr.mean(),100*tp.r.median()))
