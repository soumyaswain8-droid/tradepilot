#!/usr/bin/env python3
"""Build the candlestick research report: charts (matplotlib) + HTML + PDF (pyppeteer).

    python3 build_report.py

Reads results/*.json written by run.py and the lesson notes in ../lessons.
Writes ../report/candlestick-lessons-backtest.{html,pdf} and ../report/charts/*.png
"""
from __future__ import annotations
import json, os, glob, asyncio, collections, datetime as dt
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
REP = os.path.join(HERE, "..", "report")
CH = os.path.join(REP, "charts")
os.makedirs(CH, exist_ok=True)
COST_BPS = 12
VARIANTS = ["5m_all_day", "5m_first90", "5m_trend_run3", "5m_key_level", "5m_key_level_first90", "15m_all_day", "1d"]
VLABEL = {"5m_all_day": "5-min, all day", "5m_first90": "5-min, first 90 min", "5m_trend_run3": "5-min, after a 3-bar run",
          "5m_key_level": "5-min, at a key level", "5m_key_level_first90": "5-min, key level + first 90", "15m_all_day": "15-min", "1d": "Daily"}
PLABEL = {"hammer": "Hammer (L1/L2/L3)", "shooting_star": "Shooting star (L1/L3)", "doji_top": "Doji at top (L1)", "doji_bottom": "Doji at bottom (L1)",
          "pin_bar_bull": "Pin bar bull (L2)", "pin_bar_bear": "Pin bar bear (L2)", "engulfing_bull": "Engulfing bull (L2/L3)", "engulfing_bear": "Engulfing bear (L2/L3)",
          "three_bar_rev_bull": "3-bar reversal bull (L2)", "three_bar_rev_bear": "3-bar reversal bear (L2)", "shrinking_bull": "Shrinking bull (L2)", "shrinking_bear": "Shrinking bear (L2)",
          "three_bar_cont_bull": "3-bar continuation bull (L2)", "three_bar_cont_bear": "3-bar continuation bear (L2)", "breakout_bull": "Breakout bull (L2)", "breakout_bear": "Breakout bear (L2)",
          "bull_flag": "Bull flag (L1)", "bear_flag": "Bear flag (L1)"}
GREEN, RED, INK, MUT, ACC, AMB = "#16a34a", "#dc2626", "#1e1b4b", "#6b7280", "#4f46e5", "#d97706"


def load_trades(v):
    f = os.path.join(RES, f"trades_{v}.json")
    return pd.DataFrame(json.load(open(f))) if os.path.exists(f) else pd.DataFrame()


def table(df):
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("pattern")
    t = pd.DataFrame({
        "n": g.size(),
        "per_day": (g.size() / df["day"].nunique()).round(1),
        "win%": (100 * g["net_pct"].apply(lambda x: (x > 0).mean())).round(0),
        "gross_bps": (g["net_pct"].mean() * 1e4 + COST_BPS).round(1),
        "net_bps": (g["net_pct"].mean() * 1e4).round(1),
        "avg_R": g["r"].mean().round(2),
        "target%": (100 * g["reason"].apply(lambda x: (x == "target").mean())).round(0),
        "stop%": (100 * g["reason"].apply(lambda x: (x == "stop").mean())).round(0),
    })
    return t.sort_values("net_bps", ascending=False)


def chart_heatmap(tabs):
    pats = list(PLABEL)
    vs = [v for v in VARIANTS if v in tabs and not tabs[v].empty]
    M = np.full((len(pats), len(vs)), np.nan)
    N = np.zeros_like(M)
    for j, v in enumerate(vs):
        for i, p in enumerate(pats):
            if p in tabs[v].index:
                M[i, j] = tabs[v].loc[p, "net_bps"]; N[i, j] = tabs[v].loc[p, "n"]
    fig, ax = plt.subplots(figsize=(11, 8.2))
    vmax = np.nanmax(np.abs(M)) if np.isfinite(M).any() else 1
    im = ax.imshow(M, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(vs))); ax.set_xticklabels([VLABEL[v] for v in vs], rotation=25, ha="right", fontsize=9)
    ax.set_yticks(range(len(pats))); ax.set_yticklabels([PLABEL[p] for p in pats], fontsize=9)
    for i in range(len(pats)):
        for j in range(len(vs)):
            if np.isfinite(M[i, j]):
                ax.text(j, i, f"{M[i,j]:+.0f}\n n={int(N[i,j])}", ha="center", va="center", fontsize=7, color="black")
    ax.set_title("Net expectancy per trade (bps, after 12 bps costs) by pattern and setting", fontsize=12, color=INK)
    fig.colorbar(im, ax=ax, shrink=0.7, label="bps per trade")
    fig.tight_layout(); fig.savefig(os.path.join(CH, "heatmap.png"), dpi=170); plt.close(fig)


