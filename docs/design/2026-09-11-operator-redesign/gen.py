#!/usr/bin/env python3
"""Generates the four operator-page artboards. Tokens lifted verbatim from prototype/static/desk.css."""
HEAD = '''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>
    :root{--bg:#0a0d13;--panel:#10141c;--panel2:#0d1118;--line:#1c2330;--line2:#242d3d;--hover:#151b26;--ink:#e6ebf2;--mut:#8a94a6;--dim:#57627a;--green:#16c784;--green-bg:rgba(22,199,132,.09);--red:#ea3943;--red-bg:rgba(234,57,67,.09);--amber:#f0a93b;--amber-bg:rgba(240,169,59,.10);--acc:#6366f1;--acc-bg:rgba(99,102,241,.12);--mono:ui-monospace,"SF Mono",Menlo,monospace}
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:var(--bg);color:var(--ink);font:13px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;width:1440px;min-height:960px}
    a{color:var(--acc);text-decoration:none} a:hover{color:#8b8df5}
    .num{font-family:var(--mono);font-variant-numeric:tabular-nums}
    .pos{color:var(--green)} .neg{color:var(--red)} .flat{color:var(--mut)} .warn{color:var(--amber)}
    .topbar{display:flex;align-items:center;gap:20px;height:46px;padding:0 16px;background:var(--panel2);border-bottom:1px solid var(--line)}
    .brand{display:flex;align-items:center;gap:8px;flex:none}.brand svg{width:20px;height:20px}
    .brand b{font-size:12px;letter-spacing:2.5px;font-weight:700}.brand span{font-size:12px;letter-spacing:2.5px;color:var(--dim)}
    .idxstrip{display:flex;gap:4px;flex:1}
    .idx{display:flex;align-items:baseline;gap:7px;padding:4px 10px;border-radius:4px;white-space:nowrap}
    .idx .n{font-size:10.5px;letter-spacing:.8px;color:var(--dim);text-transform:uppercase}.idx .v{font-size:12.5px;font-weight:600}.idx .c{font-size:11.5px}
    .sess{display:flex;align-items:center;gap:10px;flex:none}
    .pill{font-size:10.5px;font-weight:700;letter-spacing:1.2px;padding:3px 9px;border-radius:3px;text-transform:uppercase}
    .pill.live{color:var(--green);background:var(--green-bg);border:1px solid rgba(22,199,132,.3)}
    .pill.pre{color:var(--amber);background:var(--amber-bg);border:1px solid rgba(240,169,59,.3)}
    .pill.closed{color:var(--dim);background:var(--panel);border:1px solid var(--line)}
    .clock{font-family:var(--mono);font-size:12.5px;color:var(--mut)}
    .nav{display:flex;gap:2px;padding:0 16px;background:var(--panel2);border-bottom:1px solid var(--line);align-items:center}
    .nav a{padding:9px 14px 8px;font-size:12px;font-weight:600;color:var(--mut);letter-spacing:.3px;border-bottom:2px solid transparent}
    .nav a.on{color:var(--ink);border-bottom-color:var(--acc)}
    .nav .sp{flex:1}.nav a.legacy{color:var(--dim);font-weight:500}
    .main{padding:14px 16px 24px}
    .card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px;min-width:0}
    .card h3{font-size:10px;font-weight:700;letter-spacing:.9px;color:var(--dim);text-transform:uppercase;margin-bottom:8px;display:flex;align-items:center;gap:8px}
    .card h3 .r{margin-left:auto;font-weight:500;letter-spacing:.3px;text-transform:none;color:var(--dim)}
    .kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px}
    .kpi .big{font-size:24px;font-weight:700;letter-spacing:-.4px}.kpi .sub{font-size:11.5px;color:var(--mut);margin-top:3px}
    .chip{font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;padding:2px 7px;border-radius:3px;white-space:nowrap}
    .chip.ok{color:var(--green);background:var(--green-bg)}.chip.bad{color:var(--red);background:var(--red-bg)}.chip.warn{color:var(--amber);background:var(--amber-bg)}.chip.acc{color:var(--acc);background:var(--acc-bg)}.chip.dim{color:var(--dim);background:var(--panel2);border:1px solid var(--line)}
    .tbl{width:100%;border-collapse:collapse;font-size:12.5px}
    .tbl th{text-align:left;font-size:10px;font-weight:700;letter-spacing:.9px;color:var(--dim);text-transform:uppercase;padding:6px 8px;border-bottom:1px solid var(--line2);white-space:nowrap}
    .tbl th.r,.tbl td.r{text-align:right}
    .tbl td{padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
    .tbl tr.sel td{background:var(--acc-bg)}
    .tbl .sym{font-weight:650}.tbl .eng{color:var(--mut);font-size:11.5px}
    .btn{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 12px;border-radius:4px;font-size:12px;font-weight:600;border:1px solid var(--line2);background:var(--panel2);color:var(--ink)}
    .btn.acc{background:var(--acc);border-color:var(--acc);color:#fff}
    .dot{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none}
    .dot.ok{background:var(--green)}.dot.bad{background:var(--red)}.dot.warn{background:var(--amber)}.dot.dim{background:var(--dim)}
    .bar-wrap{background:var(--panel2);border-radius:3px;height:5px;overflow:hidden;margin-top:7px}.bar{height:100%}
    .muted{color:var(--mut)}.dimt{color:var(--dim)}.small{font-size:11.5px}
  </style>
</helmet>
'''
TAIL = '</x-dc>\n</body>\n</html>\n'
LOGO = '''<svg viewBox="0 0 72 72" aria-label="TradePilot"><defs><linearGradient id="tpg" x1="0" y1="72" x2="72" y2="0" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#4338CA"></stop><stop offset="100%" stop-color="#7C7FF3"></stop></linearGradient></defs><g><rect x="9.25" y="45" width="11.5" height="15" rx="1.8" fill="url(#tpg)"></rect><rect x="28.25" y="34" width="11.5" height="17" rx="1.8" fill="url(#tpg)"></rect><rect x="47.25" y="23" width="11.5" height="17" rx="1.8" fill="url(#tpg)"></rect><path d="M9 54 L27 41 L45 30 L60 15" fill="none" stroke="url(#tpg)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M47 13 L62 13 L62 28" fill="none" stroke="url(#tpg)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"></path></g></svg>'''

