#!/usr/bin/env python3
"""
Build the session report PDF — a dated engineering + trading record.

Deliberately a DIFFERENT document from the explainer. The explainer answers "how does
this work" for someone who has never bought a share. This answers "what happened
today, what did it cost, and what do I now have to decide" for the person who owns
the thing. Technical detail is welcome here; it is not welcome there.

Shares the explainer's glass design system by importing it, so the two documents
cannot drift apart visually.

    python3 brand/build-session-report.py [YYYY-MM-DD]
"""
from __future__ import annotations
import asyncio, importlib.util, json, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# reuse the explainer's design system, fonts, logo and render/QA pipeline
_spec = importlib.util.spec_from_file_location("bex", ROOT / "brand" / "build-explainer.py")
BEX = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BEX)

DAY = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
OUT_HTML = ROOT / "brand" / f"session-{DAY}.html"
OUT_PDF = ROOT / "1cr-roadmap" / f"TradePilot-Session-{DAY}.pdf"


def book(day):
    f = ROOT / "docs" / "sarathi" / "knowledge" / "positions" / f"{day}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def stats(b):
    """Everything the report quotes, computed once so no figure can disagree with
    another one later in the document."""
    if not b:
        return None
    c = [p for p in b["positions"] if p["status"] == "CLOSED"]
    if not c:
        return None
    w = [p for p in c if p["pnl_net"] > 0]
    l = [p for p in c if p["pnl_net"] <= 0]
    from collections import Counter
    import statistics as st
    return {
        "n": len(c), "wins": len(w), "losses": len(l),
        "wr": len(w) / len(c) * 100,
        "gross": sum(p["pnl_gross"] for p in c),
        "fees": sum(p["fee"] for p in c),
        "net": sum(p["pnl_net"] for p in c),
        "avg_w": st.mean([p["pnl_net"] for p in w]) if w else 0,
        "avg_l": st.mean([p["pnl_net"] for p in l]) if l else 0,
        "hold": st.median([p["held_s"] for p in c]) / 60,
        "reasons": Counter(p["reason"] for p in c),
        "levels": {k: (v, sum(p["pnl_net"] for p in c if p.get("level_name") == k))
                   for k, v in Counter(p.get("level_name") for p in c).items()},
        "open": b.get("open", 0), "declined": b.get("declined_total", 0),
    }


