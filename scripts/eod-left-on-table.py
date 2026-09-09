#!/usr/bin/env python3
"""
eod-left-on-table — the EOD report Soumya asked for on 2026-09-04: scoreboard per engine,
"left on the table" measured by replaying every closed trade against Kite 5-min candles,
BUY signals nobody took, ops notes, and candlestick charts (green entry / purple exit).

  python3 scripts/eod-replay-candles.py <out.json> <date> v5,v5_wide      # step 1: replay
  python3 scripts/eod-left-on-table.py <date> <replay.json> [notes.json]  # step 2: render

Pyppeteer PDF per project rule (never weasyprint). Output: docs/watchdog/reports/<date>_eod/left-on-table.{html,pdf}
"""
import json, sys, re, asyncio, collections
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, pandas as pd, mplfinance as mpf

ROOT = Path(__file__).resolve().parent.parent
DATE = sys.argv[1]; L = json.load(open(sys.argv[2]))
NOTES = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else []
OUT = ROOT / "docs/watchdog/reports" / f"{DATE}_eod"; CH = OUT / "charts"; CH.mkdir(parents=True, exist_ok=True)
ENGINES = list(L["engines"].keys())
EJ = {e: json.load(open(ROOT / "docs/paper-trades" / e / f"{DATE}.json")) for e in ENGINES}
GREEN, PURPLE, RED = "#16a34a", "#7c3aed", "#dc2626"
NOTIONAL = 11000
SHORT = {"FLAT_FORCE_EXIT": "FLAT", "SIGNAL_FLIP": "FLIP", "STOPLOSS": "STOP", "TIME_EXIT": "TIME", "TARGET": "TGT"}
DAY = pd.Timestamp(DATE).strftime("%a %-d %b %Y")

def fmt(x): return f"{'−' if x < 0 else '+' if x > 0 else ''}Rs {abs(x):,.0f}"
def cls(x): return "neg" if x < 0 else "pos"

def chart(t, fn):
    c = L["candles"].get(t["symbol"])
    if not c: return False
    df = pd.DataFrame(c); df.index = pd.to_datetime(DATE + " " + df["t"])
    df = df.rename(columns=dict(o="Open", h="High", l="Low", c="Close"))[["Open", "High", "Low", "Close"]].astype(float)
    ent = df.index[df.index >= pd.Timestamp(DATE + " " + t["entry_time"])]; ent = ent[0] if len(ent) else df.index[0]
    ex = df.index[df.index >= pd.Timestamp(DATE + " " + t["exit_time"])]; ex = ex[0] if len(ex) else df.index[-1]
    e_s = pd.Series(float("nan"), index=df.index); x_s = e_s.copy(); x_s[ex] = t["exit"]
    if not t.get("carried"): e_s[ent] = t["entry"]
    mc = mpf.make_marketcolors(up=GREEN, down=RED, edge="inherit", wick="inherit")
    st = mpf.make_mpf_style(marketcolors=mc, gridstyle=":", facecolor="white", rc={"font.size": 8})
    ap = [mpf.make_addplot(x_s, type="scatter", markersize=140, marker="v" if t["dir"] == "LONG" else "^", color=PURPLE)]
    if not t.get("carried"):
        ap.insert(0, mpf.make_addplot(e_s, type="scatter", markersize=140, marker="^" if t["dir"] == "LONG" else "v", color=GREEN))
    fig, axes = mpf.plot(df, type="candle", style=st, addplot=ap, returnfig=True, figsize=(5.2, 3.0), datetime_format="%H:%M", xrotation=0)
    ax = axes[0]; ax.axhline(t["entry"], color=GREEN, lw=0.8, ls="--", alpha=.7); ax.axhline(t["exit"], color=PURPLE, lw=0.8, ls="--", alpha=.7)
    ax.set_title(f"{t['symbol']}  {t['dir']}  x{t['qty']}{'  (carried from prev session)' if t.get('carried') else ''}   {t['reason']}   P&L {fmt(t['pnl'])}   after exit: best {fmt(t.get('best_after_exit', 0))}", fontsize=8, loc="left")
    ax.set_ylabel(""); fig.savefig(fn, dpi=150, bbox_inches="tight"); plt.close(fig); return True