def chrome(current, sess, clock, idx):
    tabs = [('ready','Ready'),('market','Market'),('book','Book'),('review','Review')]
    nav = ''.join(f'<a class="{"on" if k==current else ""}">{t}</a>' for k,t in tabs)
    idxs = ''.join(f'<div class="idx"><span class="n">{n}</span><span class="v num">{v}</span><span class="c num {c}">{ch}</span></div>' for n,v,ch,c in idx)
    return f'''<header class="topbar">
  <div class="brand">{LOGO}<b>TRADEPILOT</b><span>TERMINAL</span></div>
  <div class="idxstrip">{idxs}</div>
  <div class="sess"><span class="pill {sess[0]}">{sess[1]}</span><span class="clock">{clock}</span></div>
</header>
<nav class="nav">{nav}<span class="sp"></span><a class="legacy">Legacy ▾</a><a class="legacy">Client app ↗</a></nav>
'''

PRE = [('NIFTY 50','24,918.40','—','flat'),('SENSEX','81,442.10','—','flat'),('BANK NIFTY','54,210.65','—','flat'),('INDIA VIX','13.42','—','flat')]
LIVE = [('NIFTY 50','24,861.15','-0.23%','neg'),('SENSEX','81,205.30','-0.29%','neg'),('BANK NIFTY','54,388.90','+0.33%','pos'),('INDIA VIX','13.91','+3.6%','warn')]
CLOSE = [('NIFTY 50','24,796.70','-0.49%','neg'),('SENSEX','80,988.45','-0.56%','neg'),('BANK NIFTY','54,120.10','-0.17%','neg'),('INDIA VIX','14.20','+5.8%','warn')]

# ───────────────────────── READY ─────────────────────────
def row(state, name, detail, action=''):
    cls = {'ok':'ok','bad':'bad','warn':'warn'}[state]
    act = f'<a class="btn">{action}</a>' if action else ''
    return f'''<div style="display:flex;align-items:center;gap:14px;padding:11px 0;border-bottom:1px solid var(--line)">
      <span class="dot {cls}"></span>
      <div style="width:190px;font-weight:600">{name}</div>
      <div style="flex:1" class="muted">{detail}</div>{act}
    </div>'''