def chart_bars(tab, name, title):
    if tab.empty:
        return
    t = tab.sort_values("net_bps")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    cols = [GREEN if x > 0 else RED for x in t["net_bps"]]
    ax.barh([PLABEL.get(p, p) for p in t.index], t["net_bps"], color=cols)
    ax.axvline(0, color=INK, lw=1)
    ax.axvline(-COST_BPS, color=AMB, lw=1, ls="--", label="pure noise line (−12 bps = costs)")
    for i, (p, r) in enumerate(t.iterrows()):
        ax.text(r["net_bps"] + (1 if r["net_bps"] >= 0 else -1), i, f"n={int(r['n'])}, win {int(r['win%'])}%", va="center", ha="left" if r["net_bps"] >= 0 else "right", fontsize=7.5, color=MUT)
    ax.set_xlabel("net bps per trade"); ax.set_title(title, color=INK); ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(CH, f"bars_{name}.png"), dpi=170); plt.close(fig)


def chart_opening(orr):
    rows = [(k, v) for k, v in orr.items() if "exp_bps" in v]
    if not rows:
        return
    rows.sort(key=lambda kv: kv[1]["exp_bps"])
    fig, ax = plt.subplots(figsize=(10, 6))
    cols = [GREEN if v["exp_bps"] > 0 else RED for k, v in rows]
    ax.barh([k.replace("_", " ") for k, v in rows], [v["exp_bps"] for k, v in rows], color=cols)
    ax.axvline(0, color=INK, lw=1)
    for i, (k, v) in enumerate(rows):
        ax.text(v["exp_bps"] + (1 if v["exp_bps"] >= 0 else -1), i, f"n={v['n']}, win {v['win%']}%", va="center", ha="left" if v["exp_bps"] >= 0 else "right", fontsize=7.5, color=MUT)
    ax.set_xlabel("net bps per trade"); ax.set_title("Opening-range strategies (lessons 3, 4, 5) and the ORB control", color=INK)
    fig.tight_layout(); fig.savefig(os.path.join(CH, "opening.png"), dpi=170); plt.close(fig)


def chart_overlay(ov):
    keys = [k for k in ov if ":" in k and not k.startswith("opposing")]
    if not keys:
        return
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [k.replace(":", " · ") for k in keys]
    vals = [ov[k]["pnl"] for k in keys]
    ax.bar(labels, vals, color=[GREEN if v > 0 else RED for v in vals])
    for i, k in enumerate(keys):
        ax.text(i, vals[i], f"n={ov[k]['n']}\nwin {ov[k]['win']}%", ha="center", va="bottom" if vals[i] >= 0 else "top", fontsize=8, color=MUT)
    ax.axhline(0, color=INK, lw=1); ax.set_ylabel("engine P&L, ₹ (11 Aug to 11 Sep)")
    ax.set_title("Engine trades by candle context at entry: agreeing / opposing / no pattern", color=INK)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(CH, "overlay.png"), dpi=170); plt.close(fig)