def score(e):
    s = EJ[e]["summary"]; v = L["engines"][e]
    exits = collections.defaultdict(lambda: [0, 0.0])
    for p in EJ[e]["pools"].values():
        for t in p.get("closed", []): exits[t["reason"]][0] += 1; exits[t["reason"]][1] += t["pnl"]
    ex = "".join(f"<tr><td>{k}</td><td>{n}</td><td class='{cls(x)}'>{fmt(x)}</td></tr>" for k, (n, x) in sorted(exits.items(), key=lambda kv: kv[1][1]))
    sl = v["stoploss_then_reversed"]; wr = 100 * s["wins"] / s["trades"] if s["trades"] else 0
    return f"""<div class="eng"><h3>{e} <span class="muted">{EJ[e].get('regime','')}</span></h3>
<table class="kv"><tr><td>Gross P&L</td><td class="{cls(s['total_pnl'])} big">{fmt(s['total_pnl'])}</td></tr>
<tr><td>Net of costs</td><td class="{cls(s['total_pnl_net'])}">{fmt(s['total_pnl_net'])} <span class="muted">(costs Rs {s['total_cost']:,.0f})</span></td></tr>
<tr><td>Trades</td><td>{s['trades']} &nbsp; L {s['longs']} / S {s['shorts']}</td></tr>
<tr><td>Win rate</td><td>{wr:.0f}% <span class="muted">({s['wins']}W / {s['losses']}L)</span></td></tr></table>
<table class="t"><tr><th>Exit reason</th><th>#</th><th>P&L</th></tr>{ex}</table>
<h4>Left on the table</h4><table class="kv">
<tr><td>Held everything to 15:15 instead of exiting</td><td class="{cls(v['hold_delta'])}">{fmt(v['hold_delta'])}</td></tr>
<tr><td>Stop-losses that later reversed our way ({len(sl)})</td><td class="pos">{fmt(sum(t['hold_delta'] for t in sl))}</td></tr>
<tr><td>Perfect-exit ceiling after our exits <span class="muted">(upper bound)</span></td><td>{fmt(v['best_case_after_exit'])}</td></tr>
<tr><td>Max favourable excursion from entry</td><td>{fmt(v['mfe_total'])}</td></tr></table></div>"""


# ── experiments section (2026-09-08): DAYGAIN baseline row, arm-band ledger, regime shadow ──
def experiments_html():
    parts = []
    bf = ROOT / "docs/research/daygain/baseline" / f"{DATE}.json"
    if bf.exists():
        b = json.loads(bf.read_text()); e_ = b.get("eod") or {}
        if e_:
            row = "".join(f"<tr><td>{e}</td><td class='{cls(EJ[e]['summary']['total_pnl_net'])}'>{fmt(EJ[e]['summary']['total_pnl_net'])}</td></tr>" for e in ENGINES)
            parts.append(f"<div><h3>DAYGAIN baseline (computed, no orders)</h3><table class='kv'><tr><td>Top-10 gainers 09:35 → 15:15, −3% stop</td><td class='{cls(e_['net'])}'>{fmt(e_['net'])} <span class='muted'>({e_['stops']} stops of {e_['priced']})</span></td></tr>{row}</table><p class='muted'>Did our scoring beat dumb? Positive engine minus baseline = yes.</p></div>")
    af = ROOT / "docs/research/shadows/armband" / f"{DATE}.json"
    if af.exists():
        a = json.loads(af.read_text()); bands = list(a["bands"])
        rows = "".join(f"<tr><td>{e}</td><td class='{cls(v['live_actual_net'])}'>{fmt(v['live_actual_net'])}</td>" + "".join(f"<td class='{cls(v['bands'][k]['net'])}'>{fmt(v['bands'][k]['net'])}</td>" for k in bands) + "</tr>" for e, v in a["engines"].items())
        parts.append(f"<div><h3>Arm-band shadow (replayed)</h3><table class='t'><tr><th>Engine</th><th>Actual</th>{''.join(f'<th>{k}</th>' for k in bands)}</tr>{rows}</table><p class='muted'>Same entries, stops, targets; only the trailing arm differs. Compare bands to the replayed 'live' column, not to actual.</p></div>")
    rf = ROOT / "docs/research/shadows/regime" / f"{DATE}.json"
    if rf.exists():
        r = json.loads(rf.read_text())
        parts.append(f"<div><h3>Regime shadow (v5)</h3><table class='kv'><tr><td>Live regime {r['live_regime']} book</td><td class='{cls(r['live_book_net'])}'>{fmt(r['live_book_net'])}</td></tr><tr><td>Alternate {r['alt_regime']} book</td><td class='{cls(r['alt_book_net'])}'>{fmt(r['alt_book_net'])}</td></tr><tr><td>Alternate − live</td><td class='{cls(r['alt_minus_live'])}'>{fmt(r['alt_minus_live'])}</td></tr><tr><td>Snapshots · common trades · only-live · only-alt</td><td>{r['snapshots']} · {r['common_trades']} · {len(r['live_only'])} · {len(r['alt_only'])}</td></tr></table><p class='muted'>Gate after 10 sessions: alternate beats live by more than Rs 2,000 cumulative net → rebuild the classifier.</p></div>")
    return f"<h2>5. Experiments (pre-registered 2026-09-08)</h2><div class='grid'>{''.join(parts)}</div>" if parts else ""

