#!/usr/bin/env python3
"""
floor-eod — did the agent floor earn its keep today?

Today's run produces three questions we have never had numbers for. This answers all
three from the floor's own logs plus Kite minute bars, and refuses to answer any of
them if we were blind for too much of the session.

  1. HOW MANY escalations, and were they SIGNAL?
     For every escalation, measure what price actually did in the next 15 minutes,
     against a CONTROL: the same stock, same day, entered at random minutes. A trigger
     that fires before nothing is noise no matter how clever it looks.

  2. ARE THE BRAKES RIGHT?
     Reassignments vs near-misses. Many near-misses and no swaps = too tight. Constant
     swaps with flat escalations = too loose.

  3. DOES SCOUTING BEAT A FIXED LIST?
     For each swap, compare what the stock we moved TO did afterwards against what the
     stock we LEFT did over the same window. That is the only honest test.

    python3 scripts/floor-eod.py [YYYY-MM-DD]
"""
from __future__ import annotations

import json, random, statistics, sys, warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ESC = ROOT / "docs" / "sarathi" / "knowledge" / "escalations"
HORIZON_MIN = 15          # how long after a trigger we judge it
N_CONTROL = 40            # random entries per stock, for the control
BLIND_LIMIT_PCT = 25.0    # refuse to draw conclusions beyond this much blindness

DAY = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")


def bars(symbol, day):
    """Minute bars for one stock on one day, keyed by HH:MM."""
    from prototype.v4 import kite_data as kd
    tok = kd.token_for(symbol)
    if not tok:
        return {}
    d = datetime.strptime(day, "%Y-%m-%d")
    try:
        raw = kd.client().historical_data(tok, d, d + timedelta(days=1), "minute")
    except Exception:
        return {}
    return {str(b["date"])[11:16]: float(b["close"]) for b in raw}


def move_after(series, hhmm, minutes=HORIZON_MIN):
    """Absolute % move over the next `minutes`, and the signed return."""
    keys = sorted(series)
    if hhmm not in series:
        later = [k for k in keys if k >= hhmm]
        if not later:
            return None
        hhmm = later[0]
    i = keys.index(hhmm)
    j = min(i + minutes, len(keys) - 1)
    if j <= i:
        return None
    a, b = series[keys[i]], series[keys[j]]
    return {"abs_pct": abs(b / a - 1) * 100, "ret_pct": (b / a - 1) * 100}


def control(series, n=N_CONTROL, seed=7):
    """What a RANDOM minute in the same stock on the same day would have looked like.

    Without this every number below is unreadable: a 0.4% average move after a
    trigger sounds impressive until you learn the stock moved 0.4% after any random
    minute too. The control is what turns a statistic into a finding.
    """
    keys = sorted(series)
    if len(keys) < HORIZON_MIN + 5:
        return None
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        k = rnd.choice(keys[:-HORIZON_MIN])
        m = move_after(series, k)
        if m:
            out.append(m["abs_pct"])
    return statistics.mean(out) if out else None