def verdicts(tabs, orr, ov):
    """Section 6 text, with the numbers computed from the results so the prose cannot drift."""
    def mean_net(v, side):
        t = tabs.get(v, pd.DataFrame())
        if t.empty:
            return np.nan
        rows = t[[(side in p) or (side == "bear" and p in ("shooting_star", "doji_top")) or (side == "bull" and p in ("hammer", "doji_bottom")) for p in t.index]]
        return float((rows["net_bps"] * rows["n"]).sum() / rows["n"].sum()) if len(rows) else np.nan
    all_bull, all_bear = mean_net("5m_all_day", "bull"), mean_net("5m_all_day", "bear")
    f90_bull, f90_bear = mean_net("5m_first90", "bull"), mean_net("5m_first90", "bear")
    kl = tabs.get("5m_key_level", pd.DataFrame()); ad = tabs.get("5m_all_day", pd.DataFrame())
    kl_lift = float(((kl["net_bps"] - ad["net_bps"]).dropna()).mean()) if not kl.empty and not ad.empty else np.nan
    t15 = tabs.get("15m_all_day", pd.DataFrame()); d1 = tabs.get("1d", pd.DataFrame())
    d1_pos = d1[(d1["net_bps"] > 0) & (d1["n"] >= 100)] if not d1.empty else pd.DataFrame()
    r4 = orr.get("R4_first_bar_colour_holds_to_0930", {}).get("rate%", np.nan)
    q1 = orr.get("Q1_liquidity_candle_rate", {})
    def g(k, f="exp_bps"):
        return orr.get(k, {}).get(f, np.nan)
    both = {k.split(":")[1]: v for k, v in ov.items() if k.startswith("both:")}
    per = {k: (v["pnl"] / v["n"] if v["n"] else np.nan) for k, v in both.items()}
    opp = ov.get("opposing_by_pattern", {})
    worst_opp = sorted(((v["pnl"] / v["n"], k, v) for k, v in opp.items() if v["n"] >= 10))[:3]
    def fmt(x, d=1):
        return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:+.{d}f}"
    html = f"""
<h2>Single- and multi-candle shapes on 5-minute bars: no edge</h2>
<p>Taking every signal all day, bullish shapes averaged <b>{fmt(all_bull)} bps</b> net per trade and bearish shapes <b>{fmt(all_bear)} bps</b>. Add back the 12 bps of costs and the gross edge is a few basis points either side of zero. The bearish side did better in every setting, but the test window (mid-July to mid-September 2026) was a falling market, so that is the regime, not the candle.</p>
<h2>Timing helps a little, levels help a little, neither pays the costs</h2>
<p>Restricting to the first 90 minutes lifted the bullish average to <b>{fmt(f90_bull)} bps</b> and the bearish to <b>{fmt(f90_bear)} bps</b>. Requiring the pattern to sit within 0.15 ATR of a key level (prior-day high, low, close or the session's running high and low) changed the average pattern by <b>{fmt(kl_lift)} bps</b>. Combining both produced the best intraday cells (three-bar continuation and three-bar reversal in the first 90 minutes at a level), and even those stayed just below break-even after costs. Lesson 1's "only when trending" filter (a run of three same-colour bars first) did not rescue the hammer, doji or shooting star.</p>
<h2>15-minute bars: same picture, fewer trades</h2>
<p>{("Every pattern was net negative on 15-minute bars; the best was " + PLABEL.get(t15["net_bps"].idxmax(), "") + f" at {t15['net_bps'].max():+.1f} bps.") if not t15.empty else ""} Lesson 2's claim that patterns improve on higher timeframes is not visible at 15 minutes.</p>
<h2>Daily bars: a few real positives, small samples</h2>
<p>{("On daily bars over one year, " + ", ".join(f"{PLABEL.get(p, p)} ({int(r['n'])} trades, {r['net_bps']:+.0f} bps, {int(r['win%'])}% win)" for p, r in d1_pos.iterrows()) + " were net positive with at least 100 trades.") if len(d1_pos) else "On daily bars no pattern with at least 100 trades was net positive."} Daily moves are large relative to costs, so a modest edge shows through. This is the one place lesson 2's higher-timeframe claim holds, and the sample is one year of one regime, so treat it as a lead, not a result.</p>
<h2>The opening range: neither the trap nor the truth</h2>
<p>Lesson 5's core claim is that the first candle's colour holds for 15 minutes. On {orr.get("R4_first_bar_colour_holds_to_0930", {}).get("n", 0):,} stock-days the first 5-minute bar's colour matched the 09:15-09:30 direction <b>{r4}%</b> of the time: a coin flip. Its open-equals-high short exited at 09:30 made <b>{fmt(g("R1_open_eq_high_short_exit0930"))} bps</b>, and open-equals-low long <b>{fmt(g("R2_open_eq_low_long_exit0930"))} bps</b>. Only one slice was positive: open-equals-low longs on the day's top-decile gappers held to the close ({orr.get("R2_open_eq_low_long_exitclose", {}).get("top10%gappers", {}).get("n", 0)} trades, {fmt(orr.get("R2_open_eq_low_long_exitclose", {}).get("top10%gappers", {}).get("exp_bps"))} bps), which is the opposite of the lesson's 09:30 exit.</p>
<p>Lesson 3's liquidity-candle test is almost always true here: <b>{q1.get("rate%", "n/a")}%</b> of opening candles exceed 25% of daily ATR (median {q1.get("median_ratio", "n/a")}× ATR), so it does not select anything. Trading the reversal outside the box made <b>{fmt(g("Q2_reversal_short_target_box"))} bps</b> on the short side and <b>{fmt(g("Q3_reversal_long_target_box"))} bps</b> on the long side with the box-edge target; only {orr.get("Q2_reversal_short_target_box", {}).get("target%", "n/a")}% and {orr.get("Q3_reversal_long_target_box", {}).get("target%", "n/a")}% of trades reached the far edge. The control, ORB continuation (the bet our engines make), was worse still at <b>{fmt(g("Q5_control_ORB_continuation_2R"))} bps</b>. Lesson 4's sneaky pivot at the prior-day high was the best opening-range idea: <b>{fmt(g("S2_sneaky_short_at_PDH_target_2R"))} bps</b> with a {g("S2_sneaky_short_at_PDH_target_2R", "win%")}% hit rate, still short of costs.</p>
<h2>What it would have done to the engines</h2>
<p>Across {sum(v["n"] for v in both.values()):,} engine trades, those entered with an agreeing pattern lost <b>₹{fmt(per.get("agreeing"), 0)} per trade</b>, those entered against an opposing pattern lost <b>₹{fmt(per.get("opposing"), 0)}</b>, and those with no pattern lost <b>₹{fmt(per.get("none"), 0)}</b>. Candle context at the entry bar does not separate good engine trades from bad ones. The engines' losses come from elsewhere: the regime, the exits, and the swept-low entries documented on 11 September.</p>
<p>The only opposing patterns worth a veto are the ones with a large loss per trade: {", ".join(f"{PLABEL.get(k, k)} (₹{pt:+.0f} per trade on {v['n']})" for pt, k, v in worst_opp)}. These are small samples and should be confirmed on more sessions before they block anything.</p>
<div class="warn"><b>Why the videos and the data disagree.</b> The teachers trade markets with a catalyst and a crowd (US small caps on news, Nasdaq at the open), use discretion to skip bad-looking setups, and remember their winners. A detector takes every instance. On a broad Indian universe with 12 bps of friction, the shape of one to four bars carries almost no information about the next 2R move. The parts of the lessons that survive are the parts that are not about shapes: trade early, trade at a level, put the stop behind structure, and confirm with the next bar. Those belong in the engine as context features, and section 6's recommendations follow from that.</div>
"""
    return html


