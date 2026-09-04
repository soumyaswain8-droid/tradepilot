# Generates the Groww-style client artboards from shared parts.
HEAD = '''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
  <style>
    body { margin: 0; background: #FFFFFF; color: #1B1F2A; font: 14px/1.5 "Plus Jakarta Sans", -apple-system, "Segoe UI", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
    a { color: #0B8F5F; text-decoration: none; } a:hover { color: #087A50; }
    .num { font-family: "JetBrains Mono", ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
    .card { background: #FFFFFF; border: 1px solid #EAECF0; border-radius: 16px; padding: 20px 22px; }
    .tint { background: #F6F8FA; border-color: #F6F8FA; }
    .label { font-size: 12px; color: #6C7280; font-weight: 600; }
    .up { color: #0FA36B; } .down { color: #E04A3C; } .mut { color: #6C7280; }
    .chip { display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .2px; }
    .chip.buy { background: #E6F7EF; color: #0B8F5F; } .chip.sell { background: #FDECEA; color: #C93C2E; }
    .chip.open { background: #EEF2FF; color: #4A55C7; } .chip.hit { background: #E6F7EF; color: #0B8F5F; } .chip.miss { background: #FDECEA; color: #C93C2E; } .chip.ung { background: #F1F3F5; color: #6C7280; }
    .tab { height: 44px; display: inline-flex; align-items: center; padding: 0 4px; margin-right: 24px; font-size: 15px; font-weight: 600; color: #6C7280; border-bottom: 2px solid transparent; }
    .tab.on { color: #1B1F2A; border-bottom-color: #0FA36B; }
    .tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
    .tbl th { text-align: left; font-size: 12px; color: #6C7280; font-weight: 600; padding: 0 12px 12px 0; border-bottom: 1px solid #EAECF0; }
    .tbl td { padding: 14px 12px 14px 0; border-bottom: 1px solid #F1F3F5; vertical-align: middle; }
    .tbl tr:last-child td { border-bottom: 0; }
    .tbl .r { text-align: right; padding-right: 0; }
    .sym { font-weight: 700; } .why { color: #3F4552; }
    .btn { display: inline-flex; align-items: center; justify-content: center; height: 44px; padding: 0 20px; border-radius: 10px; font-weight: 700; font-size: 14px; background: #0FA36B; color: #fff; border: 0; }
    .btn.ghost { background: #fff; color: #1B1F2A; border: 1px solid #DADDE3; }
    .fchip { display: inline-flex; align-items: center; height: 34px; padding: 0 14px; border-radius: 999px; border: 1px solid #DADDE3; font-size: 13px; font-weight: 600; color: #3F4552; }
    .fchip.on { background: #1B1F2A; color: #fff; border-color: #1B1F2A; }
    .field { display: flex; flex-direction: column; gap: 6px; }
    .input { height: 46px; border: 1px solid #DADDE3; border-radius: 10px; padding: 0 14px; font-size: 14px; display: flex; align-items: center; color: #1B1F2A; background: #fff; }
    .input.ph { color: #9AA0AE; }
    .idx { display: flex; flex-direction: column; gap: 2px; padding: 12px 16px; border: 1px solid #EAECF0; border-radius: 12px; min-width: 150px; }
    .idx .n { font-size: 12px; color: #6C7280; font-weight: 600; } .idx .v { font-size: 15px; font-weight: 700; }
    .tabm { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; height: 52px; justify-content: center; color: #9AA0AE; font-size: 11px; font-weight: 600; }
    .tabm.on { color: #0FA36B; }
    .tabm svg, .ic { width: 22px; height: 22px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  </style>
</helmet>
'''
FOOT = '''</x-dc>
</body>
</html>
'''
LOGO = '''<svg viewBox="0 0 72 72" style="width: 26px; height: 26px;"><defs><linearGradient id="LG" x1="0" y1="72" x2="72" y2="0" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#087A50"></stop><stop offset="100%" stop-color="#2ECC8F"></stop></linearGradient></defs><g><line x1="15" y1="40" x2="15" y2="62" stroke="url(#LG)" stroke-width="2.6" stroke-linecap="round"></line><rect x="9.25" y="45" width="11.5" height="15" rx="1.8" fill="url(#LG)"></rect><line x1="34" y1="29" x2="34" y2="56" stroke="url(#LG)" stroke-width="2.6" stroke-linecap="round"></line><rect x="28.25" y="34" width="11.5" height="17" rx="1.8" fill="url(#LG)"></rect><line x1="53" y1="18" x2="53" y2="45" stroke="url(#LG)" stroke-width="2.6" stroke-linecap="round"></line><rect x="47.25" y="23" width="11.5" height="17" rx="1.8" fill="url(#LG)"></rect><path d="M9 54 L27 41 L45 30 L60 15" fill="none" stroke="url(#LG)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"></path><path d="M47 13 L62 13 L62 28" fill="none" stroke="url(#LG)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"></path></g></svg>'''
ICONS = {
 "home": '<svg viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"></path></svg>',
 "calls": '<svg viewBox="0 0 24 24"><path d="M4 19h16M6 15l4-5 4 3 5-7"></path></svg>',
 "book": '<svg viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM8 7h8M8 11h8M8 15h5"></path></svg>',
 "record": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>',
}
def topbar(active, h=1000):
    tabs = "".join(f'<a class="tab{" on" if k==active else ""}" href="#">{t}</a>' for k,t in [("home","Home"),("calls","Calls"),("book","Book"),("record","Record")])
    return f'''<div style="width: 1440px; min-height: {h}px; display: flex; flex-direction: column; background: #FFFFFF;">
  <header style="display: flex; align-items: center; gap: 36px; height: 68px; padding: 0 64px; border-bottom: 1px solid #EAECF0;">
    <div style="display: flex; align-items: center; gap: 10px;">{LOGO}<span style="font-size: 19px; font-weight: 800; letter-spacing: -.3px;">TradePilot</span></div>
    <nav style="display: flex; align-items: center; height: 68px;">{tabs}</nav>
    <div style="margin-left: auto; display: flex; align-items: center; gap: 16px;">
      <div style="display: flex; align-items: center; gap: 8px; width: 300px; height: 40px; border: 1px solid #DADDE3; border-radius: 10px; padding: 0 12px; color: #9AA0AE; font-size: 13px;"><svg class="ic" viewBox="0 0 24 24" style="width: 18px; height: 18px;"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>Search a stock or a call</div>
      <span style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: #6C7280; font-weight: 600;"><span style="width: 8px; height: 8px; border-radius: 50%; background: #C4C9D2;"></span>Market closed</span>
      <div style="width: 36px; height: 36px; border-radius: 50%; background: #E6F7EF; color: #0B8F5F; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px;">S</div>
    </div>
  </header>
  <main style="flex: 1; padding: 28px 64px 40px; display: flex; flex-direction: column; gap: 20px;">
'''
END = '''  </main>
</div>
'''
def idxstrip():
    return '''<div style="display: flex; gap: 12px;">
      <div class="idx"><span class="n">NIFTY 50</span><span class="v num">23,897.70 <span class="up" style="font-size: 12px;">+0.10%</span></span></div>
      <div class="idx"><span class="n">SENSEX</span><span class="v num">76,515.00 <span class="up" style="font-size: 12px;">+0.48%</span></span></div>
      <div class="idx"><span class="n">BANK NIFTY</span><span class="v num">57,369.65 <span class="down" style="font-size: 12px;">−0.32%</span></span></div>
      <div class="idx"><span class="n">INDIA VIX</span><span class="v num">20.45 <span class="down" style="font-size: 12px;">−2.1%</span></span></div>
    </div>'''