rows_html, chart_html = {}, {}
for e in ENGINES:
    tr = [t for t in L["engines"][e]["trades"] if "best_after_exit" in t]
    top = sorted(tr, key=lambda t: -t["best_after_exit"])[:4]
    cards = [f'<div class="card"><img src="charts/lot_{e}_{i}_{t["symbol"]}.png"></div>' for i, t in enumerate(top) if chart(t, CH / f"lot_{e}_{i}_{t['symbol']}.png")]
    chart_html[e] = "".join(cards)
    rows_html[e] = "".join(f"<tr><td>{t['symbol']}</td><td>{t['dir']}</td><td>{SHORT.get(t['reason'], t['reason'])}</td><td>{'c/f' if t.get('carried') else t['entry_time'][:5]}→{t['exit_time'][:5]}</td><td class='{cls(t['pnl'])}'>{fmt(t['pnl'])}</td><td class='{cls(t['hold_delta'])}'>{fmt(t['hold_delta'])}</td><td>{fmt(t['best_after_exit'])}</td></tr>" for t in sorted(tr, key=lambda t: -t['best_after_exit'])[:8])

# missed BUYs from missed-trades-report.py output
missed, right, neutral, total_missed = [], 0, 0, 0
mf = ROOT / "docs/reports" / f"missed-trades-{DATE}.md"
if mf.exists():
    md = mf.read_text()
    m = re.search(r"Missed by ALL engines \| (\d+)", md); total_missed = int(m.group(1)) if m else 0
    m = re.search(r"Right call[^|]*\| (\d+)", md); right = int(m.group(1)) if m else 0
    m = re.search(r"Neutral[^|]*\| (\d+)", md); neutral = int(m.group(1)) if m else 0
    for s_, p in re.findall(r"^\| ([A-Z0-9&-]+) \| ([+-][0-9.]+)% \|$", md, re.M):
        if float(p) > 0.5: missed.append((s_, float(p)))
