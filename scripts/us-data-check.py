#!/usr/bin/env python3
"""
us-data-check — run the US feed cross-check before the US session and page on trouble.

WHY IT RUNS AT 18:30 IST
The US engine starts at 19:00 IST (com.tradepilot.us-paper-trade). Checking the data
AFTER the engine has already traded on it is an autopsy, not a guard. Thirty minutes
is enough to see the page and pull the engine before the open.

WHY IT IS SILENT ON SUCCESS
Same reason kite-token-reminder is: a job that reports "fine" every evening trains you
to swipe the notification away, and the one evening it says something different gets
swiped too. It pages on trouble and on RECOVERY, nothing else.

DEDUPE, AND WHY IT ESCALATES ANYWAY
A repeated identical alert is noise — the ML pager storm in July proved that. So an
identical problem signature is suppressed. But suppression that never ends is just a
silent failure with extra steps, so a problem still present after MAX_SUPPRESSED runs
pages again regardless. Silence must be earned every few days, not granted once.

Exit codes:  0 = pass or suppressed-repeat   1 = problem paged   2 = could not run
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "prototype" / "data" / "us_cache" / "datacheck_state.json"
LOG = ROOT / "logs" / "auto" / "v2" / "us-data-check.log"
MAX_SUPPRESSED = 3
SAMPLE = 17          # the whole verifiable subset on FMP's free plan


def telegram(msg: str) -> bool:
    tok = chat = None
    env = ROOT / ".env"
    if env.exists():
        for ln in env.read_text().splitlines():
            if ln.startswith("TELEGRAM_BOT_TOKEN="):
                tok = ln.split("=", 1)[1].strip().strip('"')
            elif ln.startswith("TELEGRAM_CHAT_ID="):
                chat = ln.split("=", 1)[1].strip().strip('"')
    if not (tok and chat):
        print("  no telegram credentials in .env", file=sys.stderr)
        return False
    try:
        # PLAIN TEXT. A Markdown message died on "can't parse entities" on
        # 2026-07-28 because a payload contained brackets, and never arrived.
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print(f"  telegram send failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2))


def log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a") as f:
        f.write(f"{stamp}  {line}\n")
    print(f"  {line}")


def signature(res: dict) -> str:
    """What makes two runs 'the same problem'. Deliberately excludes counts and
    prices — a divergence that grows from 0.6% to 0.9% is the same fault, and
    repaging on the drift would be exactly the noise dedupe exists to stop."""
    parts = [res.get("verdict", "?")]
    parts += [f"stray:{s}" for s in res.get("stray_symbols", [])]
    parts += [f"ext:{e['symbol']}" for e in res.get("extent_shortfall", [])]
    parts += [f"val:{d['symbol']}" for d in res.get("value_divergence", [])]
    return "|".join(sorted(parts))


def describe(res: dict) -> str:
    ts = datetime.now().strftime("%d %b, %H:%M IST")
    out = [f"TradePilot US data check - {ts}", ""]
    if res["verdict"] == "inconclusive":
        out.append(f"INCONCLUSIVE: only {res['checked']}/{res['requested']} symbols "
                   f"could be compared. This is NOT a pass - the feed is unverified.")
    else:
        out.append(f"PROBLEM FOUND ({res['checked']}/{res['requested']} compared)")
    for s in res.get("stray_symbols", [])[:6]:
        out.append(f"  CONTAMINATION: {s} present but never requested")
    for e in res.get("extent_shortfall", [])[:6]:
        out.append(f"  SHORT HISTORY: {e['symbol']} {e['ours']} bars vs "
                   f"{e['reference']} at reference ({e['ratio']:.0%})")
    for d in res.get("value_divergence", [])[:6]:
        out.append(f"  PRICE DIVERGE: {d['symbol']} {d['date']} ours {d['ours']} "
                   f"vs {d['reference']} ({d['pct']:.2f}%)")
    out += ["", "US engine starts 19:00 IST. Data is suspect - consider holding it.",
            "Check: python3 prototype/us/verify_source.py"]
    return "\n".join(out)


def main() -> int:
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "prototype" / "us" / "verify_source.py"),
             "--sample", str(SAMPLE), "--json"],
            capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        res = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        log("FAIL verify_source timed out after 600s")
        telegram("TradePilot US data check: the verifier TIMED OUT. The feed is "
                 "unverified before tonight's US session.")
        return 2
    except Exception as e:
        log(f"FAIL could not run verify_source: {type(e).__name__}: {e}")
        # A checker that cannot run is not a pass. Say so out loud.
        telegram(f"TradePilot US data check could not run: {type(e).__name__}: {e}. "
                 f"The feed is unverified before tonight's US session.")
        return 2

    verdict = res.get("verdict", "inconclusive")
    sig = signature(res)
    st = load_state()
    prev_sig, suppressed = st.get("signature", ""), int(st.get("suppressed", 0))

    if verdict == "pass":
        log(f"PASS {res['checked']}/{res['requested']} symbols agree, "
            f"{res.get('calls_remaining')} calls left")
        if prev_sig and prev_sig != sig:
            telegram(f"TradePilot US data check: RECOVERED. "
                     f"{res['checked']}/{res['requested']} symbols agree again.")
        save_state({"signature": sig, "suppressed": 0,
                    "last": datetime.now().isoformat(timespec="seconds")})
        return 0

    repeat = (sig == prev_sig)
    if repeat and suppressed < MAX_SUPPRESSED:
        log(f"{verdict.upper()} (repeat {suppressed + 1}/{MAX_SUPPRESSED}, suppressed) {sig}")
        save_state({"signature": sig, "suppressed": suppressed + 1,
                    "last": datetime.now().isoformat(timespec="seconds")})
        return 0

    msg = describe(res)
    if repeat:
        msg += f"\n\n(unchanged for {suppressed + 1} runs - still not fixed)"
    sent = telegram(msg)
    log(f"{verdict.upper()} paged={'yes' if sent else 'FAILED'} {sig}")
    save_state({"signature": sig, "suppressed": 0,
                "last": datetime.now().isoformat(timespec="seconds")})
    return 1


if __name__ == "__main__":
    sys.exit(main())
