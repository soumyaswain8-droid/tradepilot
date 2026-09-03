import pandas as pd, numpy as np, json, sys
from scipy import stats
pd.options.mode.chained_assignment=None
B='/Users/soumyaswain/Documents/tinker/projects/tradepilot/'
ret=pd.read_parquet(B+'quant/data/sf_ret.parquet')
turn=pd.read_parquet(B+'quant/data/sf_turn.parquet')
p=pd.read_parquet(B+'docs/research/overnight/winners_panel_own.parquet')
print('panel',p.shape,'dates',p.date.min(),p.date.max())

# ---------- forward returns from sf_ret (log-safe compounding) ----------
lr=np.log1p(ret.clip(-0.9,None))
dates=ret.index
di={d:i for i,d in enumerate(dates)}
def fwd(k):
    c=lr.fillna(0.0).cumsum()
    valid=ret.notna().rolling(k).sum().shift(-(k-1))  # count of valid obs in window
    f=np.expm1(c.shift(-(k-1))-c.shift(1))
    f=f.where(valid>=k)
    return f
F={1:ret.copy(),5:fwd(5),10:fwd(10),21:fwd(21)}

# tradeable mask: median 20d turnover >= Rs 1 crore (turn in lakhs)
t20=turn.rolling(20,min_periods=15).median()
trad=(t20>=100.0)

# market proxy = equal-weight mean over tradeable names, per horizon
MKT={k:F[k].where(trad).mean(axis=1) for k in F}

# ---------- attach to panel ----------
p['di']=p.date.map(di)
sym_i={s:i for i,s in enumerate(ret.columns)}
p['si']=p.sym.map(sym_i)
p=p.dropna(subset=['di','si']); p['di']=p.di.astype(int); p['si']=p.si.astype(int)
for k in F:
    A=F[k].values
    p[f'f{k}']=A[p.di.values,p.si.values]
    p[f'm{k}']=MKT[k].values[p.di.values]
    p[f'x{k}']=p[f'f{k}']-p[f'm{k}']     # market-neutral excess
p['tradeable']=trad.values[p.di.values,p.si.values]
print('tradeable frac',p.tradeable.mean().round(3))

# ---------- structural classification (all from PRIOR-CLOSE features) ----------
def classify(d):
    t=pd.Series('OTHER',index=d.index,dtype=object)
    # order matters; assign most specific first
    fromnowhere=(d.ret21.abs()<0.05)&(d.ret5.abs()<0.03)&(d.vol20<0.025)
    revers=(d.pos52<=0.10)&(d.ret21<=-0.15)
    breakout=(d.pos52>=0.95)
    cont=(d.ret21>=0.20)&(d.pos52<0.95)
    t[fromnowhere]='FROM-NOWHERE'
    t[cont]='CONTINUATION'
    t[revers]='REVERSAL'
    t[breakout]='BREAKOUT'
    return t
p['type']=classify(p)
print(p.type.value_counts())

SPLIT=pd.Timestamp('2025-01-20')
p['period']=np.where(p.date<SPLIT,'train','holdout')

COST={'intraday':0.00107,'delivery':0.0024}

def clust_t(df,col):
    g=df.groupby('date')[col].mean().dropna()
    if len(g)<10: return np.nan,np.nan,len(g)
    return g.mean(), g.mean()/(g.std(ddof=1)/np.sqrt(len(g))), len(g)

rows=[]
sub=p[p.tradeable].copy()
for period in ['train','holdout']:
    for typ in ['BREAKOUT','REVERSAL','CONTINUATION','FROM-NOWHERE','OTHER','ALL']:
        for h in [1,5,10,21]:
            d=sub[(sub.period==period)]
            if typ!='ALL': d=d[d.type==typ]
            d=d.dropna(subset=[f'x{h}',f'f{h}'])
            if len(d)<200: continue
            r=d[f'f{h}'].values; x=d[f'x{h}'].values
            thr=0.05 if h==1 else (0.10 if h<=10 else 0.15)
            mn,tt,nd=clust_t(d,f'x{h}')
            mnr,ttr,_=clust_t(d,f'f{h}')
            rows.append(dict(period=period,type=typ,h=h,n=len(d),
                win_rate=float(d['win'].mean()) if h==1 else np.nan,
                mean_raw=float(np.mean(r)),mean_mn=mn,t_mn=tt,t_raw=ttr,ndays=nd,
                p_up=float((r>thr).mean()),p_dn=float((r<-thr).mean()),
                p_up_mn=float((x>thr).mean()),p_dn_mn=float((x<-thr).mean()),
                skew=float(stats.skew(r,nan_policy='omit')),
                skew_mn=float(stats.skew(x,nan_policy='omit')),
                med=float(np.median(r)),
                net_intra=float(np.mean(r))-COST['intraday'],
                net_deliv=float(np.mean(r))-COST['delivery'],
                net_mn_deliv=mn-COST['delivery']))
res=pd.DataFrame(rows)
res.to_csv(B+'docs/research/overnight/_anatomy_types.csv',index=False)
print(res[res.h==1].to_string(index=False))