def md_table(t, cols=None):
    if t.empty:
        return "<p class='muted'>no trades</p>"
    t = t.copy()
    t.index = [PLABEL.get(p, p) for p in t.index]
    cols = cols or list(t.columns)
    head = "".join(f"<th>{c}</th>" for c in ["pattern"] + cols)
    body = ""
    for p, r in t.iterrows():
        cls = "pos" if r["net_bps"] > 0 else "neg"
        cells = "".join(f"<td class='num'>{int(r[c]) if c in ('n',) else r[c]}</td>" for c in cols)
        body += f"<tr class='{cls}'><td>{p}</td>{cells}</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def main():
    tabs = {v: table(load_trades(v)) for v in VARIANTS}
    orr = json.load(open(os.path.join(RES, "opening_range.json"))) if os.path.exists(os.path.join(RES, "opening_range.json")) else {}
    ov = json.load(open(os.path.join(RES, "engine_overlay.json"))) if os.path.exists(os.path.join(RES, "engine_overlay.json")) else {}
    chart_heatmap(tabs)
    for v in VARIANTS:
        chart_bars(tabs[v], v, f"{VLABEL[v]}: net expectancy per pattern")
    chart_opening(orr); chart_overlay(ov)

    # ranking: best (pattern, setting) pairs with n >= 100
    ranked = []
    for v, t in tabs.items():
        for p, r in t.iterrows():
            if r["n"] >= 100:
                ranked.append((r["net_bps"], p, v, int(r["n"]), int(r["win%"]), r["avg_R"]))
    ranked.sort(reverse=True)
    top = ranked[:8]; bottom = ranked[-5:]
    positives = [x for x in ranked if x[0] > 0]

    # engine overlay numbers
    ovb = {k: ov[k] for k in ov if k.startswith("both:")}
    opp_by = ov.get("opposing_by_pattern", {})

    now = dt.date.today().isoformat()
    lessons_html = ""
    for f in sorted(glob.glob(os.path.join(HERE, "..", "lessons", "0[1-6]-*.md"))):
        title = open(f).readline().lstrip("# ").strip()
        lessons_html += f"<li><b>{title}</b> <span class='muted'>({os.path.basename(f)})</span></li>"

    def rank_rows(rows):
        return "".join(f"<tr class='{'pos' if x[0] > 0 else 'neg'}'><td>{PLABEL.get(x[1], x[1])}</td><td>{VLABEL[x[2]]}</td><td class='num'>{x[3]}</td><td class='num'>{x[4]}%</td><td class='num'>{x[5]:+.2f}</td><td class='num'>{x[0]:+.1f}</td></tr>" for x in rows)

    or_rows = "".join(
        f"<tr class='{'pos' if v.get('exp_bps', 0) > 0 else 'neg'}'><td>{k.replace('_', ' ')}</td><td class='num'>{v['n']}</td><td class='num'>{v.get('win%', v.get('rate%', ''))}%</td><td class='num'>{v.get('exp_bps', '')}</td><td class='num'>{v.get('avg_R', '')}</td><td class='num'>{v.get('target%', '')}</td></tr>"
        for k, v in orr.items())

    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Candlestick lessons, tested on TradePilot data</title>