ready = HEAD + chrome('ready', ('pre','Pre-open'), '08:52:10', PRE) + f'''
<div class="main" style="display:grid;grid-template-columns:minmax(0,7fr) minmax(0,4fr);gap:12px">
  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card" style="border-color:rgba(240,169,59,.4);background:var(--amber-bg);padding:18px 20px;display:flex;align-items:center;gap:18px">
      <div style="font-size:30px;font-weight:800;letter-spacing:-.6px;color:var(--amber)">Fix 1 thing before open</div>
      <div class="muted" style="font-size:13px">Everything else is ready. Market opens in <span class="num" style="color:var(--ink)">22:50</span>.</div>
    </div>
    <div class="card">
      <h3>Pre-open checks <span class="r">ran 08:52:10 · re-runs every 60s</span></h3>
      {row('ok','Launch fired on time','launchd fired 08:45:02 · Mac on AC power · did not sleep overnight')}
      {row('bad','Engines up','4 of 5 running. <b style="color:var(--ink)">v6 did not start</b> · last log line: ModuleNotFoundError: v6.scorer','Start v6')}
      {row('ok','Price feed sane','451 symbols · last tick 08:52:04 · 0 NaN · cache cleared 08:44')}
      {row('ok','ML model fresh','trained 2026-09-10 21:30 · 1 day old · guard limit 3 days')}
      {row('ok','Data link','NSE direct OK · yfinance OK · Kite: paper mode')}
      {row('ok','Regime picked','09:06 rescore will run · yesterday closed <b style="color:var(--ink)">trending down</b>')}
      {row('warn','Disk','12 GB free · engine logs 3.1 GB · fine for today, clean this week','Clean logs')}
    </div>
  </div>
  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card">
      <h3>Yesterday in one line</h3>
      <div style="font-size:15px;line-height:1.5">Fleet <b class="num neg">₹-4,085</b> on 53 trades. v5 hit rate <b class="num">45%</b>, below the 60% floor. 9 of 31 losses entered against the trend.</div>
      <div style="margin-top:8px"><a>Open yesterday's Review →</a></div>
    </div>
    <div class="card">
      <h3>Today's setup</h3>
      <table class="tbl">
        <thead><tr><th>Engine</th><th>Capital</th><th class="r">Pool</th><th class="r">State</th></tr></thead>
        <tbody>
          <tr><td class="sym">v5</td><td class="num">₹10,00,000</td><td class="r muted">intraday</td><td class="r"><span class="chip ok">ready</span></td></tr>
          <tr><td class="sym">v5_wide</td><td class="num">₹10,00,000</td><td class="r muted">intraday</td><td class="r"><span class="chip ok">ready</span></td></tr>
          <tr><td class="sym">v5_swing</td><td class="num">₹10,00,000</td><td class="r muted">swing</td><td class="r"><span class="chip ok">ready</span></td></tr>
          <tr><td class="sym">DAYGAIN</td><td class="num">₹1,00,000</td><td class="r muted">holdout</td><td class="r"><span class="chip ok">ready</span></td></tr>
          <tr><td class="sym">v6</td><td class="num">₹10,00,000</td><td class="r muted">intraday</td><td class="r"><span class="chip bad">down</span></td></tr>
        </tbody>
      </table>
    </div>
    <div class="card">
      <h3>Shadow experiments <span class="r">day 4 of 10</span></h3>
      <div class="small" style="display:flex;flex-direction:column;gap:6px">
        <div style="display:flex;justify-content:space-between"><span>Regime gate</span><span class="num pos">+₹1,140 vs live</span></div>
        <div style="display:flex;justify-content:space-between"><span>Arm band</span><span class="num neg">-₹380 vs live</span></div>
        <div style="display:flex;justify-content:space-between"><span>DAYGAIN row</span><span class="num flat">recording</span></div>
      </div>
    </div>
  </div>
</div>
''' + TAIL

# ───────────────────────── MARKET ─────────────────────────
def news(t, src, head, tag, cls):
    return f'''<div style="display:flex;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)">
      <span class="num dimt small" style="width:44px;flex:none">{t}</span>
      <div style="flex:1;min-width:0"><div>{head}</div><div class="small dimt">{src}</div></div>
      <span class="chip {cls}" style="align-self:flex-start">{tag}</span></div>'''

def spark(pts, color):
    return f'<svg viewBox="0 0 120 28" width="120" height="28" style="display:block"><polyline fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="{pts}"></polyline></svg>'

def mood(n, v, ch, cls, pts, col):
    return f'''<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line)">
      <div><div class="small dimt" style="letter-spacing:.8px;text-transform:uppercase">{n}</div><div><span class="num" style="font-size:16px;font-weight:600">{v}</span> <span class="num {cls} small">{ch}</span></div></div>{spark(pts,col)}</div>'''