SPARK = '<svg viewBox="0 0 220 56" style="width: 220px; height: 56px;"><path d="M0 40 L20 36 L40 38 L60 30 L80 32 L100 22 L120 26 L140 18 L160 24 L180 14 L200 20 L220 12" fill="none" stroke="#0FA36B" stroke-width="2.2" stroke-linecap="round"></path><path d="M0 40 L20 36 L40 38 L60 30 L80 32 L100 22 L120 26 L140 18 L160 24 L180 14 L200 20 L220 12 L220 56 L0 56 Z" fill="#0FA36B" opacity=".08"></path></svg>'
CALLS = [
 ("TBZ","buy","BUY","10:24","Reclaimed VWAP on 2.1× volume; sector leading",78,"₹480.85","open","OPEN"),
 ("HFCL","buy","BUY","10:24","Opening-range breakout above 229; buyers held the retest",74,"₹231.44","open","OPEN"),
 ("RRKABEL","sell","SELL","10:24","Broke below the morning low; price −1.4% under VWAP",71,"₹2,522.50","hit","HIT"),
 ("SRF","sell","SELL","09:36","Gap-down continuation; failed to reclaim 2,560",66,"₹2,544.00","miss","MISS"),
 ("PAYTM","buy","BUY","09:36","Held the open above 1,640 with rising volume",64,"₹1,648.60","hit","HIT"),
 ("ECLERX","sell","SELL","15:01","Lost the afternoon support at 1,920 on heavy selling",62,"₹1,922.40","hit","HIT"),
 ("RAYMOND","sell","SELL","10:24","Rejected at 750 twice; sellers in control",60,"₹748.50","ung","UNGRADED"),
]
def call_rows(items):
    return "".join(f'<tr><td style="width: 170px;"><span class="sym">{s}</span> <span class="chip {sc}">{sl}</span><div class="num mut" style="font-size: 12px; margin-top: 2px;">{t}</div></td><td class="why">{w}</td><td class="r num" style="width: 70px;">{sc2}</td><td class="r num" style="width: 120px;">{p}</td><td class="r" style="width: 110px;"><span class="chip {oc}">{ol}</span></td></tr>' for s,sc,sl,t,w,sc2,p,oc,ol in items)