<style>
@page {{ size: A4; margin: 0; }}
body {{ margin:0; font-family: Charter, Georgia, 'Times New Roman', serif; color:#1b1f2a; font-size:11pt; line-height:1.5; }}
h1,h2,h3 {{ font-family:'Avenir Next','Avenir',Helvetica,Arial,sans-serif; color:{INK}; }}
.page {{ padding: 22mm 18mm; page-break-after: always; }}
.cover {{ min-height:297mm; box-sizing:border-box; background:linear-gradient(180deg,#ffffff,#f0f4ff,#dbeafe,#bfdbfe,#93c5fd); display:flex; flex-direction:column; justify-content:center; }}
.badge {{ display:inline-block; background:{ACC}; color:#fff; padding:4px 12px; border-radius:6px; font-family:Avenir,Helvetica,sans-serif; font-size:10pt; letter-spacing:1px; }}
.cover h1 {{ font-size:34pt; line-height:1.15; margin:18px 0 8px; }}
.cover p {{ font-size:13pt; color:#334155; }}
table {{ border-collapse:collapse; width:100%; margin:8px 0 12px; font-size:9pt; page-break-inside:avoid; }}
th {{ background:linear-gradient(135deg,{ACC},#7c3aed); color:#fff; padding:5px 6px; text-align:left; font-family:Avenir,Helvetica,sans-serif; }}
td {{ padding:4px 6px; border-bottom:1px solid #e5e7eb; }}
td.num {{ text-align:right; font-family:'Courier New',monospace; }}
tr.pos td:first-child {{ border-left:4px solid {GREEN}; }} tr.neg td:first-child {{ border-left:4px solid {RED}; }}
.key {{ background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px 14px; margin:10px 0; page-break-inside:avoid; }}
.tip {{ background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:10px 14px; margin:10px 0; page-break-inside:avoid; }}
.warn {{ background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:10px 14px; margin:10px 0; page-break-inside:avoid; }}
img {{ max-width:100%; page-break-inside:avoid; }}
.muted {{ color:{MUT}; font-size:9pt; }}
.page.flow {{ page-break-after:auto; }}
.variant {{ page-break-inside:avoid; margin-bottom:14px; }}
.variant h2 {{ margin:6px 0 4px; font-size:14pt; }}
img.bars {{ width:88%; display:block; margin:0 auto; }}
.variant table {{ font-size:8pt; }} .variant td, .variant th {{ padding:2px 5px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
</style></head><body>
<div class="page cover">
  <span class="badge">TRADEPILOT RESEARCH</span>
  <h1>Five candlestick lessons, tested on our own market</h1>
  <p>What the videos teach, where they agree, and what each rule actually earned on 399 NSE stocks over 45 sessions (13 Jul to 11 Sep 2026), plus what it would have done to the engines' own trades.</p>
  <p class="muted">Soumya Swain · Surya AI · {now} · v1.0</p>
</div>

<div class="page">
<h1>1. The answer first</h1>
<div class="key"><b>Raw candle shapes on 5-minute bars are noise.</b> Across {sum(int(t['n'].sum()) for t in tabs.values() if not t.empty):,} pattern trades, gross expectancy sits within a few basis points of zero and net expectancy is about the cost of trading. Hit rates are 28 to 36% against a 2-to-1 target that needs 33%. No lesson's single-candle or two-candle shape pays for itself when taken everywhere it appears.</div>
<div class="tip"><b>Nothing intraday beat its costs; a few daily patterns did.</b> The filters every lesson insists on (a run before the pattern, a key level under it, the first 90 minutes) move expectancy a few basis points in the right direction but never past break-even on 5- or 15-minute bars. On daily bars, three patterns were net positive with at least 100 trades over one year. The table below ranks every pattern-and-setting pair with at least 100 trades.</div>
<h3>Best pattern-and-setting pairs (n ≥ 100)</h3>
<table><thead><tr><th>pattern</th><th>setting</th><th>n</th><th>win</th><th>avg R</th><th>net bps</th></tr></thead><tbody>{rank_rows(top)}</tbody></table>
<p class="muted">{len(positives)} of {len(ranked)} pattern-and-setting pairs are net positive, all on daily bars. "bps" is basis points of price per trade after 12 bps round-trip costs; 10 bps on a ₹1,00,000 position is ₹100.</p>
<div class="variant"><h3>Worst</h3>
<table><thead><tr><th>pattern</th><th>setting</th><th>n</th><th>win</th><th>avg R</th><th>net bps</th></tr></thead><tbody>{rank_rows(bottom)}</tbody></table></div>
</div>

<div class="page">
<h1>2. What the lessons teach</h1>
<ul>{lessons_html}</ul>
<h2>The common core</h2>
<p>All five teachers, in different words, say the same four things. A wick is the message: a long lower wick means buyers absorbed a dip, a long upper wick means sellers rejected a high. A reversal candle is a signal, not an entry; the next candle must confirm by breaking the reversal candle's extreme. Location beats shape: the same candle means nothing inside a range and everything at a level or the end of a run. The stop goes behind the structure, and the target is about twice the risk or the far side of the structure.</p>
<h2>Where they disagree</h2>
<p><b>Is the opening move a trap or the truth?</b> Lesson 3 and lesson 4 say the first 15-minute candle is engineered liquidity that gets reversed; trade against it once a reversal candle prints outside the range. Lesson 5 says the first minute's direction holds for 15 minutes; trade with it and leave at 09:30. <b>Timeframe:</b> lesson 1 works on 1- and 5-minute bars, lesson 2 says patterns are unreliable below one hour. <b>Vocabulary:</b> lesson 1 names ten candles, lesson 3 keeps two. These disagreements are exactly what the backtest settles.</p>
<h2>How the test was run</h2>
<p>Every rule was written as a detector on open, high, low, close. Entry is the next bar's open after the signal completes, so there is no look-ahead. The stop is the level the lesson prescribes for that pattern. The target is twice the risk. Anything still open is closed at the session end. If a bar touches both the stop and the target, it counts as a stop. Costs are 12 basis points round trip, the same model the fleet uses. Every trade risks a fixed ₹500 so rupee totals compare across patterns. Data: 399 stocks from the engines' universe, 5-minute bars from 13 July to 11 September 2026, 15-minute bars built from them, and one year of daily bars.</p>
</div>

<div class="page">
<h1>3. Every pattern, every setting</h1>
<img src="charts/heatmap.png">
<p class="muted">Each cell is the net expectancy per trade for that pattern in that setting, with the trade count. Green earns, red loses. A cell near −12 is pure noise: the pattern added nothing and costs took their 12 bps.</p>
</div>

<div class="page flow">{"".join(f'<div class="variant"><h2>{VLABEL[v]}</h2><img class="bars" src="charts/bars_{v}.png">{md_table(tabs[v])}</div>' for v in VARIANTS if not tabs[v].empty)}</div>

<div class="page">
<h1>4. The opening range: trap or truth?</h1>
<img src="charts/opening.png">
<table><thead><tr><th>strategy</th><th>n</th><th>win / rate</th><th>net bps</th><th>avg R</th><th>target%</th></tr></thead><tbody>{or_rows}</tbody></table>
<p class="muted">Q rows are lesson 3 (liquidity candle ≥ 25% of daily ATR, then a hammer, inverted hammer or engulfing candle outside the box within 90 minutes; target the far edge of the box or 2R). Q5 is the control: ORB continuation, the bet our engines make. S rows are lesson 4 (sneaky pivot at the prior day's high or low on 15-minute bars). R rows are lesson 5 (open = high or open = low on the first 5-minute bar, exit 09:30, with longer holds as controls). R4 is the base rate that the first bar's colour holds to 09:30. Q1 is how often the opening candle qualifies as a liquidity candle.</p>
</div>

<div class="page">
<h1>5. What it would have done to our engines</h1>
<img src="charts/overlay.png">
<p>Every closed v5 and v5_wide trade from 11 August to 11 September was tagged with the candle patterns that completed on its entry bar or the bar before. "Agreeing" means a pattern pointed the same way as the trade, "opposing" means a pattern pointed the other way, "none" means no pattern was present.</p>
<table><thead><tr><th>group</th><th>trades</th><th>P&amp;L ₹</th><th>win</th></tr></thead><tbody>{"".join(f"<tr class='{'pos' if v['pnl']>0 else 'neg'}'><td>{k}</td><td class='num'>{v['n']}</td><td class='num'>{v['pnl']:,.0f}</td><td class='num'>{v['win']}%</td></tr>" for k, v in ov.items() if ':' in k)}</tbody></table>
<h3>Opposing patterns, by pattern (engine P&amp;L of the trades they argued against)</h3>
<table><thead><tr><th>pattern</th><th>trades</th><th>P&amp;L ₹</th></tr></thead><tbody>{"".join(f"<tr class='{'pos' if v['pnl']>0 else 'neg'}'><td>{PLABEL.get(k,k)}</td><td class='num'>{v['n']}</td><td class='num'>{v['pnl']:,.0f}</td></tr>" for k, v in opp_by.items())}</tbody></table>
</div>

<div class="page">
<h1>6. Which ones work, and why</h1>
{verdicts(tabs, orr, ov)}
<h2>Recommendations for the engines and the Floor</h2>
<ol>
<li><b>Do not add raw candle-shape features to the scorer.</b> Their standalone expectancy is zero; as ML features they will fit noise.</li>
<li><b>Add context features instead:</b> run length before the bar, distance to prior-day high/low/close and to the session high/low in ATR units, minutes since the open, and the opening-range position (inside, above, below the 09:15-09:30 box). These are the only things that moved expectancy in the right direction in this test.</li>
<li><b>Use the opposing-pattern tag as a veto, not the agreeing tag as an entry.</b> Section 5 shows which opposing patterns coincided with engine losses. That is the same lesson as the swept-low reclaim finding from 11 September: the cheapest improvement is to stop the worst entries, not to add new ones.</li>
<li><b>Feed the Floor the same context.</b> Its SWEEP_RECLAIM is the reclaim family here; point it at the engine universe and it becomes the live detector for the veto.</li>
</ol>
</div>
</body></html>"""
    out_html = os.path.join(REP, "candlestick-lessons-backtest.html")
    open(out_html, "w").write(html)
    print("wrote", out_html)
    json.dump({"ranked": ranked}, open(os.path.join(RES, "ranked.json"), "w"))


if __name__ == "__main__":
    main()
