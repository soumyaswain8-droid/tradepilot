import pandas as pd, numpy as np, os
from scipy import stats
from sklearn.linear_model import LogisticRegression
np.seterr(all='ignore')
D='/Users/soumyaswain/Documents/tinker/projects/tradepilot/'
P = pd.read_parquet(D+'docs/research/overnight/winners_panel_own.parquet')
FEATS=['ret1','ret5','ret21','ret63','vol20','turn20','turn_ratio','pos52','vs_sma20']
P=P.dropna(subset=FEATS)
dates=np.sort(P['date'].unique()); split=dates[int(len(dates)*0.65)]
# loser label
P['lose'] = P.groupby('date')['ret_today'].rank(ascending=True, method='first')<=50
print('turnover units: raw turn20 is log10. median 10^turn20 = %.0f ; deciles:' % (10**P.turn20.median()))
print((10**P.groupby(pd.qcut(P.turn20,10,labels=False,duplicates='drop')).turn20.median()).round(0).to_dict())
print('winner mean ret %.2f%%  loser mean ret %.2f%%' % (100*P.loc[P.win==1,'ret_today'].mean(), 100*P.loc[P.lose,'ret_today'].mean()))

def zs(df):
    o=df[FEATS].copy()
    for f in FEATS:
        m=df.groupby('date')[f].transform('mean'); s=df.groupby('date')[f].transform('std')
        o[f]=((df[f]-m)/(s+1e-12)).clip(-5,5)
    return o.values
tr=P[P.date<split]; ho=P[P.date>=split]

def report(tag, cols):
    clf=LogisticRegression(max_iter=400).fit(zs(tr)[:,[FEATS.index(c) for c in cols]], tr.win.values)
    s=clf.decision_function(zs(ho)[:,[FEATS.index(c) for c in cols]])
    d=pd.DataFrame({'date':ho.date.values,'s':s,'w':ho.win.values,'l':ho.lose.values,'r':ho.ret_today.values})
    d['rk']=d.groupby('date')['s'].rank(ascending=False,method='first'); top=d[d.rk<=50]
    dr=top.groupby('date')['r'].mean()
    print('%-24s win_hit=%.4f (%.2fx)  LOSE_hit=%.4f (%.2fx)  gross=%+.4f%% t=%.2f  median_ret=%+.3f%%'
          %(tag, top.w.mean(), top.w.mean()/ho.win.mean(), top.l.mean(), top.l.mean()/ho.lose.mean(),
            100*dr.mean(), stats.ttest_1samp(dr,0).statistic, 100*top.r.median()))
    return dr
print('\n=== IS IT JUST VOLATILITY? (holdout, predicted top-50) ===')
report('full 9-feature model', FEATS)
report('vol20 ONLY', ['vol20'])
report('momentum only (ret1/5/21/63)', ['ret1','ret5','ret21','ret63'])
report('no vol20', [c for c in FEATS if c!='vol20'])

print('\n=== SYMMETRY: return distribution of predicted top-50 (holdout, full model) ===')
clf=LogisticRegression(max_iter=400).fit(zs(tr),tr.win.values)
s=clf.decision_function(zs(ho))
d=pd.DataFrame({'date':ho.date.values,'s':s,'w':ho.win.values,'l':ho.lose.values,'r':ho.ret_today.values,'turn20':ho.turn20.values})
d['rk']=d.groupby('date')['s'].rank(ascending=False,method='first'); top=d[d.rk<=50]
print('n=%d  mean=%+.4f%% median=%+.4f%%  P(up)=%.3f  P(>+5%%)=%.3f P(<-5%%)=%.3f  skew=%.2f'
      %(len(top),100*top.r.mean(),100*top.r.median(),(top.r>0).mean(),(top.r>0.05).mean(),(top.r<-0.05).mean(),top.r.skew()))
rest=d[d.rk>50]
print('rest of universe: mean=%+.4f%% median=%+.4f%% P(up)=%.3f'%(100*rest.r.mean(),100*rest.r.median(),(rest.r>0).mean()))

print('\n=== STABILITY of low-liquidity basket (holdout split in halves) ===')
d['liqt']=pd.qcut(d.turn20,3,labels=['low','mid','high'])
hd=np.sort(d.date.unique()); mid=hd[len(hd)//2]
for lv in ['low','mid','high']:
    sub=d[d.liqt==lv].copy(); sub['rk2']=sub.groupby('date')['s'].rank(ascending=False,method='first')
    tp=sub[sub.rk2<=17]; dr=tp.groupby('date')['r'].mean()
    h1=dr[dr.index<mid]; h2=dr[dr.index>=mid]
    print('%-5s all: %+.4f%% t=%.2f | H1 %+.4f%% t=%.2f | H2 %+.4f%% t=%.2f | net_intraday all %+.4f%%'
          %(lv,100*dr.mean(),stats.ttest_1samp(dr,0).statistic,100*h1.mean(),stats.ttest_1samp(h1,0).statistic,
            100*h2.mean(),stats.ttest_1samp(h2,0).statistic,100*(dr.mean()-0.00107)))
    print('      median turnover in tercile = %.0f (units of sf_turn); P(|ret|>=9.5%%)=%.3f'%(10**sub.turn20.median(),(sub.r.abs()>=0.095).mean()))