def reconstruct(day):
    """Rebuild what we can from the floor's own stdout when it died mid-session.

    The floor narrates as it goes — gap opens/closes, reassignments, near-miss
    counts — so a crash costs us the tidy summary but not the evidence.
    """
    import re
    out = {"reassignments": [], "data_gaps": [], "near_miss_total": None,
           "blind_seconds": None, "reconstructed": True}
    logs = sorted(Path(ROOT / "logs").glob(f"agent-floor-{day}*.log"))
    closed_secs, opened, closed = 0.0, 0, 0
    for lg in logs:
        for line in lg.read_text(errors="ignore").splitlines():
            if "DATA GAP OPENED" in line:
                opened += 1
                m = re.search(r"(\d\d:\d\d:\d\d) DATA GAP OPENED \(([A-Z_]+)\): (.*)", line)
                if m:
                    out["data_gaps"].append({"from": m.group(1), "kind": m.group(2),
                                             "detail": m.group(3)[:60]})
            elif "DATA GAP CLOSED" in line:
                closed += 1
                m = re.search(r"after ([\d.]+)s", line)
                if m:
                    closed_secs += float(m.group(1))
                    if out["data_gaps"]:
                        out["data_gaps"][-1]["seconds"] = float(m.group(1))
            elif "REASSIGN" in line:
                m = re.search(r"(\d\d:\d\d:\d\d) REASSIGN (\S+) \(([\d.]+), (\d+) scouts\)"
                              r" -> (\S+) \(([\d.]+), (\d+) scouts\)", line)
                if m:
                    out["reassignments"].append(
                        {"at": m.group(1), "out": m.group(2),
                         "out_score": float(m.group(3)), "out_agree": int(m.group(4)),
                         "in": m.group(5), "in_score": float(m.group(6)),
                         "agree": int(m.group(7))})
            elif "near-misses" in line:
                m = re.search(r"\((\d+) near-misses", line)
                if m:
                    out["near_miss_total"] = int(m.group(1))
    # Copies overlap: agent-floor-DAY_run1.log is the head of agent-floor-DAY.log,
    # so globbing both listed every early gap twice. Dedupe on identity, not on file.
    def uniq(rows, key):
        seen, keep = set(), []
        for r in rows:
            k = key(r)
            if k not in seen:
                seen.add(k); keep.append(r)
        return keep
    out["data_gaps"] = uniq(out["data_gaps"], lambda g: (g["from"], g["kind"]))
    out["reassignments"] = uniq(out["reassignments"],
                                lambda r: (r["at"], r["out"], r["in"]))
    opened = len(out["data_gaps"])
    out["blind_seconds"] = sum(g.get("seconds", 0) for g in out["data_gaps"])
    out["gaps_never_closed"] = sum(1 for g in out["data_gaps"] if "seconds" not in g)
    closed = opened - out["gaps_never_closed"]
    print(f"    recovered: {len(out['reassignments'])} reassignments, "
          f"{opened} gaps opened ({closed} closed, {opened-closed} still open at death), "
          f"near-misses {out['near_miss_total']}")
    return out