market = HEAD + chrome('market', ('live','Live'), '10:42:18', LIVE) + f'''
<div class="main" style="display:grid;grid-template-columns:minmax(0,5fr) minmax(0,3fr) minmax(0,5fr);gap:12px">
  <div class="card">
    <h3>World, filtered for India <span class="r">only items that can move our stocks</span></h3>
    {news('10:31','Reuters','Brent crude +3.1% after OPEC+ holds output cut','Hurts OMCs, paints','bad')}
    {news('10:05','Bloomberg','US 10-yr yield 4.41%, dollar index 104.8','FII outflow risk','warn')}
    {news('09:48','ET Markets','RBI keeps repo at 6.25%, stance neutral','Neutral banks','dim')}
    {news('09:20','Nikkei','Nikkei -1.2%, Hang Seng -0.9% on China data','Weak Asia open','bad')}
    {news('08:55','Mint','Adani Ports Q1 volumes +8%, guidance raised','Helps ADANIPORTS','ok')}
    {news('08:30','CNBC','Nasdaq futures flat ahead of CPI print at 18:00 IST','Watch IT at close','warn')}
    <div class="small dimt" style="margin-top:8px">Impact tags are set by the news agent. Untagged items are hidden.</div>
  </div>
  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card">
      <h3>Mood</h3>
      {mood('NIFTY 50','24,861','-0.23%','neg','0,10 20,12 40,9 60,14 80,17 100,16 120,19','#ea3943')}
      {mood('BANK NIFTY','54,389','+0.33%','pos','0,18 20,16 40,17 60,12 80,10 100,11 120,8','#16c784')}
      {mood('INDIA VIX','13.91','+3.6%','warn','0,20 20,19 40,17 60,15 80,12 100,10 120,8','#f0a93b')}
      <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px" class="small">
        <div style="display:flex;justify-content:space-between"><span class="muted">Breadth</span><span class="num">612 up · 1,204 down</span></div>
        <div style="display:flex;justify-content:space-between"><span class="muted">FII / DII (prov.)</span><span class="num"><span class="neg">-412 Cr</span> / <span class="pos">+988 Cr</span></span></div>
        <div style="display:flex;justify-content:space-between"><span class="muted">Regime (09:06)</span><span class="chip dim">Trending down</span></div>
      </div>
    </div>
    <div class="card">
      <h3>Sectors now</h3>
      <div class="small" style="display:flex;flex-direction:column;gap:5px">
        <div style="display:flex;justify-content:space-between"><span>Bank</span><span class="num pos">+0.4%</span></div>
        <div style="display:flex;justify-content:space-between"><span>Pharma</span><span class="num pos">+0.3%</span></div>
        <div style="display:flex;justify-content:space-between"><span>IT</span><span class="num neg">-0.8%</span></div>
        <div style="display:flex;justify-content:space-between"><span>Oil &amp; gas</span><span class="num neg">-1.1%</span></div>
        <div style="display:flex;justify-content:space-between"><span>Metals</span><span class="num neg">-1.6%</span></div>
      </div>
    </div>
  </div>
  <div class="card">
    <h3>Running today, and we are not in <span class="r">top movers vs our book</span></h3>
    <table class="tbl">
      <thead><tr><th>Stock</th><th class="r">Move</th><th class="r">Volume</th><th>Why we skipped it</th></tr></thead>
      <tbody>
        <tr><td class="sym">HINDALCO</td><td class="r num neg">-3.4%</td><td class="r num">2.1×</td><td class="small muted">Short score 21, below the 25 gate</td></tr>
        <tr><td class="sym">ICICIBANK</td><td class="r num pos">+2.2%</td><td class="r num">1.8×</td><td class="small muted">Regime blocks longs today</td></tr>
        <tr><td class="sym">TATASTEEL</td><td class="r num neg">-2.9%</td><td class="r num">2.4×</td><td class="small muted">ASM list, excluded</td></tr>
        <tr><td class="sym">SUNPHARMA</td><td class="r num pos">+1.9%</td><td class="r num">1.3×</td><td class="small muted">Regime blocks longs today</td></tr>
        <tr><td class="sym">IRFC</td><td class="r num pos">+4.1%</td><td class="r num">3.2×</td><td class="small warn">Not in the 451 universe</td></tr>
        <tr><td class="sym">BPCL</td><td class="r num neg">-2.6%</td><td class="r num">1.6×</td><td class="small muted">Scored 31 at 09:36, slot full</td></tr>
      </tbody>
    </table>
    <div style="margin-top:12px;padding:10px 12px;border:1px solid var(--line2);border-radius:4px" class="small">
      <b>Pattern so far:</b> the regime gate blocked 2 longs that would have paid. Both are in sectors that are green while the index is red. Tonight's Review will score this.
    </div>
  </div>
</div>
''' + TAIL