CALL_HEAD = '<thead><tr><th>Stock</th><th>Why</th><th class="r">Score</th><th class="r">Price at call</th><th class="r">Outcome</th></tr></thead>'

pages = {}
# ---------- HOME ----------
pages["Main"] = HEAD + topbar("home", 1000) + f'''
    {idxstrip()}
    <div style="display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 20px;">
      <div class="card" style="display: flex; align-items: center; gap: 24px;">
        <div style="flex: 1; display: flex; flex-direction: column; gap: 8px;">
          <div class="label">Your book</div>
          <div class="num" style="font-size: 38px; font-weight: 800; letter-spacing: -1px; line-height: 1.05;">₹2,71,486</div>
          <div style="display: flex; align-items: center; gap: 10px; font-size: 14px;"><span class="num down" style="font-weight: 700;">−₹1,224 (−0.45%)</span><span class="mut">today</span><span class="mut">·</span><span class="mut">1 price unavailable</span></div>
          <div style="display: flex; gap: 10px; margin-top: 6px;"><a class="btn" href="#" style="height: 40px;">Add a trade</a><a class="btn ghost" href="#" style="height: 40px;">Open book</a></div>
        </div>
        {SPARK}
      </div>
      <div class="card" style="display: flex; flex-direction: column; gap: 8px;">
        <div class="label">Track record</div>
        <div style="font-size: 32px; font-weight: 800; letter-spacing: -.6px; color: #6C7280; line-height: 1.1;">Not yet</div>
        <div class="mut" style="font-size: 14px;"><span class="num" style="color: #1B1F2A; font-weight: 700;">18</span> calls resolved since 28 Aug. We publish a hit rate from <span class="num" style="color: #1B1F2A; font-weight: 700;">100</span>.</div>
        <div style="height: 8px; background: #F1F3F5; border-radius: 4px; margin-top: 6px;"><div style="width: 18%; height: 8px; background: #0FA36B; border-radius: 4px;"></div></div>
        <div class="mut" style="font-size: 12px;">18 of 100</div>
      </div>
    </div>
    <div class="card" style="padding: 0;">
      <div style="display: flex; align-items: center; gap: 12px; padding: 20px 22px 12px;">
        <h2 style="margin: 0; font-size: 18px; font-weight: 800; letter-spacing: -.3px;">Today's calls</h2><span class="mut" style="font-size: 13px;">from Thursday's close · 5 published</span>
        <a href="#" style="margin-left: auto; font-weight: 700;">See all</a>
      </div>
      <div style="padding: 0 22px 8px;"><table class="tbl">{CALL_HEAD}<tbody>{call_rows(CALLS[:5])}</tbody></table></div>
    </div>
''' + END + FOOT
# ---------- CALLS ----------
pages["Calls"] = HEAD + topbar("calls", 1000) + f'''
    <div style="display: flex; align-items: flex-end; gap: 16px;">
      <div><h1 style="margin: 0; font-size: 28px; font-weight: 800; letter-spacing: -.6px;">Calls</h1><div class="mut" style="font-size: 14px;">Thursday 4 September · 7 published · market closed, showing the last session</div></div>
      <div style="margin-left: auto; display: flex; gap: 8px;"><span class="fchip on">All 7</span><span class="fchip">Open 2</span><span class="fchip">Hit 3</span><span class="fchip">Miss 1</span><span class="fchip">Ungraded 1</span></div>
    </div>
    <div class="card" style="padding: 8px 22px;"><table class="tbl">{CALL_HEAD}<tbody>{call_rows(CALLS)}</tbody></table></div>
    <div class="card tint" style="display: flex; align-items: center; gap: 14px;">
      <svg class="ic" viewBox="0 0 24 24" style="color: #6C7280;"><circle cx="12" cy="12" r="9"></circle><path d="M12 8v5M12 16h.01"></path></svg>
      <div class="mut" style="font-size: 13px;">A call is a published idea with a target and a stop. It becomes HIT or MISS only when price reaches one of them. Nothing here is a recommendation to buy or sell.</div>
    </div>
''' + END + FOOT
# ---------- CALL DETAIL ----------
pages["CallDetail"] = HEAD + topbar("calls", 1000) + f'''
    <a href="#" style="font-weight: 700; font-size: 13px;">← All calls</a>
    <div style="display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 20px;">
      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div class="card" style="display: flex; flex-direction: column; gap: 14px;">
          <div style="display: flex; align-items: center; gap: 12px;"><h1 style="margin: 0; font-size: 30px; font-weight: 800; letter-spacing: -.6px;">TBZ</h1><span class="chip buy" style="height: 28px; font-size: 12px;">BUY</span><span class="chip open" style="height: 28px; font-size: 12px;">OPEN</span><span class="mut num" style="margin-left: auto; font-size: 13px;">Published 4 Sep · 10:24</span></div>
          <div style="display: flex; align-items: baseline; gap: 14px;"><span class="num" style="font-size: 34px; font-weight: 800; letter-spacing: -.8px;">₹480.85</span><span class="mut">price at call</span><span class="num up" style="font-weight: 700;">₹484.10 now · +0.7%</span></div>
          <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;">
            <div class="card tint" style="padding: 14px 16px;"><div class="label">Entry</div><div class="num" style="font-size: 20px; font-weight: 700;">₹480.85</div></div>
            <div class="card tint" style="padding: 14px 16px;"><div class="label">Target</div><div class="num up" style="font-size: 20px; font-weight: 700;">₹490.50 <span style="font-size: 12px;">+2.0%</span></div></div>
            <div class="card tint" style="padding: 14px 16px;"><div class="label">Stop</div><div class="num down" style="font-size: 20px; font-weight: 700;">₹478.40 <span style="font-size: 12px;">−0.5%</span></div></div>
          </div>
        </div>
        <div class="card" style="display: flex; flex-direction: column; gap: 10px;">
          <h2 style="margin: 0; font-size: 16px; font-weight: 800;">Why this call</h2>
          <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #3F4552;">Reclaimed VWAP on 2.1× the usual volume while the sector was leading. Buyers defended the morning low at 478 twice before the breakout. Score <span class="num" style="font-weight: 700; color: #1B1F2A;">78</span> out of 100 — the higher the score, the more of our checks lined up.</p>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;"><span class="fchip" style="height: 30px; font-size: 12px;">Above VWAP</span><span class="fchip" style="height: 30px; font-size: 12px;">Volume 2.1×</span><span class="fchip" style="height: 30px; font-size: 12px;">Sector leading</span><span class="fchip" style="height: 30px; font-size: 12px;">Held the retest</span></div>
        </div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div class="card" style="display: flex; flex-direction: column; gap: 10px;">
          <div class="label">Price since the call</div>
          <svg viewBox="0 0 320 120" style="width: 100%; height: 120px;"><line x1="0" y1="64" x2="320" y2="64" stroke="#DADDE3" stroke-dasharray="4 4"></line><text x="4" y="58" font-size="10" fill="#9AA0AE" font-family="JetBrains Mono, monospace">480.85 call</text><line x1="0" y1="18" x2="320" y2="18" stroke="#0FA36B" stroke-dasharray="4 4" opacity=".6"></line><text x="4" y="14" font-size="10" fill="#0FA36B" font-family="JetBrains Mono, monospace">490.50 target</text><line x1="0" y1="104" x2="320" y2="104" stroke="#E04A3C" stroke-dasharray="4 4" opacity=".6"></line><text x="4" y="116" font-size="10" fill="#E04A3C" font-family="JetBrains Mono, monospace">478.40 stop</text><path d="M0 64 L30 70 L60 58 L90 62 L120 50 L150 56 L180 44 L210 52 L240 46 L270 40 L300 48 L320 42" fill="none" stroke="#1B1F2A" stroke-width="2"></path></svg>
          <div class="mut" style="font-size: 12px;">Closed at ₹484.10 on Thursday. Open until target or stop is reached, or 5 sessions pass.</div>
        </div>
        <div class="card" style="display: flex; flex-direction: column; gap: 12px;">
          <div class="label">Timeline</div>
          <div style="display: flex; gap: 12px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #0FA36B; margin-top: 5px;"></span><div><div style="font-weight: 700;">Published</div><div class="mut num" style="font-size: 12px;">Thu 4 Sep · 10:24 · ₹480.85</div></div></div>
          <div style="display: flex; gap: 12px;"><span style="width: 10px; height: 10px; border-radius: 50%; background: #C4C9D2; margin-top: 5px;"></span><div><div style="font-weight: 700; color: #6C7280;">Outcome</div><div class="mut" style="font-size: 12px;">Not yet — still open</div></div></div>
        </div>
        <a class="btn" href="#">Add to my book at ₹484.10</a>
      </div>
    </div>
''' + END + FOOT
# ---------- BOOK ----------
pages["Book"] = HEAD + topbar("book", 1000) + '''
    <div style="display: flex; align-items: flex-end; gap: 16px;"><div><h1 style="margin: 0; font-size: 28px; font-weight: 800; letter-spacing: -.6px;">Your book</h1><div class="mut" style="font-size: 14px;">Marked to Thursday's close · 13 positions</div></div></div>
    <div style="display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 20px; align-items: start;">
      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;">
          <div class="card" style="padding: 16px 18px;"><div class="label">Value</div><div class="num" style="font-size: 26px; font-weight: 800; letter-spacing: -.5px;">₹2,71,486</div></div>
          <div class="card" style="padding: 16px 18px;"><div class="label">Today</div><div class="num down" style="font-size: 26px; font-weight: 800; letter-spacing: -.5px;">−₹1,224</div></div>
          <div class="card" style="padding: 16px 18px;"><div class="label">Priced</div><div class="num" style="font-size: 26px; font-weight: 800; letter-spacing: -.5px;">12 <span class="mut" style="font-size: 13px; font-weight: 600;">of 13</span></div></div>
        </div>
        <div class="card" style="padding: 8px 22px;">
          <div style="display: flex; align-items: center; gap: 10px; padding: 12px 0 4px;"><h2 style="margin: 0; font-size: 15px; font-weight: 800;">From calls</h2><span class="mut" style="font-size: 12px;">9 positions</span></div>
          <table class="tbl"><thead><tr><th>Stock</th><th>Since</th><th class="r">Qty</th><th class="r">Avg</th><th class="r">Last</th><th class="r">P&amp;L</th><th class="r"></th></tr></thead><tbody>
            <tr><td class="sym">ADANIENSOL</td><td class="mut">4 Sep</td><td class="r num">16</td><td class="r num">₹1,406.50</td><td class="r num">₹1,412.10</td><td class="r num up" style="font-weight: 700;">+₹90 <span class="mut" style="font-weight: 400;">+0.4%</span></td><td class="r"><a href="#" style="font-size: 12px; color: #6C7280;">Remove</a></td></tr>
            <tr><td class="sym">TBZ</td><td class="mut">4 Sep</td><td class="r num">66</td><td class="r num">₹480.85</td><td class="r num">₹484.10</td><td class="r num up" style="font-weight: 700;">+₹214 <span class="mut" style="font-weight: 400;">+0.7%</span></td><td class="r"><a href="#" style="font-size: 12px; color: #6C7280;">Remove</a></td></tr>
            <tr><td class="sym">DEEPINDS</td><td class="mut">4 Sep</td><td class="r num">35</td><td class="r num">₹791.75</td><td class="r num">₹784.20</td><td class="r num down" style="font-weight: 700;">−₹264 <span class="mut" style="font-weight: 400;">−1.0%</span></td><td class="r"><a href="#" style="font-size: 12px; color: #6C7280;">Remove</a></td></tr>
            <tr><td class="sym">HFCL</td><td class="mut">4 Sep</td><td class="r num">80</td><td class="r num">₹231.44</td><td class="r num">₹229.90</td><td class="r num down" style="font-weight: 700;">−₹123 <span class="mut" style="font-weight: 400;">−0.7%</span></td><td class="r"><a href="#" style="font-size: 12px; color: #6C7280;">Remove</a></td></tr>
          </tbody></table>
          <div style="display: flex; align-items: center; gap: 10px; padding: 18px 0 4px;"><h2 style="margin: 0; font-size: 15px; font-weight: 800;">Logged by you</h2><span class="mut" style="font-size: 12px;">4 positions</span></div>
          <table class="tbl"><tbody>
            <tr><td class="sym" style="width: 170px;">KSHINTL</td><td class="mut">2 Sep</td><td class="r num">22</td><td class="r num">₹1,088.85</td><td class="r mut">price unavailable</td><td class="r mut">—</td><td class="r"><a href="#" style="font-size: 12px; color: #6C7280;">Remove</a></td></tr>
            <tr><td class="sym">PAISALO</td><td class="mut">1 Sep</td><td class="r num">287</td><td class="r num">₹73.94</td><td class="r num">₹75.10</td><td class="r num up" style="font-weight: 700;">+₹333 <span class="mut" style="font-weight: 400;">+1.6%</span></td><td class="r"><a href="#" style="font-size: 12px; color: #6C7280;">Remove</a></td></tr>
          </tbody></table>
        </div>
      </div>
      <div class="card" style="display: flex; flex-direction: column; gap: 14px; position: sticky; top: 20px;">
        <h2 style="margin: 0; font-size: 16px; font-weight: 800;">Add a trade</h2>
        <div class="mut" style="font-size: 13px;">Log something you bought outside a call. It joins your book at the price you paid.</div>
        <div class="field"><span class="label">Stock</span><div class="input ph">Search NSE symbol</div></div>
        <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px;">
          <div class="field"><span class="label">Quantity</span><div class="input ph">0</div></div>
          <div class="field"><span class="label">Price paid</span><div class="input ph">₹0.00</div></div>
        </div>
        <div class="field"><span class="label">Date</span><div class="input num">05 Sep 2026</div></div>
        <a class="btn" href="#">Add to book</a>
        <div class="mut" style="font-size: 12px;">No orders are placed. Your book is a record, not a broker.</div>
      </div>
    </div>
''' + END + FOOT
# ---------- RECORD ----------
pages["Record"] = HEAD + topbar("record", 1000) + '''
    <div><h1 style="margin: 0; font-size: 28px; font-weight: 800; letter-spacing: -.6px;">Track record</h1><div class="mut" style="font-size: 14px;">Every call we publish is graded against its own target and stop. Nothing is removed.</div></div>
    <div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px;">
      <div class="card" style="display: flex; flex-direction: column; gap: 10px;">
        <div class="label">Hit rate</div>
        <div style="font-size: 44px; font-weight: 800; letter-spacing: -1px; color: #6C7280; line-height: 1;">Not yet</div>
        <div style="font-size: 15px; color: #3F4552;"><span class="num" style="font-weight: 800; color: #1B1F2A;">18</span> calls resolved since 28 Aug. We publish a hit rate from <span class="num" style="font-weight: 800; color: #1B1F2A;">100</span> resolved calls, because a percentage over a handful of trades is the easiest number in finance to fool yourself with.</div>
        <div style="height: 10px; background: #F1F3F5; border-radius: 5px; margin-top: 6px;"><div style="width: 18%; height: 10px; background: #0FA36B; border-radius: 5px;"></div></div>
        <div style="display: flex; justify-content: space-between;" class="mut num"><span>18 resolved</span><span>100</span></div>
      </div>
      <div class="card" style="display: flex; flex-direction: column; gap: 14px;">
        <div class="label">All calls so far · 31</div>
        <div style="display: flex; flex-direction: column; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 12px;"><span style="width: 90px; font-weight: 700;">Hit</span><div style="flex: 1; height: 12px; background: #F1F3F5; border-radius: 6px;"><div style="width: 39%; height: 12px; background: #0FA36B; border-radius: 6px;"></div></div><span class="num" style="width: 30px; text-align: right; font-weight: 700;">12</span></div>
          <div style="display: flex; align-items: center; gap: 12px;"><span style="width: 90px; font-weight: 700;">Miss</span><div style="flex: 1; height: 12px; background: #F1F3F5; border-radius: 6px;"><div style="width: 19%; height: 12px; background: #E04A3C; border-radius: 6px;"></div></div><span class="num" style="width: 30px; text-align: right; font-weight: 700;">6</span></div>
          <div style="display: flex; align-items: center; gap: 12px;"><span style="width: 90px; font-weight: 700;">Ungraded</span><div style="flex: 1; height: 12px; background: #F1F3F5; border-radius: 6px;"><div style="width: 16%; height: 12px; background: #C4C9D2; border-radius: 6px;"></div></div><span class="num" style="width: 30px; text-align: right; font-weight: 700;">5</span></div>
          <div style="display: flex; align-items: center; gap: 12px;"><span style="width: 90px; font-weight: 700;">Open</span><div style="flex: 1; height: 12px; background: #F1F3F5; border-radius: 6px;"><div style="width: 26%; height: 12px; background: #4A55C7; border-radius: 6px;"></div></div><span class="num" style="width: 30px; text-align: right; font-weight: 700;">8</span></div>
        </div>
        <div class="mut" style="font-size: 12px;">Ungraded means price never reached target or stop within 5 sessions. It counts as resolved, not as a hit.</div>
      </div>
    </div>
    <div class="card" style="padding: 8px 22px;">
      <div style="display: flex; align-items: center; gap: 10px; padding: 12px 0 4px;"><h2 style="margin: 0; font-size: 15px; font-weight: 800;">Resolved calls</h2><span class="mut" style="font-size: 12px;">newest first</span></div>
      <table class="tbl"><thead><tr><th>Stock</th><th>Published</th><th class="r">Price at call</th><th class="r">Target</th><th class="r">Stop</th><th class="r">Resolved at</th><th class="r">Outcome</th></tr></thead><tbody>
        <tr><td><span class="sym">RRKABEL</span> <span class="chip sell">SELL</span></td><td class="mut num">4 Sep 10:24</td><td class="r num">₹2,522.50</td><td class="r num">₹2,472.05</td><td class="r num">₹2,535.11</td><td class="r num">₹2,468.00 · 11:25</td><td class="r"><span class="chip hit">HIT</span></td></tr>
        <tr><td><span class="sym">SRF</span> <span class="chip sell">SELL</span></td><td class="mut num">4 Sep 09:36</td><td class="r num">₹2,544.00</td><td class="r num">₹2,493.12</td><td class="r num">₹2,569.44</td><td class="r num">₹2,581.60 · 10:06</td><td class="r"><span class="chip miss">MISS</span></td></tr>
        <tr><td><span class="sym">PAYTM</span> <span class="chip buy">BUY</span></td><td class="mut num">4 Sep 09:36</td><td class="r num">₹1,648.60</td><td class="r num">₹1,681.57</td><td class="r num">₹1,640.36</td><td class="r num">₹1,682.10 · 11:12</td><td class="r"><span class="chip hit">HIT</span></td></tr>
        <tr><td><span class="sym">RAYMOND</span> <span class="chip sell">SELL</span></td><td class="mut num">4 Sep 10:24</td><td class="r num">₹748.50</td><td class="r num">₹733.53</td><td class="r num">₹752.24</td><td class="r num">— · 5 sessions</td><td class="r"><span class="chip ung">UNGRADED</span></td></tr>
      </tbody></table>
    </div>
''' + END + FOOT
# ---------- SIGN IN ----------
pages["SignIn"] = HEAD + f'''<div style="width: 1440px; height: 900px; display: flex; background: #FFFFFF;">
  <div style="width: 560px; flex: none; background: #F6F8FA; display: flex; flex-direction: column; justify-content: space-between; padding: 48px 56px;">
    <div style="display: flex; align-items: center; gap: 10px;">{LOGO}<span style="font-size: 19px; font-weight: 800; letter-spacing: -.3px;">TradePilot</span></div>
    <div style="display: flex; flex-direction: column; gap: 18px;">
      <h1 style="margin: 0; font-size: 36px; font-weight: 800; letter-spacing: -1px; line-height: 1.15;">Every call we make, graded in public.</h1>
      <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #3F4552;">Intraday calls with a target and a stop, a book that marks your positions to market, and a track record we only publish once it means something.</p>
      <div style="display: flex; gap: 12px;"><div class="card" style="padding: 14px 16px; flex: 1;"><div class="label">Calls published</div><div class="num" style="font-size: 22px; font-weight: 800;">31</div></div><div class="card" style="padding: 14px 16px; flex: 1;"><div class="label">Resolved</div><div class="num" style="font-size: 22px; font-weight: 800;">18 <span class="mut" style="font-size: 12px; font-weight: 600;">of 100</span></div></div></div>
    </div>
    <div class="mut" style="font-size: 12px;">Paper record. Not investment advice. [SEBI STATUS LINE]</div>
  </div>
  <div style="flex: 1; display: flex; align-items: center; justify-content: center;">
    <div style="width: 400px; display: flex; flex-direction: column; gap: 18px;">
      <div><h2 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -.5px;">Sign in</h2><div class="mut" style="font-size: 14px;">Members only for now. <a href="#" style="font-weight: 700;">Join the waitlist</a></div></div>
      <div class="field"><span class="label">Email</span><div class="input">soumya@sidewall.in</div></div>
      <div class="field"><span class="label">Password</span><div class="input num">••••••••••••</div></div>
      <a class="btn" href="#">Sign in</a>
      <div style="display: flex; justify-content: space-between; font-size: 13px;"><a href="#" style="font-weight: 600;">Forgot password?</a><a href="#" style="font-weight: 600;">Have an invite?</a></div>
    </div>
  </div>
</div>
''' + FOOT
# ---------- PHONE HOME ----------
def phone(active, body):
    tabs = "".join(f'<a class="tabm{" on" if k==active else ""}" href="#">{ICONS[k]}{t}</a>' for k,t in [("home","Home"),("calls","Calls"),("book","Book"),("record","Record")])
    return HEAD + f'''<div style="width: 390px; height: 844px; display: flex; flex-direction: column; background: #FFFFFF; overflow: hidden;">
  <header style="display: flex; align-items: center; gap: 10px; height: 52px; padding: 0 16px; margin-top: 44px;">
    {LOGO}<span style="font-size: 17px; font-weight: 800; letter-spacing: -.3px;">TradePilot</span>
    <div style="margin-left: auto; width: 32px; height: 32px; border-radius: 50%; background: #E6F7EF; color: #0B8F5F; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 12px;">S</div>
  </header>
  <main style="flex: 1; min-height: 0; overflow: hidden; padding: 8px 16px 0; display: flex; flex-direction: column; gap: 12px;">
{body}
  </main>
  <nav style="display: flex; background: #fff; border-top: 1px solid #EAECF0; padding: 6px 8px 22px;">{tabs}</nav>
</div>
''' + FOOT
def mrow(s,sc,sl,w,p,oc,ol):
    return f'''<div style="display: flex; align-items: center; gap: 10px; min-height: 60px; padding: 8px 0; border-bottom: 1px solid #F1F3F5;">
        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px;">
          <div style="display: flex; align-items: center; gap: 8px;"><span class="sym">{s}</span><span class="chip {sc}" style="height: 20px; font-size: 10px;">{sl}</span><span class="num" style="margin-left: auto; font-size: 13px; font-weight: 600;">{p}</span></div>
          <div class="mut" style="font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{w}</div>
        </div><span class="chip {oc}" style="height: 20px; font-size: 10px;">{ol}</span></div>'''