def main():
    summ = ESC / f"{DAY}_summary.json"
    jl = ESC / f"{DAY}.jsonl"
    if not summ.exists() and not jl.exists():
        print(f"  no floor output for {DAY} — did the floor run?")
        return
    S = json.loads(summ.read_text()) if summ.exists() else None
    if S is None:
        # THE SUMMARY IS ONLY WRITTEN ON A CLEAN SHUTDOWN. On 2026-08-25 the floor
        # died at 12:49 and never reached that path, so this file did not exist —
        # and an earlier version of this script defaulted to {} and printed
        # "0 data gaps, 0 reassignments, 0 near-misses" as though they had been
        # MEASURED. All three were wrong: the logs showed 7, 12 and 53.
        #
        # A missing measurement must never render as a zero. Reconstruct what the
        # floor did write, and label the rest UNKNOWN.
        print(f"\n  ⚠ NO SUMMARY FILE for {DAY} — the floor did not shut down cleanly.")
        print("    Reconstructing from the session logs; anything unrecoverable is")
        print("    reported as UNKNOWN, never as zero.")
        S = reconstruct(DAY)
    events = []
    if jl.exists():
        for line in jl.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except Exception:
                pass

    # ── 0. how much of the day could we actually see? ────────────────────────
    blind = S.get("blind_seconds")
    unknown = S.get("reconstructed", False)
    gaps = S.get("data_gaps", [])
    session_s = 375 * 60
    blind_pct = (blind / session_s * 100) if blind is not None else None
    print(f"\n  ═══ FLOOR EOD — {DAY} ═══")
    if blind is None:
        print(f"  data gaps: {len(gaps)}  |  blind time UNKNOWN (not measured)")
    else:
        tail = " (LOWER BOUND — gaps still open at death are not counted)" \
            if S.get("gaps_never_closed") else ""
        print(f"  data gaps: {len(gaps)}  |  blind >= {blind/60:.1f} min "
              f"({blind_pct:.1f}% of the session){tail}")
    if blind_pct is not None and blind_pct > BLIND_LIMIT_PCT:
        print(f"  ⚠ MORE THAN {BLIND_LIMIT_PCT:.0f}% BLIND — counts below understate "
              f"reality and must not be read as a verdict on the thresholds.")
    for g in gaps[:6]:
        print(f"     {g.get('from')}–{g.get('to','open')} "
              f"{g.get('seconds','?')}s  {g.get('kind')}: {g.get('detail','')[:50]}")

    # ── 1. escalation volume and quality ─────────────────────────────────────
    print(f"\n  1. ESCALATIONS: {len(events)}")
    by_trig, by_sym = {}, {}
    for e in events:
        by_trig[e["trigger"].split(":")[0]] = by_trig.get(e["trigger"].split(":")[0], 0) + 1
        by_sym[e["symbol"]] = by_sym.get(e["symbol"], 0) + 1
    for k, v in sorted(by_trig.items(), key=lambda x: -x[1]):
        print(f"     {k:<20} {v:>4}")
    if by_sym:
        loud = sorted(by_sym.items(), key=lambda x: -x[1])[:3]
        print(f"     loudest stocks: " + ", ".join(f"{s}({n})" for s, n in loud))

    if not events:
        print("     nothing fired. Either the market was still or the thresholds are "
              "too high — the data-gap line above says which.")
        return

    print(f"\n  2. WERE THEY SIGNAL? (move in the {HORIZON_MIN}min after, vs a random "
          f"minute in the same stock)")
    cache, rows = {}, []
    for e in events:
        s = e["symbol"]
        if s not in cache:
            cache[s] = bars(s, DAY)
        ser = cache[s]
        if not ser:
            continue
        m = move_after(ser, e["at"][:5])
        c = control(ser)
        if m and c:
            rows.append({"trigger": e["trigger"].split(":")[0],
                         "abs": m["abs_pct"], "ret": m["ret_pct"], "ctrl": c})
    if rows:
        tot_a = statistics.mean(r["abs"] for r in rows)
        tot_c = statistics.mean(r["ctrl"] for r in rows)
        print(f"     overall   after-trigger {tot_a:.3f}%   random {tot_c:.3f}%   "
              f"lift {tot_a-tot_c:+.3f}pp   n={len(rows)}")
        per = {}
        for r in rows:
            per.setdefault(r["trigger"], []).append(r)
        for k, v in sorted(per.items(), key=lambda x: -len(x[1])):
            a = statistics.mean(x["abs"] for x in v)
            c = statistics.mean(x["ctrl"] for x in v)
            verdict = "SIGNAL" if a > c * 1.15 else ("noise" if a < c else "flat")
            print(f"     {k:<20} n={len(v):>3}  after {a:.3f}%  random {c:.3f}%  "
                  f"lift {a-c:+.3f}pp  {verdict}")
    else:
        print("     could not fetch minute bars to judge — check the Kite session.")

    # ── 3. brakes ────────────────────────────────────────────────────────────
    sw = S.get("reassignments", [])
    nm = S.get("near_miss_total")
    print(f"\n  3. THE BRAKES: {len(sw)} reassignments, "
          f"{nm if nm is not None else 'UNKNOWN'} near-misses")
    if nm is None:
        print("     cannot judge — near-miss count not recovered.")
    elif not sw and nm > 20:
        print("     TOO TIGHT — challengers kept coming close and never got in.")
    elif len(sw) > 12:
        print("     TOO LOOSE — the floor churned; check escalations did not suffer.")
    else:
        print("     within the intended band.")

    # ── 4. did scouting pay? ─────────────────────────────────────────────────
    if sw:
        print(f"\n  4. DID THE SWAPS PAY? (move after the swap: in vs out)")
        wins = 0
        judged = 0
        for r in sw:
            for s in (r["in"], r["out"]):
                if s not in cache:
                    cache[s] = bars(s, DAY)
            mi = move_after(cache.get(r["in"], {}), r["at"][:5])
            mo = move_after(cache.get(r["out"], {}), r["at"][:5])
            if not mi or not mo:
                continue
            judged += 1
            better = mi["abs_pct"] > mo["abs_pct"]
            wins += better
            print(f"     {r['at']}  {r['out']:<11}{mo['abs_pct']:>6.2f}%  ->  "
                  f"{r['in']:<11}{mi['abs_pct']:>6.2f}%   "
                  f"{'better' if better else 'worse'}")
        if judged == 0:
            print(f"     UNMEASURABLE — no minute bars retrieved for any of the "
                  f"{len(sw)} swaps. Not a score of 0; a failed measurement.")
            print("     Re-run once the Kite session is live.")
        else:
            print(f"     swaps that moved to a livelier stock: {wins}/{judged} judged "
                  f"(of {len(sw)} total)")
            print("     (one day is not a verdict — this accumulates)")


if __name__ == "__main__":
    main()
