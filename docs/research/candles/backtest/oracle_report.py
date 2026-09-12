#!/usr/bin/env python3
"""Report 2: "Where the money was, and what the candles looked like".
Reads results/oracle_summary.json + results/oracle_trades.json + ../oracle/{daily,charts}
and writes ../report/where-the-money-was.html, then render with render_pdf.py --which oracle.
"""
from __future__ import annotations
import json, os, glob, collections, datetime as dt
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
REP = os.path.abspath(os.path.join(HERE, "..", "report"))
ORA = os.path.abspath(os.path.join(HERE, "..", "oracle"))
CH = os.path.join(REP, "charts2")
os.makedirs(CH, exist_ok=True)
GREEN, RED, INK, MUT, ACC, AMB, PUR = "#16a34a", "#dc2626", "#1e1b4b", "#6b7280", "#4f46e5", "#d97706", "#7c3aed"
PLABEL = {"hammer": "Hammer", "shooting_star": "Shooting star", "doji_top": "Doji at top", "doji_bottom": "Doji at bottom",
          "pin_bar_bull": "Pin bar bull", "pin_bar_bear": "Pin bar bear", "engulfing_bull": "Engulfing bull", "engulfing_bear": "Engulfing bear",
          "three_bar_rev_bull": "3-bar reversal bull", "three_bar_rev_bear": "3-bar reversal bear", "shrinking_bull": "Shrinking bull", "shrinking_bear": "Shrinking bear",
          "three_bar_cont_bull": "3-bar continuation bull", "three_bar_cont_bear": "3-bar continuation bear", "breakout_bull": "Breakout bull", "breakout_bear": "Breakout bear",
          "bull_flag": "Bull flag", "bear_flag": "Bear flag"}


def lift_chart(rows, title, fname, n_min=200):
    rows = [r for r in rows if r["n"] >= n_min and r["lift"] is not None]
    rows.sort(key=lambda r: r["lift"])
    fig, ax = plt.subplots(figsize=(9, 0.42 * len(rows) + 1.2))
    cols = [GREEN if r["lift"] > 1.2 else (RED if r["lift"] < 0.8 else MUT) for r in rows]
    ax.barh([r["candle"] for r in rows], [r["lift"] for r in rows], color=cols)
    ax.axvline(1, color=INK, lw=1)
    for i, r in enumerate(rows):
        ax.text(r["lift"] + 0.03, i, f"{r['share%']:.1f}% of turns · n={r['n']}", va="center", fontsize=7.5, color=MUT)
    ax.set_xlabel("lift = share at ideal turning points ÷ share of all bars"); ax.set_title(title, color=INK, fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(CH, fname), dpi=160); plt.close(fig)


def hour_chart(hours, fname):
    ks = sorted(hours); vs = [hours[k] for k in ks]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar([f"{k}:00" for k in ks], vs, color=ACC)
    tot = sum(vs)
    for i, v in enumerate(vs):
        ax.text(i, v, f"{100*v/tot:.0f}%", ha="center", va="bottom", fontsize=8, color=MUT)
    ax.set_title("When the ideal entries happen (hour of day)", color=INK); ax.set_ylabel("ideal entries")
    fig.tight_layout(); fig.savefig(os.path.join(CH, fname), dpi=160); plt.close(fig)