# ───────────────────────── BOOK ─────────────────────────
def pod(name, state, cls, scans, trades, pnl, pcls):
    return f'''<div class="card" style="padding:10px 12px;display:flex;flex-direction:column;gap:4px">
      <div style="display:flex;align-items:center;gap:8px"><span class="dot {cls}"></span><b>{name}</b><span class="chip dim" style="margin-left:auto">{state}</span></div>
      <div class="small muted">{scans}</div>
      <div style="display:flex;justify-content:space-between" class="small"><span class="muted">{trades}</span><span class="num {pcls}">{pnl}</span></div></div>'''

def prow(sym, eng, side, entry, now, pnl, pcls, stop, t, trend, tcls, sel=''):
    return f'<tr class="{sel}"><td class="sym">{sym}<div class="eng">{eng}</div></td><td><span class="chip dim">{side}</span></td><td class="r num">{entry}</td><td class="r num">{now}</td><td class="r num {pcls}">{pnl}</td><td class="r num">{stop}</td><td class="r num muted">{t}</td><td><span class="chip {tcls}">{trend}</span></td></tr>'

book = HEAD + chrome('book', ('live','Live'), '10:42:18', LIVE) + f'''
<div class="main">
  <div class="kpis">
    <div class="card kpi"><h3>Net today</h3><div class="big num neg">₹-1,224</div><div class="sub">₹-812 before costs of ₹412 · 14 trades</div></div>
    <div class="card kpi"><h3>Open now</h3><div class="big num">7</div><div class="sub">₹4.2L deployed of ₹41L</div></div>
    <div class="card kpi"><h3>At risk if every stop hits</h3><div class="big num warn">₹-3,860</div><div class="sub">2 positions within 0.3% of stop</div></div>
    <div class="card kpi"><h3>Hit rate today</h3><div class="big num">6 / 14</div><div class="sub">43% counting 3 open winners · floor is 60%</div></div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:10px">
    {pod('v5','picking','ok','scan 10:40 · next 10:45','9 trades','₹-514','neg')}
    {pod('v5_wide','picking','ok','scan 10:40 · next 10:45','3 trades','₹+862','pos')}
    {pod('v5_swing','holding','ok','rescore 13:30','1 open','₹-610','neg')}
    {pod('DAYGAIN','recording','ok','scan 10:40','1 trade','₹-550','neg')}
    {pod('v6','down','bad','no scan since 08:45','0 trades','—','flat')}
  </div>
  <div style="display:grid;grid-template-columns:minmax(0,8fr) minmax(0,4fr);gap:12px">
    <div class="card">
      <h3>Open positions <span class="r">sorted by distance to stop</span></h3>
      <table class="tbl">
        <thead><tr><th>Stock</th><th>Side</th><th class="r">Entry</th><th class="r">Now</th><th class="r">P&amp;L</th><th class="r">To stop</th><th class="r">In trade</th><th>Trend at entry</th></tr></thead>
        <tbody>
          {prow('HINDALCO','v5','SHORT','612.40','617.10','₹-376','neg','0.2%','18 min','Against','warn','sel')}
          {prow('INFY','v5','SHORT','1,482.00','1,489.50','₹-300','neg','0.3%','32 min','Against','warn')}
          {prow('GRASIM','v5_wide','SHORT','2,741.20','2,731.80','₹+282','pos','1.4%','41 min','With','dim')}
          {prow('TATAMOTORS','v5','SHORT','688.90','684.10','₹+192','pos','1.1%','55 min','With','dim')}
          {prow('SBIN','v5_swing','LONG','812.30','806.20','₹-610','neg','0.9%','2 days','Flat','dim')}
          {prow('JSWSTEEL','DAYGAIN','LONG','918.00','912.50','₹-550','neg','0.8%','1h 05','Against','warn')}
          {prow('AXISBANK','v5_wide','SHORT','1,102.60','1,098.40','₹+168','pos','1.3%','12 min','With','dim')}
        </tbody>
      </table>
      <div class="small" style="margin-top:10px;padding:10px 12px;background:var(--red-bg);border-radius:4px;border:1px solid rgba(234,57,67,.25)">
        <b class="neg">Bleeding:</b> 3 of 7 open trades were entered against the 15-min trend, and all 3 are losing. Combined <span class="num neg">₹-1,226</span>. This is the pattern from yesterday.
      </div>
    </div>
    <div class="card">
      <h3>Exits today <span class="r">newest first</span></h3>
      <div class="small" style="display:flex;flex-direction:column">
        <div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)"><span class="num dimt">10:38</span><b style="width:96px">BAJFINANCE</b><span class="muted" style="flex:1">target</span><span class="num pos">₹+412</span></div>
        <div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)"><span class="num dimt">10:21</span><b style="width:96px">TECHM</b><span class="muted" style="flex:1">stop</span><span class="num neg">₹-288</span></div>
        <div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)"><span class="num dimt">10:04</span><b style="width:96px">LTIM</b><span class="muted" style="flex:1">stop</span><span class="num neg">₹-301</span></div>
        <div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)"><span class="num dimt">09:58</span><b style="width:96px">EICHERMOT</b><span class="muted" style="flex:1">target</span><span class="num pos">₹+520</span></div>
        <div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)"><span class="num dimt">09:50</span><b style="width:96px">COALINDIA</b><span class="muted" style="flex:1">stop, 10 min</span><span class="num neg">₹-103</span></div>
        <div style="display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)"><span class="num dimt">09:44</span><b style="width:96px">POWERGRID</b><span class="muted" style="flex:1">stop, 6 min</span><span class="num neg">₹-96</span></div>
        <div style="display:flex;gap:10px;padding:7px 0"><span class="num dimt">09:41</span><b style="width:96px">ONGC</b><span class="muted" style="flex:1">target</span><span class="num pos">₹+238</span></div>
      </div>
      <div class="small dimt" style="margin-top:10px">4 stops so far. 2 of them lasted 10 minutes or less.</div>
    </div>
  </div>
</div>
''' + TAIL