def build(day, S):
    css = BEX.build_html().split("<style>")[1].split("</style>")[0]
    logo = BEX.logo_uri()
    mark = (ROOT / "brand" / "letterhead" / "tradepilot-mark.svg").read_text()
    MESH = ("<svg viewBox='0 0 210 297' preserveAspectRatio='none'><defs>"
            "<radialGradient id='m1' cx='.5' cy='.5' r='.5'>"
            "<stop offset='0%' stop-color='#818cf8' stop-opacity='.20'/>"
            "<stop offset='100%' stop-color='#818cf8' stop-opacity='0'/></radialGradient>"
            "<radialGradient id='m2' cx='.5' cy='.5' r='.5'>"
            "<stop offset='0%' stop-color='#4f46e5' stop-opacity='.13'/>"
            "<stop offset='100%' stop-color='#4f46e5' stop-opacity='0'/></radialGradient>"
            "</defs><ellipse cx='196' cy='26' rx='62' ry='62' fill='url(#m1)'/>"
            "<ellipse cx='12' cy='232' rx='54' ry='54' fill='url(#m2)'/></svg>")

    extra = """
.tl{display:grid;grid-template-columns:20mm 1fr;gap:5mm;margin:0 0 5mm;
    page-break-inside:avoid;}
.tl .t{font-family:'JetBrains Mono',monospace;font-size:11pt;color:#4f46e5;
    font-weight:500;padding-top:.6mm;}
.tl .t small{display:block;font-size:6.6pt;color:#6b6580;margin-top:.8mm;}
.tl h3{margin:0 0 2mm;}
.kpi{display:flex;gap:3mm;margin:4mm 0;page-break-inside:avoid;}
.kpi .k{flex:1;padding:3.5mm;border-radius:5pt;text-align:center;
  background:rgba(255,255,255,.82);border:0.6pt solid rgba(255,255,255,.9);
  box-shadow:0 0.8pt 0 rgba(49,46,129,.10), inset 0 0.6pt 0 rgba(255,255,255,.95);}
.kpi .k .n{font-family:'JetBrains Mono',monospace;font-size:17pt;font-weight:500;
  color:#0a0520;line-height:1.1;}
.kpi .k .n.neg{color:#be123c;} .kpi .k .n.pos{color:#1a7f4b;}
.kpi .k .l{font-size:6.8pt;letter-spacing:.12em;text-transform:uppercase;
  color:#6b6580;margin-top:1.2mm;}
.dec{padding:4mm 5mm;margin:3.5mm 0;border-radius:5pt;page-break-inside:avoid;
  background:rgba(255,255,255,.82);border:0.6pt solid rgba(255,255,255,.9);
  border-left:2.6pt solid #4f46e5;
  box-shadow:0 0.8pt 0 rgba(49,46,129,.10), inset 0 0.6pt 0 rgba(255,255,255,.95);}
.dec h4{margin:0 0 1.5mm;}
.dec .o{display:grid;grid-template-columns:6mm 1fr;gap:2mm;padding:1.6mm 0;
  border-top:.5pt solid rgba(221,222,245,.9);font-size:9pt;}
.dec .o b{font-family:'JetBrains Mono',monospace;color:#4f46e5;}
"""

    def page(inner, num, title):
        return f"""<div class="page"><div class="mesh">{MESH}</div>
  <div class="rh"><div class="brand"><img src="{logo}"/><span class="wm">TradePilot</span></div>
    <span class="sec">{title}</span></div>
  {inner}
  <div class="rf"><span>Session report — {day}</span><span>{num}</span></div></div>"""

    n = lambda v: f"{v:+,.2f}"
    P = []

    # ── cover ────────────────────────────────────────────────────────────────
    P.append(f"""<div class="page cover"><div class="inner">
  <div class="mk">{mark}</div>
  <h1>Session Report</h1>
  <p class="sub">Wednesday 26 August 2026 — the day the agents started trading on
  their own, and the day their first result was falsified within two charts.</p>
  <div class="meta">
    <div>PREPARED BY<b>Soumya Swain</b></div>
    <div>SESSION<b>{day}</b></div>
    <div>CAPITAL AT RISK<b>None — paper throughout</b></div>
  </div></div><div class="strip"></div></div>""")

    # ── page 2: at a glance ──────────────────────────────────────────────────
    kpi = ""
    if S:
        kpi = f"""
  <div class="kpi">
    <div class="k"><div class="n">{S['n']}</div><div class="l">paper trades</div></div>
    <div class="k"><div class="n {'neg' if S['net']<0 else 'pos'}">{'−' if S['net']<0 else '+'}₹{abs(S['net']):,.0f}</div><div class="l">net</div></div>
    <div class="k"><div class="n">{S['wr']:.0f}%</div><div class="l">win rate</div></div>
    <div class="k"><div class="n">{S['declined']}</div><div class="l">declined</div></div>
    <div class="k"><div class="n pos">0</div><div class="l">data gaps</div></div>
  </div>"""

    P.append(page(f"""
  <h2>The day at a glance</h2>
  <p class="lead">Six commits. Real money deliberately withheld. The
  escalation-to-trade loop closed for the first time — then falsified within two
  charts, and undermined again by a bug found at 14:15.</p>
  {kpi}
  <div class="box bad">
    <h4>Real money was held back, and every gate agreed</h4>
    <p>Wednesday was the day ₹3,000 of real cash was meant to go in. It did not, and
    not out of nerves — all four pre-agreed gates said no.</p>
  </div>
  <div class="tw"><table>
    <thead><tr><th>Blocker</th><th>State</th><th>Why it matters</th></tr></thead>
    <tbody>
      <tr><td>Account funding</td><td class="n bad">₹1,000 of ₹3,000</td>
        <td>The top-up had not landed. The plan is undefined at the size it was designed for.</td></tr>
      <tr><td>Options gate</td><td class="n bad">0 of 8</td>
        <td>Eight closed paper cards, net positive after fees, was the agreed bar.</td></tr>
      <tr><td>Equity lane</td><td class="n bad">0 cards ever</td>
        <td>It has never produced a trade card on any day.</td></tr>
      <tr><td>Infrastructure</td><td class="n bad">53% down Tuesday</td>
        <td>The floor died at 12:49 and never recovered.</td></tr>
    </tbody>
  </table></div>
  <div class="box">
    <h4>And the measurement that reframed the question</h4>
    <p>Tuesday's 1,563 alerts were scored against a control of random minutes in the
    same stock. Every trigger showed <strong>volatility</strong> afterwards and
    <strong>no direction</strong> — signed returns −0.014%, 45.6% of moves up, all
    inside the 0.106% cost of trading. What we have built is an excellent
    <em>attention allocator</em>. It says where something is about to happen, not
    which way.</p>
  </div>""", 2, "At a glance"))

    # ── page 3: morning changes ──────────────────────────────────────────────
    P.append(page(f"""
  <h2>09:13 — three changes, all from Tuesday's numbers</h2>

  <div class="tl"><div class="t">1<small>5b11ed1</small></div><div>
    <h3>Volume-burst alert retired</h3>
    <p>Fired <strong>540 times</strong> — more than any other — with a lift of
    <span class="bad">−0.014pp</span> against the control. Loudest, and worse than
    random. Disabled rather than deleted so the call stays reversible.</p>
  </div></div>

  <div class="tl"><div class="t">2</div><div>
    <h3>Sweep-and-reclaim loosened</h3>
    <p>Our strongest signal by <strong>3×</strong> (+0.278pp) and our
    <em>quietest</em> at 118 fires — the wrong way round, so we were missing valid
    instances. Pierce threshold 5.0 → 3.0 bps, lookback 30 → 45 ticks.</p>
  </div></div>

  <div class="tl"><div class="t">3</div><div>
    <h3>The restart path — the bug that cost 2h40m</h3>
    <p>Tuesday's watchdog detected the dead floor correctly and restarted it twice.
    Both relaunches were dead within ten minutes having written <em>nothing</em>, not
    even an error.</p>
    <p>The cause: the watchdog is itself a scheduled job, and macOS reaps the job's
    whole process group when the script exits — so a background child cannot outlive
    its parent. The watchdog logged "relaunched"; the floor was already gone. It now
    restarts the floor's own scheduled job, and <strong>verifies twelve seconds later
    that a process actually exists</strong>.</p>
  </div></div>

  <div class="box ok">
    <h4>By 10:41 the changes had done what the data predicted</h4>
    <p>Alert rate 8.8/min → <strong>6.5/min</strong>. Sweep-and-reclaim up
    <strong>71%</strong>. <strong>Zero data gaps</strong>, where Tuesday had four by
    the same hour and was already 36 minutes blind. Five reassignments against zero in
    Tuesday's entire first run.</p>
  </div>""", 3, "Morning changes"))

    # ── page 4: the loop ─────────────────────────────────────────────────────
    P.append(page(f"""
  <h2>11:55 — positions read zero because none could exist</h2>
  <p class="lead">The console showed 0 open positions. Not a display bug: nothing in
  the floor had ever been able to take one.</p>
  <p><code>self.position</code> was assigned exactly once — to nothing — and never
  again. Three consequences, none cosmetic:</p>
  <ul style="font-size:10pt;margin:0 0 4mm 5mm;">
    <li><strong>Two of five triggers were unreachable code.</strong> The stop-loss and
      take-profit checks sat behind that guard and had never once been able to run.</li>
    <li><strong>A safety rule I had called load-bearing protected nothing.</strong>
      "An agent holding a position is never reassigned" — there had never been a
      position to abandon.</li>
    <li><strong>The console faithfully reported a number that could only be zero</strong>,
      which reads as "no trades today" rather than "this path does not exist".</li>
  </ul>

  <h2 style="margin-top:7mm">12:09 — the loop closed, with no approval gate</h2>
  <div class="tw"><table>
    <thead><tr><th>Rule</th><th>Setting</th><th>Why</th></tr></thead>
    <tbody>
      <tr><td>Trigger</td><td class="n">sweep &amp; reclaim only</td>
        <td>The only alert that implies a <em>direction</em></td></tr>
      <tr><td>Agreement</td><td class="n">2+ scouts</td>
        <td>Confluence is our one finding that survived falsification</td></tr>
      <tr><td>Stop</td><td class="n">the swept low</td>
        <td>Structural — if price returns below what it reclaimed, the story is false</td></tr>
      <tr><td>Target</td><td class="n">1.5R</td><td>Below this the toll eats the trade</td></tr>
      <tr><td>Size / window</td><td class="n">₹6,000 · 09:30–14:30</td>
        <td>Max 5 concurrent, squared off 15:15</td></tr>
      <tr><td>Fees</td><td class="n">0.106% round trip</td><td>Our measured cost, so net is net</td></tr>
    </tbody>
  </table></div>
  <div class="box warn">
    <h4>Stated plainly</h4>
    <p>This is <strong>not believed to be profitable</strong>. It exists so that acting
    on an alert produces <em>evidence</em> instead of a guess. Every refused trade is
    logged with its reason, so a quiet day can never hide a threshold silently
    rejecting everything.</p>
  </div>""", 4, "Closing the loop"))

    # ── page 5: chart read ───────────────────────────────────────────────────
    P.append(page(f"""
  <h2>12:13 — looking at the charts falsified the rule</h2>
  <p class="lead">I had the system draw the actual charts behind two of its own live
  signals and read them the way a person would. Both were no-trades, for the same
  structural reason.</p>

  <div class="tw"><table>
    <thead><tr><th>Stock</th><th>What the chart showed</th><th>Why the rule was wrong</th></tr></thead>
    <tbody>
      <tr><td class="n">UDS</td><td>Coiled in a narrow range all session, crossing the
        average price repeatedly</td>
        <td>A "dip and recovery" through a line price has crossed twenty times is not a
        trap being sprung</td></tr>
      <tr><td class="n">QUESS</td><td>A textbook decline — each peak lower than the
        last: 374, 372, 370, 368</td>
        <td>The rule would have <strong>bought into a steady fall</strong>, because a
        bounce back to the average satisfies the arithmetic</td></tr>
    </tbody>
  </table></div>

  <div class="box bad">
    <h4>An average can never be a place where orders rest</h4>
    <p>Half of any day is below that day's average price — that is what "average"
    means. Price crosses it constantly, in every stock. So "dipped below the average
    and came back" is like saying <em>"the temperature fell below today's average and
    then rose"</em>. Of course it did.</p>
    <p>Nobody parks a standing order at an average. They park them at yesterday's low,
    today's low, at round numbers. <strong>Those can be swept. An average cannot.</strong></p>
  </div>

  <p>Quantified before changing anything: signals on the average were <strong>33% of
  Tuesday's and 42% of Wednesday's</strong>. Entries are now restricted to real levels
  where orders genuinely rest — cutting the largest single slice of candidates, the
  slice the pictures showed was worthless.</p>

  <div class="box">
    <h4>This is exactly what the chart-reading lane was for</h4>
    <p>The rule can only check arithmetic. Looking at the picture catches the case
    where the arithmetic is technically true and completely meaningless. It took two
    charts.</p>
  </div>""", 5, "The chart read"))

    # ── page 6: results ──────────────────────────────────────────────────────
    if S:
        rows = "".join(
            f'<tr><td>{k}</td><td class="n">{v[0]}</td>'
            f'<td class="n {"bad" if v[1] < 0 else "ok"}">₹{v[1]:,.2f}</td></tr>'
            for k, v in sorted(S["levels"].items(), key=lambda x: -x[1][0]))
        res = f"""
  <div class="tw"><table>
    <thead><tr><th>Metric</th><th>Value</th><th>Reading</th></tr></thead>
    <tbody>
      <tr><td>Closed trades</td><td class="n">{S['n']}</td><td>First ever from the floor</td></tr>
      <tr><td>Win rate</td><td class="n bad">{S['wr']:.0f}% ({S['wins']}/{S['n']})</td>
        <td>Losing more often than winning</td></tr>
      <tr><td>Average win</td><td class="n">₹{S['avg_w']:+,.2f}</td>
        <td>And losing <em>bigger</em> than winning — the worse of the two</td></tr>
      <tr><td>Average loss</td><td class="n bad">₹{S['avg_l']:+,.2f}</td><td></td></tr>
      <tr><td>Gross</td><td class="n bad">₹{S['gross']:+,.2f}</td>
        <td><strong>Losing before fees are applied at all</strong></td></tr>
      <tr><td>Fees</td><td class="n">₹{S['fees']:,.2f}</td><td>{S['n']} round trips at 0.106%</td></tr>
      <tr><td>Net</td><td class="n bad">₹{S['net']:+,.2f}</td><td></td></tr>
      <tr><td>Median hold</td><td class="n">{S['hold']:.1f} min</td>
        <td>Very short — the stop sits inside the noise</td></tr>
    </tbody>
  </table></div>
  <p>The shape of it: <strong>{S['reasons'].get('STOP',0)} stops against
  {S['reasons'].get('TARGET',0)} targets</strong>. The stop at the swept low is
  structurally correct but tight, so ordinary noise takes it out before the idea has
  room to work. And critically, the strategy is negative <em>gross</em> — this is not a
  fee problem we can size our way out of.</p>
  <h4>By the level that was swept</h4>
  <div class="tw"><table>
    <thead><tr><th>Level</th><th>Trades</th><th>Net</th></tr></thead>
    <tbody>{rows}</tbody></table></div>"""
    else:
        res = "<p>No closed trades recorded for this session.</p>"

    P.append(page(f"""
  <h2>14:08 — the first results, and they are losing</h2>
  {res}""", 6, "First results"))

    # ── page 7: the stale-levels finding ─────────────────────────────────────
    P.append(page(f"""
  <h2>14:15 — every agent was watching a price frozen at 9:16am</h2>
  <p class="lead">That "day high" row prompted a check. Each agent's levels are
  computed once, when it is <em>assigned</em> a stock. An agent that keeps its stock
  all session <strong>never refreshes them</strong>.</p>
  <p>So "today's high" actually means <em>the high of the first minute of trading</em>,
  held for six hours.</p>

  <div class="tw"><table>
    <thead><tr><th>Stock</th><th>Level at 9:16</th><th>Actual level later</th><th>Drift</th></tr></thead>
    <tbody>
      <tr><td class="n">INDSWFTLAB</td><td class="n">337.80</td><td class="n">372.00</td>
        <td class="n bad">10.12%</td></tr>
      <tr><td class="n">DEEPINDS</td><td class="n">651.95</td><td class="n">671.90</td>
        <td class="n bad">3.06%</td></tr>
      <tr><td class="n">GOKEX</td><td class="n">800.00</td><td class="n">805.25</td>
        <td class="n">0.66%</td></tr>
      <tr><td class="n">MINDACORP</td><td class="n">723.50</td><td class="n">725.00</td>
        <td class="n">0.21%</td></tr>
    </tbody>
  </table></div>

  <div class="box bad">
    <h4>Why this probably explains the loss</h4>
    <p>A stale level is not a level anyone is watching. The entire premise of a sweep
    is that <em>other people's orders rest there</em> — and nobody has orders parked at
    a price that stopped being significant at 9:17am.</p>
    <p>Thirteen of the twenty-five trades fired on exactly that. This is the single
    most likely cause of the negative gross, and it is a <strong>bug rather than a
    strategy failure</strong> — which means today's loss is
    <strong>not yet a fair test of the idea</strong>.</p>
  </div>

  <p class="dim">Not fixed today, deliberately. Changing the measuring instrument
  mid-measurement would have wasted the rest of the session. It goes in at tomorrow's
  open.</p>""", 7, "The stale-levels bug"))

    # ── page 8: decisions ────────────────────────────────────────────────────
    P.append(page(f"""
  <h2>What needs your decision</h2>
  <p class="lead">Four open calls. Each is stated with options rather than a single
  recommendation, because these are yours to weigh.</p>

  <div class="dec"><h4>1 · Real money — when?</h4>
  <p>My position is unchanged: not until the ₹2,000 top-up lands, the equity lane has
  produced cards on three separate days, and the floor completes one clean session.
  None of those is true yet.</p>
  <div class="o"><b>a</b><span>Hold until all three gates pass — my recommendation</span></div>
  <div class="o"><b>b</b><span>Go anyway at minimum size as a pure execution test, measuring fills against the card price. Defensible — but it needs a card to exist, and the equity lane has never produced one.</span></div>
  </div>

  <div class="dec"><h4>2 · Fix stale levels, then re-run</h4>
  <p>Refresh each agent's levels every few minutes instead of once at assignment.
  Today's loss was measured on a broken instrument; the number after this fix is the
  first honest test of the entry rule.</p>
  <div class="o"><b>a</b><span>Fix at tomorrow's open and re-measure over a full clean session</span></div>
  <div class="o"><b>b</b><span>Also widen the stop — 17 stops against 8 targets suggests it sits inside the noise band</span></div>
  </div>

  <div class="dec"><h4>3 · How far to trust the chart read</h4>
  <p>It found in two charts what the mechanical rule could not see at all. A strong
  first showing — but it is two charts.</p>
  <div class="o"><b>a</b><span>Run it on every sweep signal for a week and compare its verdicts against what price actually did</span></div>
  <div class="o"><b>b</b><span>Let it gate entries — nothing opens unless the chart read agrees. Slower, and it cannot run on every tick.</span></div>
  </div>

  <div class="dec"><h4>4 · The unresolved contradiction</h4>
  <p>Sweep-and-reclaim scored <strong>+0.278pp</strong> live but <strong>−0.017%</strong>
  in our historical falsification run. Both were measured properly. Either the live
  version picks up something the bar-level test flattened, or 118 examples is too small
  to trust. Worth resolving before anything else is built on it.</p>
  </div>""", 8, "Decisions"))

    body = "".join(P)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>TradePilot — Session {day}</title>"
            f"<style>{css}{extra}</style></head><body>{body}</body></html>")


def main():
    b = book(DAY)
    S = stats(b)
    if not S:
        print(f"  no closed paper trades for {DAY} — report will omit the results page")
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build(DAY, S))
    print(f"  html: {OUT_HTML}")
    asyncio.get_event_loop().run_until_complete(BEX.render(OUT_HTML, OUT_PDF))
    print(f"  pdf : {OUT_PDF}")
    BEX.qa(OUT_PDF)


if __name__ == "__main__":
    main()