def main():
    S = json.load(open(os.path.join(RES, "oracle_summary.json")))
    T = pd.DataFrame(json.load(open(os.path.join(RES, "oracle_trades.json"))))
    base_bars = S.get("base_bars", 0); base_counts = S.get("base_counts", {})
    n_long, n_short = S["longs"], S["shorts"]

    def precision(rows, n_turns):
        out = []
        for r in rows:
            bc = base_counts.get(r["candle"], 0)
            out.append({**r, "precision%": round(100 * r["n"] / bc, 1) if bc else None})
        return out
    ent_l = precision(S["entry_candle_long"], n_long); ent_s = precision(S["entry_candle_short"], n_short)
    bef_l = precision(S["before_entry_long"], n_long); bef_s = precision(S["before_entry_short"], n_short)
    ex_l = precision(S["exit_candle_long"], n_long); ex_s = precision(S["exit_candle_short"], n_short)

    lift_chart(ent_l, "Candle AT the ideal long entry (the low bar)", "lift_entry_long.png")
    lift_chart(ent_s, "Candle AT the ideal short entry (the high bar)", "lift_entry_short.png")
    lift_chart(bef_l, "Candle one bar BEFORE the ideal long entry", "lift_before_long.png")
    lift_chart(bef_s, "Candle one bar BEFORE the ideal short entry", "lift_before_short.png")
    lift_chart(ex_l, "Candle AT the ideal long exit (the high bar)", "lift_exit_long.png")
    lift_chart(ex_s, "Candle AT the ideal short exit (the low bar)", "lift_exit_short.png")
    hour_chart(S["hour_of_entry"], "hours.png")

    def tbl(rows, extra_hdr="", top=10):
        rows = sorted([r for r in rows if r["n"] >= 200], key=lambda r: -(r["lift"] or 0))[:top]
        body = "".join(f"<tr class='{'pos' if (r['lift'] or 0) > 1.2 else 'neg'}'><td>{r['candle']}</td><td class='num'>{r['n']:,}</td><td class='num'>{r['share%']}%</td><td class='num'>{r['base%']}%</td><td class='num'>{r['lift']}</td><td class='num'>{r.get('precision%', '')}%</td></tr>" for r in rows)
        return f"<table><thead><tr><th>candle</th><th>at turns</th><th>share of turns</th><th>share of all bars</th><th>lift</th><th>precision</th></tr></thead><tbody>{body}</tbody></table>"

    pat = S["patterns_at_entry"]
    pat_rows = "".join(f"<tr class='{'pos' if (r['lift'] or 0) > 1.2 else 'neg'}'><td>{PLABEL.get(r['pattern'], r['pattern'])}</td><td class='num'>{r['at_ideal_entries']:,}</td><td class='num'>{r['agreeing_direction']:,}</td><td class='num'>{r['share%']}%</td><td class='num'>{r['base%']}%</td><td class='num'>{r['lift']}</td></tr>" for r in pat)

    # day-by-day: top 5 per day and one chart per day (largest opportunity)
    days = sorted(T["day"].unique())
    day_sections = ""
    gallery = ""
    charts = {os.path.basename(p)[:10]: p for p in sorted(glob.glob(os.path.join(ORA, "charts", "*.png")))}
    for d in days:
        td = T[T["day"] == d].sort_values("move_pct", ascending=False)
        top5 = td.head(5)
        rows = "".join(f"<tr><td>{r.sym.replace('.NS','')}</td><td>{'LONG' if r.dir>0 else 'SHORT'}</td><td class='num'>{r.entry_t}</td><td class='num'>{r.exit_t}</td><td class='num'>{r.move_pct:+.2f}%</td><td>{r.before_entry}</td><td><b>{r.at_entry}</b></td><td>{r.after_entry}</td><td>{r.at_exit}</td><td class='num'>{'' if pd.isna(r.practical_move_pct) else f'{r.practical_move_pct:+.2f}%'}</td></tr>" for r in top5.itertuples())
        day_sections += f"<h3>{d} <span class='muted'>· {len(td)} swings ≥ {S['thr_pct']:.1f}% in {td['sym'].nunique()} stocks · median {td['move_pct'].median():.2f}%</span></h3><table class='day'><thead><tr><th>stock</th><th>side</th><th>in</th><th>out</th><th>move</th><th>before</th><th>at entry</th><th>after</th><th>at exit</th><th>practical</th></tr></thead><tbody>{rows}</tbody></table>"
    # gallery: 16 days with the biggest single move, one chart each
    best_days = T.sort_values("move_pct", ascending=False).drop_duplicates("day").head(16)
    for r in best_days.itertuples():
        p = os.path.join(ORA, "charts", f"{r.day}_{r.sym.replace('.NS','')}.png")
        if os.path.exists(p):
            gallery += f"<div class='shot'><img src='../oracle/charts/{os.path.basename(p)}'><p class='muted'>{r.day} · {r.sym.replace('.NS','')} · best swing {r.move_pct:+.2f}% · candle at entry: {r.at_entry}; before: {r.before_entry}; at exit: {r.at_exit}</p></div>"

    pr = S["practical"]
    now = dt.date.today().isoformat()
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Where the money was</title>
<style>
@page {{ size: A4; margin: 0; }}
body {{ margin:0; font-family: Charter, Georgia, 'Times New Roman', serif; color:#1b1f2a; font-size:10.5pt; line-height:1.5; }}
h1,h2,h3 {{ font-family:'Avenir Next','Avenir',Helvetica,Arial,sans-serif; color:{INK}; }}
h3 {{ margin:14px 0 4px; font-size:11.5pt; }}
.page {{ padding: 20mm 16mm; page-break-after: always; }}
.page.flow {{ page-break-after: auto; }}
.cover {{ min-height:297mm; box-sizing:border-box; background:linear-gradient(180deg,#ffffff,#f0f4ff,#dbeafe,#bfdbfe,#93c5fd); display:flex; flex-direction:column; justify-content:center; }}
.badge {{ display:inline-block; background:{ACC}; color:#fff; padding:4px 12px; border-radius:6px; font-family:Avenir,Helvetica,sans-serif; font-size:10pt; letter-spacing:1px; }}
.cover h1 {{ font-size:34pt; line-height:1.15; margin:18px 0 8px; }} .cover p {{ font-size:13pt; color:#334155; }}
table {{ border-collapse:collapse; width:100%; margin:6px 0 10px; font-size:8.5pt; page-break-inside:avoid; }}
th {{ background:linear-gradient(135deg,{ACC},#7c3aed); color:#fff; padding:4px 6px; text-align:left; font-family:Avenir,Helvetica,sans-serif; }}
td {{ padding:3px 6px; border-bottom:1px solid #e5e7eb; }} td.num {{ text-align:right; font-family:'Courier New',monospace; }}
tr.pos td:first-child {{ border-left:4px solid {GREEN}; }} tr.neg td:first-child {{ border-left:4px solid #cbd5e1; }}
table.day {{ font-size:7.8pt; }} table.day td, table.day th {{ padding:2px 4px; }}
.key {{ background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px 14px; margin:10px 0; page-break-inside:avoid; }}
.tip {{ background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:10px 14px; margin:10px 0; page-break-inside:avoid; }}
.warn {{ background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:10px 14px; margin:10px 0; page-break-inside:avoid; }}
img {{ max-width:100%; page-break-inside:avoid; }} .shot {{ page-break-inside:avoid; margin-bottom:10px; }} .shot img {{ width:100%; }}
.muted {{ color:{MUT}; font-size:8.5pt; }} .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
.stat {{ display:inline-block; min-width:30%; margin:4px 2%; padding:8px 10px; border:1px solid #e5e7eb; border-radius:8px; }} .stat b {{ font-size:18pt; font-family:'Courier New',monospace; color:{INK}; display:block; }}
</style></head><body>
<div class="page cover"><span class="badge">TRADEPILOT RESEARCH · PART 2</span>
<h1>Where the money was, and what the candles looked like</h1>
<p>Every decent intraday swing in {S['symbols']} NSE stocks over {S['sessions']} sessions, with the ideal entry and exit marked, and the candle that formed before, at and after each turning point.</p>
<p class="muted">Soumya Swain · Surya AI · {now} · v1.0 · data: Kite 5-minute bars</p></div>

<div class="page"><h1>1. The answer first</h1>
<div class="stat"><b>{S['ideal_trades']:,}</b>ideal swings ≥ {S['thr_pct']:.1f}%</div><div class="stat"><b>{S['per_symbol_day']}</b>per stock per day</div><div class="stat"><b>{S['median_move_pct']:.2f}%</b>median swing</div>
<div class="stat"><b>{pr['captured_share%']}%</b>of the swing left after a confirmation-bar entry</div><div class="stat"><b>{pr['median_pct']:.2f}%</b>median practical move, net of costs</div><div class="stat"><b>{sum(v for k, v in S['hour_of_entry'].items() if k in ('09','10'))*100//max(1,S['ideal_trades'])}%</b>of ideal entries before 11:00</div>
<div class="key"><b>The lessons' reversal candles really do sit at the turning points.</b> At the ideal long entry the low bar is a hammer shape {next((r['lift'] for r in ent_l if r['candle']=='hammer shape (red)'), '')}× more often than anywhere else, and the bar just before it is a long red body {next((r['lift'] for r in bef_l if r['candle']=='long body red'), '')}× more often. At the ideal short entry the high bar is an inverted hammer {next((r['lift'] for r in ent_s if r['candle']=='inverted hammer shape (green)'), '')}× more often and the bar before is a long green body {next((r['lift'] for r in bef_s if r['candle']=='long body green'), '')}× more often. Tops and bottoms look the way the videos say they look: a climax candle, then a wick that rejects the extreme, then a long candle the other way.</div>
<div class="warn"><b>But the candles are common and the turning points are rare.</b> A hammer shape appears on about {S['base_candles'].get('hammer shape (red)', 0) + S['base_candles'].get('hammer shape (green)', 0):.1f}% of all bars; a decent bottom happens about {100*n_long/max(1,base_bars):.1f}% of bars. So even with a 1.7× lift, only a few percent of hammers are the bottom (the "precision" column). That is why Part 1 found no forward edge in the shapes alone, and why the money in these swings is only reachable with something the candle does not give you: the level, the time of day, and the size of the move that preceded it.</div>
<div class="tip"><b>Practical, not perfect.</b> Entering at the open of the bar after the confirmation bar (the candle-over-candle rule every lesson uses) still keeps a median {pr['median_pct']:.2f}% after costs on these swings, {pr['captured_share%']}% of the ideal move. The swings are worth chasing; the problem is knowing which hammer is the real one.</div>
</div>

<div class="page"><h1>2. What sat at the turning points</h1>
<h2>At the ideal entry bar</h2>
<div class="grid2"><div><img src="charts2/lift_entry_long.png"></div><div><img src="charts2/lift_entry_short.png"></div></div>
<p class="muted">Lift = how much more often the candle appears at an ideal turning point than on a random bar. Precision = share of all bars with that candle that were an ideal turning point. Bars with fewer than 200 occurrences are omitted.</p>
{tbl(ent_l)}{tbl(ent_s)}
</div>
<div class="page"><h2>One bar before the ideal entry</h2>
<div class="grid2"><div><img src="charts2/lift_before_long.png"></div><div><img src="charts2/lift_before_short.png"></div></div>
{tbl(bef_l)}{tbl(bef_s)}
<p>The bar before a bottom is a long red body or a red marubozu at two to three times its normal frequency; the bar before a top is a long green body at three times. The turning point comes after the climax, not after a quiet drift.</p>
</div>
<div class="page"><h2>At the ideal exit bar</h2>
<div class="grid2"><div><img src="charts2/lift_exit_long.png"></div><div><img src="charts2/lift_exit_short.png"></div></div>
{tbl(ex_l)}{tbl(ex_s)}
<p>Exits are the mirror image. The top of a long is most often a long green body (the climax bar itself) or an inverted-hammer or gravestone rejection; the bottom of a short is a long red body or a hammer. This is the "get out on the first candle-under-candle after a topping tail" rule from lesson 1, seen from the other side.</p>
<h2>Multi-bar patterns completing within one bar of the ideal entry</h2>
<table><thead><tr><th>pattern</th><th>at entries</th><th>agreeing direction</th><th>share of entries</th><th>base rate</th><th>lift</th></tr></thead><tbody>{pat_rows}</tbody></table>
<p class="muted">Three-bar reversals and breakout candles carry the most lift, around 1.8×, but each sits at only one or two percent of the turning points. Engulfing candles appear at a fifth of all turning points and at almost the same rate everywhere else.</p>
<img src="charts2/hours.png">
</div>

<div class="page"><h1>3. Sixteen days, marked</h1><p class="muted">One chart per day for the sixteen largest single swings. Green arrow = ideal entry, purple = ideal exit, with the candle name at each. Every session's charts are in <code>docs/research/candles/oracle/charts/</code>.</p></div>
<div class="page flow">{gallery}</div>

<div class="page"><h1>4. Day by day</h1><p>For every session: the five largest swings, the candle before, at and after the entry, the candle at the exit, and the practical move from a confirmation-bar entry. The full list for each day (top 25) is in <code>docs/research/candles/oracle/daily/</code>.</p></div>
<div class="page flow">{day_sections}</div>

<div class="page"><h1>5. What to do with this</h1>
<ol>
<li><b>Teach the agents the sequence, not the shape.</b> The sequence at a bottom is: a run down, a climax red bar, a bar whose low is rejected (hammer, dragonfly, or a small body with a long lower wick), then a green bar over the rejection bar's high. Encode it as features: run length, size of the last red bar in ATR, lower-wick share of the rejection bar, and the break of its high. The same in mirror for tops.</li>
<li><b>Add the missing context.</b> Precision is low because the candle does not know where it is. Distance to the prior-day high/low/close and the session extremes, minutes since the open, and the swing already travelled since the last pivot are the inputs that separate the real hammer from the noise one.</li>
<li><b>Exits deserve the same treatment.</b> The top of a winning long is a climax green bar or a wick rejection. Our engines exit on stops, time and targets; a "climax-bar trail" that tightens the stop after a long green body or an inverted hammer would catch what these charts show.</li>
<li><b>Train and test on the sequence.</b> Label every bar with "ideal turning point within the next 1 bar" from this study, train the ML on the features above, and measure precision at a fixed recall. That is the honest way to find out whether the candles can be read better than by eye.</li>
</ol>
<p class="muted">Method: zigzag with a {S['thr_pct']:.1f}% reversal threshold on highs and lows; every swing is an ideal trade from one pivot to the next. Practical entry = open of the bar after the first bar that breaks the pivot bar's high (or low). Costs 12 bps. Single-candle names use the lessons' definitions: body ≤10% of range = doji; lower wick ≥60% with upper ≤15% = hammer shape; body ≥85% = marubozu; body ≥60% and range above the day's median = long body; body ≤30% with wicks both sides = spinning top.</p>
</div>
</body></html>"""
    out = os.path.join(REP, "where-the-money-was.html")
    open(out, "w").write(html)
    print("wrote", out, "days", len(days))


if __name__ == "__main__":
    main()