# ───────────────────────── REVIEW ─────────────────────────
def candles():
    # 5-min candles 09:15 -> 10:15 for ADANIPORTS, (open, high, low, close); a down open then a rip up through the short.
    data = [(1772,1776,1766,1768),(1768,1770,1761,1763),(1763,1765,1757,1759),(1759,1762,1754,1756),(1756,1760,1753,1758),(1758,1764,1757,1763),
            (1763,1770,1762,1769),(1769,1774,1767,1772),(1772,1775,1769,1771),(1771,1773,1766,1768),(1768,1770,1764,1766),(1766,1769,1763,1767)]
    lo, hi = 1750, 1780
    W, H, L, T = 640, 260, 48, 16
    def y(p): return T + (hi - p) / (hi - lo) * H
    out = []
    for i,(o,h,l,c) in enumerate(data):
        x = L + 24 + i*48
        up = c >= o
        col = '#16c784' if up else '#ea3943'
        out.append(f'<line x1="{x}" y1="{y(h):.1f}" x2="{x}" y2="{y(l):.1f}" stroke="{col}" stroke-width="1.5"></line>')
        top, bot = y(max(o,c)), y(min(o,c))
        out.append(f'<rect x="{x-7}" y="{top:.1f}" width="14" height="{max(bot-top,2):.1f}" rx="1.5" fill="{col if not up else "#10141c"}" stroke="{col}" stroke-width="1.5"></rect>')
    grid = ''.join(f'<line x1="{L}" y1="{y(p):.1f}" x2="{W}" y2="{y(p):.1f}" stroke="#1c2330"></line><text x="{L-6}" y="{y(p)+4:.1f}" text-anchor="end" fill="#57627a" font-size="10" font-family="ui-monospace,Menlo,monospace">{p}</text>' for p in (1755,1760,1765,1770,1775))
    ticks = ''.join(f'<text x="{L+24+i*48}" y="{T+H+16}" text-anchor="middle" fill="#57627a" font-size="10" font-family="ui-monospace,Menlo,monospace">{t}</text>' for i,t in enumerate(['09:15','','09:25','','09:35','','09:45','','09:55','','10:05','']))
    # entry short at 09:40 (index 5) @1757.4 ; exit stop 09:50 (index 7) @1768.1
    ex, ey = L+24+5*48, y(1757.4)
    xx, xy = L+24+7*48, y(1768.1)
    marks = f'''<line x1="{L}" y1="{y(1757.4):.1f}" x2="{W}" y2="{y(1757.4):.1f}" stroke="#16c784" stroke-dasharray="3 4" opacity=".6"></line>
    <line x1="{L}" y1="{y(1768.1):.1f}" x2="{W}" y2="{y(1768.1):.1f}" stroke="#ea3943" stroke-dasharray="3 4" opacity=".6"></line>
    <path d="M{ex} {ey+26:.1f} l-7 10 h14 z" fill="#16c784"></path><text x="{ex}" y="{ey+50:.1f}" text-anchor="middle" fill="#16c784" font-size="10" font-weight="700">SELL 09:40 · 1757.4</text>
    <path d="M{xx} {xy-26:.1f} l-7 -10 h14 z" fill="#6366f1"></path><text x="{xx}" y="{xy-42:.1f}" text-anchor="middle" fill="#8b8df5" font-size="10" font-weight="700">STOP 09:50 · 1768.1</text>
    <rect x="{L+24+2*48-20}" y="{T}" width="{4*48}" height="{H}" fill="#ea3943" opacity=".06"></rect>
    <text x="{L+24+4*48-20}" y="{T+12}" text-anchor="middle" fill="#ea3943" font-size="10" font-weight="700" opacity=".9">15-min trend: DOWN then TURNING</text>'''
    return f'<svg viewBox="0 0 {W+16} {H+40}" width="100%" style="display:block">{grid}{"".join(out)}{marks}{ticks}</svg>'