pages["HomePhone"] = phone("home", f'''
    <div style="display: flex; gap: 8px; overflow: hidden;"><div class="idx" style="min-width: 0; flex: 1; padding: 10px 12px;"><span class="n">NIFTY 50</span><span class="v num" style="font-size: 14px;">23,897 <span class="up" style="font-size: 11px;">+0.1%</span></span></div><div class="idx" style="min-width: 0; flex: 1; padding: 10px 12px;"><span class="n">SENSEX</span><span class="v num" style="font-size: 14px;">76,515 <span class="up" style="font-size: 11px;">+0.5%</span></span></div></div>
    <div class="card" style="padding: 16px 18px; display: flex; flex-direction: column; gap: 6px;">
      <div class="label">Your book</div>
      <div class="num" style="font-size: 32px; font-weight: 800; letter-spacing: -.8px; line-height: 1.05;">₹2,71,486</div>
      <div style="font-size: 13px;"><span class="num down" style="font-weight: 700;">−₹1,224 (−0.45%)</span> <span class="mut">today</span></div>
      <div style="display: flex; gap: 8px; margin-top: 8px;"><a class="btn" href="#" style="flex: 1; height: 40px;">Add a trade</a><a class="btn ghost" href="#" style="flex: 1; height: 40px;">Open book</a></div>
    </div>
    <div class="card" style="padding: 14px 18px; display: flex; align-items: center; gap: 12px;">
      <div style="flex: 1; display: flex; flex-direction: column; gap: 4px;"><div class="label">Track record</div><div class="mut" style="font-size: 12px;"><span class="num" style="color: #1B1F2A; font-weight: 700;">18</span> resolved · hit rate from <span class="num" style="color: #1B1F2A; font-weight: 700;">100</span></div><div style="height: 6px; background: #F1F3F5; border-radius: 3px;"><div style="width: 18%; height: 6px; background: #0FA36B; border-radius: 3px;"></div></div></div>
      <div style="font-size: 18px; font-weight: 800; color: #6C7280;">Not yet</div>
    </div>
    <div class="card" style="padding: 12px 18px 2px;">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;"><h2 style="margin: 0; font-size: 15px; font-weight: 800;">Today's calls</h2><a href="#" style="margin-left: auto; font-weight: 700; font-size: 13px;">See all</a></div>
      {mrow("TBZ","buy","BUY","Reclaimed VWAP on 2.1× volume; sector leading","₹480.85","open","OPEN")}
      {mrow("HFCL","buy","BUY","Opening-range breakout above 229; held the retest","₹231.44","open","OPEN")}
      {mrow("RRKABEL","sell","SELL","Broke below the morning low; −1.4% under VWAP","₹2,522.50","hit","HIT")}
    </div>
''')
pages["CallsPhone"] = phone("calls", f'''
    <div><h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -.5px;">Calls</h1><div class="mut" style="font-size: 12px;">Thursday's session · 7 published</div></div>
    <div style="display: flex; gap: 8px; overflow: hidden;"><span class="fchip on" style="height: 32px; font-size: 12px;">All 7</span><span class="fchip" style="height: 32px; font-size: 12px;">Open 2</span><span class="fchip" style="height: 32px; font-size: 12px;">Hit 3</span><span class="fchip" style="height: 32px; font-size: 12px;">Miss 1</span></div>
    <div class="card" style="padding: 4px 18px;">
      {"".join(mrow(s,sc,sl,w,p,oc,ol) for s,sc,sl,t,w,sc2,p,oc,ol in CALLS[:7])}
    </div>
''')
for name, html in pages.items():
    open(f"{name}.dc.html", "w").write(html)
print("wrote", ", ".join(pages))