missed_rows = "".join(f"<tr><td>{s_}</td><td>+{p:.2f}%</td><td>{fmt(NOTIONAL*p/100)}</td></tr>" for s_, p in missed)
missed_total = sum(NOTIONAL * p / 100 for _, p in missed)
notes_html = "".join(f"<li>{n}</li>" for n in NOTES)
gross = sum(EJ[e]["summary"]["total_pnl"] for e in ENGINES); net = sum(EJ[e]["summary"]["total_pnl_net"] for e in ENGINES)
sl_all = [t for e in ENGINES for t in L["engines"][e]["stoploss_then_reversed"]]; sl_rev = sum(t["hold_delta"] for t in sl_all)
n_sl = sum(sum(1 for p in EJ[e]["pools"].values() for t in p.get("closed", []) if t["reason"] == "STOPLOSS") for e in ENGINES)
sl_cost = sum(t["pnl"] for e in ENGINES for p in EJ[e]["pools"].values() for t in p.get("closed", []) if t["reason"] == "STOPLOSS")
ceiling = sum(L["engines"][e]["best_case_after_exit"] for e in ENGINES)
eng_line = " · ".join(f"{e} {fmt(EJ[e]['summary']['total_pnl_net'])} net" for e in ENGINES)

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>TradePilot EOD {DATE}</title><style>
@page {{ size: A4; margin: 14mm 12mm; }}
body {{ font-family: 'Avenir Next','Avenir',Helvetica,Arial,sans-serif; color:#1e1b4b; font-size:10.5pt; line-height:1.45; margin:0; }}
h1 {{ font-size:22pt; margin:0 0 2px; }} h2 {{ font-size:14pt; margin:14px 0 6px; border-bottom:2px solid #4f46e5; padding-bottom:3px; }} h3 {{ margin:6px 0 4px; font-size:12pt; color:#4f46e5; page-break-after:avoid; break-after:avoid }} h4 {{ margin:8px 0 3px; font-size:10.5pt }}
.hdr {{ background:linear-gradient(135deg,#1e1b4b,#4338ca); color:white; padding:18px 20px; border-radius:10px; margin-bottom:12px }} .hdr .sub {{ opacity:.85; font-size:10pt }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px }} .grid3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px }} .eng {{ border:1px solid #e0e7ff; border-radius:8px; padding:8px 10px; page-break-inside:avoid }}
table {{ border-collapse:collapse; width:100%; font-size:9.5pt }} td,th {{ padding:3px 6px; border-bottom:1px solid #eef2ff; text-align:left; vertical-align:top }} th {{ background:#eef2ff; color:#312e81 }}
.kv td:last-child {{ text-align:right; font-weight:600; white-space:nowrap }} .t td:not(:first-child) {{ text-align:right; white-space:nowrap }} .grid .t {{ font-size:8.5pt }} .big {{ font-size:14pt }}
.pos {{ color:{GREEN} }} .neg {{ color:{RED} }} .muted {{ color:#6b7280; font-weight:400; font-size:9pt }}
.cards {{ display:grid; grid-template-columns:1fr 1fr; gap:8px }} .card {{ page-break-inside:avoid }} .card img {{ width:100%; border:1px solid #e5e7eb; border-radius:6px }}
.box {{ background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:8px 12px; margin:8px 0; page-break-inside:avoid }} .warn {{ background:#fff7ed; border-color:#fed7aa }}
.legend span {{ display:inline-block; margin-right:14px }} .sq {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:middle }}
</style></head><body>
<div class="hdr"><h1>TradePilot — End of Day, {DAY}</h1><div class="sub">Paper fleet: {', '.join(ENGINES)} &nbsp;·&nbsp; {eng_line} &nbsp;·&nbsp; Prepared by Sarathi for Soumya Swain</div></div>
<div class="box"><b>Bottom line.</b> Combined gross <b class="{cls(gross)}">{fmt(gross)}</b>, net of costs <b class="{cls(net)}">{fmt(net)}</b>.
{n_sl} stop-outs cost {fmt(sl_cost)}; {len(sl_all)} of them reversed our way after exit, worth {fmt(sl_rev)} had we held.
Realistic money left on the table: <b>about {fmt(sl_rev)}</b> (stops) plus <b>about {fmt(missed_total)}</b> gross on {len(missed)} BUY signals no engine took. Perfect-exit ceiling {fmt(ceiling)} is not a target.</div>
<h2>1. Scoreboard</h2><div class="{'grid3' if len(ENGINES) == 3 else 'grid'}">{''.join(score(e) for e in ENGINES)}</div>
<h2>2. Left on the table — how it was measured</h2>
<p>Every closed trade replayed against Kite 5-minute candles after the close: P&L if held to 15:15 (<b>hold Δ</b>), which stop-losses reversed afterwards, and how far price travelled our way after exit (<b>ceiling</b>). Trades exited at the 15:15 force-close count as zero.</p>
<div class="grid">{''.join(f'<div><h3>{e} — top post-exit moves</h3><table class="t"><tr><th>Stock</th><th>Dir</th><th>Exit</th><th>Time</th><th>P&L</th><th>Hold Δ</th><th>Ceiling</th></tr>{rows_html[e]}</table></div>' for e in ENGINES)}</div>
<h2>3. BUY signals nobody took</h2>
<p>{total_missed} dashboard BUYs skipped by every engine: {len(missed)} rose more than 0.5% (wrong to skip), {right} fell more than 0.5% (right to skip), {neutral} flat. Gross upside on the wrong calls at Rs {NOTIONAL:,} each:</p>
<div class="grid"><table class="t"><tr><th>Stock</th><th>Day move</th><th>At Rs {NOTIONAL//1000}K</th></tr>{missed_rows}<tr><th>Total gross</th><th></th><th>{fmt(missed_total)}</th></tr></table>
<div class="box warn"><b>Ops notes</b><ul style="margin:4px 0 0 16px;padding:0">{notes_html}</ul></div></div>
<h2 style="margin-top:18px">4. The trades that hurt most — candlesticks</h2>
<p class="legend"><span><span class="sq" style="background:{GREEN}"></span>green marker = our entry</span><span><span class="sq" style="background:{RED}"></span>red candle down</span><span><span class="sq" style="background:{PURPLE}"></span>purple marker = our exit</span><span>dashed lines = entry / exit price</span></p>
{''.join(f'<h3>{e}</h3><div class="cards">{chart_html[e]}</div>' for e in ENGINES)}
{experiments_html()}
<p class="muted" style="margin-top:14px">Sources: docs/paper-trades/*/{DATE}.json · Kite historical 5-min · docs/reports/missed-trades-{DATE}.md. Paper trading only, no real orders.</p>
</body></html>"""
(OUT / "left-on-table.html").write_text(html)

async def pdf():
    from pyppeteer import launch
    b = await launch(executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless=True, args=["--no-sandbox", "--disable-gpu"])
    try:
        p = await b.newPage(); await p.goto(f"file://{OUT/'left-on-table.html'}", {"waitUntil": "networkidle0", "timeout": 60000}); await asyncio.sleep(1.5)
        await p.pdf({"path": str(OUT / "left-on-table.pdf"), "printBackground": True, "preferCSSPageSize": True, "displayHeaderFooter": False, "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}})
    finally: await b.close()
asyncio.get_event_loop().run_until_complete(pdf()); print("PDF", OUT / "left-on-table.pdf")