def trow(sym, eng, side, t, pnl, pcls, tag, tcls, sel=''):
    return f'<tr class="{sel}"><td class="sym">{sym}<div class="eng">{eng}</div></td><td class="num small muted">{t}</td><td class="r num {pcls}">{pnl}</td><td><span class="chip {tcls}">{tag}</span></td></tr>'

review = HEAD + chrome('review', ('closed','Closed'), '16:10:44', CLOSE) + f'''
<div class="main" style="display:grid;grid-template-columns:minmax(0,3fr) minmax(0,6fr) minmax(0,3fr);gap:12px">
  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card">
      <h3>Day by engine <span class="r">Wed 10 Sep</span></h3>
      <table class="tbl">
        <thead><tr><th>Engine</th><th class="r">Net</th><th class="r">Hit</th></tr></thead>
        <tbody>
          <tr><td class="sym">v5</td><td class="r num neg">₹-2,123</td><td class="r num">17/38</td></tr>
          <tr><td class="sym">v5_wide</td><td class="r num neg">₹-287</td><td class="r num">3/11</td></tr>
          <tr><td class="sym">v5_swing</td><td class="r num neg">₹-2,087</td><td class="r num">0/1</td></tr>
          <tr><td class="sym">DAYGAIN</td><td class="r num pos">₹+412</td><td class="r num">2/3</td></tr>
          <tr><td class="sym" style="color:var(--mut)">Fleet</td><td class="r num neg" style="font-weight:700">₹-4,085</td><td class="r num">22/53</td></tr>
        </tbody>
      </table>
    </div>
    <div class="card" style="flex:1">
      <h3>Trades <span class="r">losers first</span></h3>
      <table class="tbl">
        <thead><tr><th>Stock</th><th>In → out</th><th class="r">Net</th><th>Why</th></tr></thead>
        <tbody>
          {trow('SBIN','v5_swing · long','LONG','Mon → 15:20','₹-2,087','neg','Held through drop','warn')}
          {trow('HINDALCO','v5 · short','SHORT','10:24 → 11:10','₹-540','neg','Against trend','warn')}
          {trow('HCLTECH','v5 · short','SHORT','09:52 → 10:04','₹-301','neg','Against trend','warn')}
          {trow('WIPRO','v5 · short','SHORT','10:02 → 10:21','₹-288','neg','Late entry','warn')}
          {trow('ADANIPORTS','v5 · short','SHORT','09:40 → 09:50','₹-103','neg','Against trend','warn','sel')}
          {trow('NTPC','v5 · short','SHORT','09:38 → 09:44','₹-96','neg','Against trend','warn')}
          {trow('BAJFINANCE','v5_wide · short','SHORT','10:10 → 10:38','₹+412','pos','With trend','dim')}
          {trow('MARUTI','v5 · short','SHORT','09:31 → 09:58','₹+520','pos','With trend','dim')}
        </tbody>
      </table>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card">
      <h3>ADANIPORTS · v5 · short <span class="r">5-min candles · 09:15 to 10:15</span></h3>
      {candles()}
      <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:8px" class="small">
        <div><div class="dimt">Entered</div><div class="num">09:40:13 · 1,757.40</div></div>
        <div><div class="dimt">Exited</div><div class="num">09:50:14 · 1,768.10 · stop</div></div>
        <div><div class="dimt">Net</div><div class="num neg">₹-102.52 · cost ₹16.92</div></div>
        <div><div class="dimt">Candle at entry</div><div>Hammer after 4 red, 2.1× volume</div></div>
      </div>
    </div>
    <div class="card">
      <h3>What the engine saw at 09:40 <span class="r">score 29.3, gate was 25</span></h3>
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 18px" class="small">
        <div><span class="neg">−</span> ORB breakdown below 1760</div>
        <div><span class="neg">−</span> Price 0.39% below VWAP (1764)</div>
        <div><span class="neg">−</span> FII selling, -583 Cr</div>
        <div><span class="pos">+</span> DII buying, +1509 Cr</div>
        <div><span class="neg">−</span> Negative intraday momentum</div>
        <div><span class="warn">!</span> Not checked: last candle was a hammer on volume</div>
      </div>
      <div class="small" style="margin-top:10px;padding:10px 12px;background:var(--amber-bg);border:1px solid rgba(240,169,59,.3);border-radius:4px">
        <b class="warn">Verdict:</b> shorted the bottom. The 09:35 candle was a reversal signal the scorer does not read. Same shape on NTPC and HCLTECH today. Three trades, <span class="num neg">₹-500</span>, one cause.
      </div>
    </div>
  </div>
  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card">
      <h3>Losses by cause <span class="r">31 losing trades</span></h3>
      <div class="small" style="display:flex;flex-direction:column;gap:9px">
        <div><div style="display:flex;justify-content:space-between"><span>Entered against 15-min trend</span><span class="num neg">₹-1,040</span></div><div class="bar-wrap"><div class="bar" style="width:50%;background:var(--red)"></div></div><div class="dimt">9 trades · 0 won</div></div>
        <div><div style="display:flex;justify-content:space-between"><span>Swing held through a drop</span><span class="num neg">₹-2,087</span></div><div class="bar-wrap"><div class="bar" style="width:100%;background:var(--red)"></div></div><div class="dimt">1 trade · no intraday stop</div></div>
        <div><div style="display:flex;justify-content:space-between"><span>Late entry, move was done</span><span class="num neg">₹-612</span></div><div class="bar-wrap"><div class="bar" style="width:29%;background:var(--red)"></div></div><div class="dimt">4 trades · 0 won</div></div>
        <div><div style="display:flex;justify-content:space-between"><span>Normal stop, good entry</span><span class="num neg">₹-346</span></div><div class="bar-wrap"><div class="bar" style="width:17%;background:var(--dim)"></div></div><div class="dimt">17 trades · acceptable</div></div>
      </div>
    </div>
    <div class="card">
      <h3>Learnings recorded <span class="r">3 today</span></h3>
      <div class="small" style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;gap:8px"><span class="chip acc">new</span><span>Reversal candle on 2× volume after 5 red: do not short for 2 bars.</span></div>
        <div style="display:flex;gap:8px"><span class="chip acc">new</span><span>Swing pool needs an intraday stop on down-regime days.</span></div>
        <div style="display:flex;gap:8px"><span class="chip dim">repeat</span><span>Regime gate blocked 3 winning longs in green sectors. 4th day running.</span></div>
      </div>
    </div>
    <div class="card">
      <h3>ML loop</h3>
      <div class="small" style="display:flex;flex-direction:column;gap:6px">
        <div style="display:flex;justify-content:space-between"><span class="muted">Last trained</span><span class="num">10 Sep 21:30</span></div>
        <div style="display:flex;justify-content:space-between"><span class="muted">Learnings used</span><span class="num">41 of 44</span></div>
        <div style="display:flex;justify-content:space-between"><span class="muted">Not yet used</span><span class="num warn">3, from today</span></div>
        <div style="display:flex;justify-content:space-between"><span class="muted">Next retrain</span><span class="num">tonight 21:30</span></div>
      </div>
      <a class="btn acc" style="margin-top:10px">Retrain now with today's learnings</a>
    </div>
  </div>
</div>
''' + TAIL

for name, html in (('Main', ready), ('Market', market), ('Book', book), ('Review', review)):
    open(f'{name}.dc.html', 'w').write(html)
    print(name, len(html))
