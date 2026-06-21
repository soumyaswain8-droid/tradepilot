#!/usr/bin/env python3
"""
v4 leakage watchdog — observes how much v4 leaves on the table per scan.

Tails v4-YYYY-MM-DD.log + reads docs/paper-trades/v4/YYYY-MM-DD.json.
For each scan: tracks BUY count, filter drops (held/corp_ban/loss_cap/watchlist),
sizer drops (floor), final deployed count, idle capital, theoretical leakage.

Output:
  logs/v4-leakage-watchdog-YYYY-MM-DD.log    human-readable
  docs/v4-leakage/YYYY-MM-DD.jsonl           machine JSONL (one row per scan)

Telegram: end-of-day digest at 15:25 IST with total leakage estimate.
"""
import json, re, time, os, sys, datetime, glob
from pathlib import Path

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")
TODAY = datetime.date.today().isoformat()
LOG_FILE = ROOT / f"logs/v4-{TODAY}.log"
STATE_FILE = ROOT / f"docs/paper-trades/v4/{TODAY}.json"
OUT_DIR = ROOT / "docs/v4-leakage"
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSONL_FILE = OUT_DIR / f"{TODAY}.jsonl"
HUMAN_LOG = ROOT / f"logs/v4-leakage-watchdog-{TODAY}.log"

POLL_SEC = 60
END_OF_DAY = datetime.time(15, 35)
DIGEST_TIME = datetime.time(15, 25)

RE_SCORING = re.compile(
    r"(\d{2}:\d{2}:\d{2}).*?Scoring complete:\s*(\d+)\s*scored.*?BUY=(\d+)\s*HOLD=(\d+)\s*AVOID=(\d+)"
)
RE_DEPLOY = re.compile(
    r"(\d{2}:\d{2}:\d{2}).*?DEPLOYING Rs ([\d,]+).*?into (\d+) v4 BUY signals"
)
RE_SKIP_HELD = re.compile(r"Already holding all v4 BUY signals")
RE_SKIP_REASON = re.compile(r"^\s+(\S+):\s+SKIPPED\s+\(([^)]+)\)")
RE_NO_SIZED = re.compile(r"Position sizer returned no positions")


def telegram(msg: str) -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    token = chat = ""
    for line in env.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("TELEGRAM_CHAT_ID="):
            chat = line.split("=", 1)[1].strip().strip('"')
    if not (token and chat):
        return
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=5
        )
    except Exception:
        pass


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def parse_scans(log_path: Path) -> list[dict]:
    """Walk the v4 log forward, building one scan record per scoring->deploy block."""
    if not log_path.exists():
        return []
    text = log_path.read_text(errors="ignore")
    scans = []
    cur = None
    skip_lines = []  # symbol-level SKIPPED lines that fall between scoring + deploy
    for raw in text.splitlines():
        m_score = RE_SCORING.search(raw)
        if m_score:
            # close previous incomplete scan
            if cur is not None:
                cur["skips_by_reason"] = _bucket_skips(skip_lines)
                scans.append(cur)
            cur = {
                "ts": m_score.group(1),
                "scored": int(m_score.group(2)),
                "buy": int(m_score.group(3)),
                "hold": int(m_score.group(4)),
                "avoid": int(m_score.group(5)),
                "deployed": None,
                "deployed_capital_rs": None,
                "no_new_buys": False,
                "no_sized": False,
            }
            skip_lines = []
            continue
        m_skip = RE_SKIP_REASON.match(raw)
        if m_skip and cur is not None:
            skip_lines.append((m_skip.group(1), m_skip.group(2)))
            continue
        if RE_SKIP_HELD.search(raw) and cur is not None:
            cur["no_new_buys"] = True
            continue
        m_dep = RE_DEPLOY.search(raw)
        if m_dep and cur is not None:
            cur["deployed_capital_rs"] = int(m_dep.group(2).replace(",", ""))
            cur["deployed"] = int(m_dep.group(3))
            cur["skips_by_reason"] = _bucket_skips(skip_lines)
            scans.append(cur)
            cur = None
            skip_lines = []
            continue
        if RE_NO_SIZED.search(raw) and cur is not None:
            cur["no_sized"] = True
            cur["deployed"] = 0
            cur["skips_by_reason"] = _bucket_skips(skip_lines)
            scans.append(cur)
            cur = None
            skip_lines = []
    if cur is not None:
        cur["skips_by_reason"] = _bucket_skips(skip_lines)
        scans.append(cur)
    return scans


def _bucket_skips(items: list[tuple[str, str]]) -> dict:
    buckets = {"watchlist": 0, "corp_ban": 0, "loss_cap": 0, "other": 0}
    for sym, reason in items:
        r = reason.lower()
        if "watchlist" in r:
            buckets["watchlist"] += 1
        elif "blacklist" in r or "losses" in r:
            buckets["loss_cap"] += 1
        elif "corp" in r or "ban" in r or "split" in r or "bonus" in r or "dividend" in r:
            buckets["corp_ban"] += 1
        else:
            buckets["other"] += 1
    return buckets


def compute_leakage(scan: dict, state: dict) -> dict:
    """Estimate Rs leakage = unused-capital × today's avg intraday return.

    We approximate avg return from v4's open positions' MTM if available; else 0.
    """
    held = len(state.get("positions", []))
    cash = float(state.get("cash", 0) or 0)
    deployed_capital = float(state.get("total_deployed", 0) or 0)
    deployed_in_scan = scan.get("deployed_capital_rs") or 0
    idle = max(cash - deployed_in_scan, 0)

    # Filter funnel
    skips = scan.get("skips_by_reason", {})
    filtered_drops = sum(skips.values())  # corp_ban + loss_cap + watchlist + other
    new_buys_estimate = max(scan["buy"] - held - filtered_drops, 0)
    sizer_drops = max(new_buys_estimate - (scan.get("deployed") or 0), 0)

    # Theoretical leakage proxy: idle capital × intraday return of held positions
    # (use realized_pnl + unrealized as % of deployed_capital as the alpha proxy)
    realized = float(state.get("realized_pnl", 0) or 0)
    # Unrealized estimate: if positions exist and deployed_capital > 0, take 0 (we only have realized in state)
    alpha_pct = (realized / deployed_capital * 100) if deployed_capital > 0 else 0.0
    leakage_rs = idle * alpha_pct / 100.0

    return {
        "held": held,
        "cash": round(cash, 0),
        "deployed_in_scan": deployed_in_scan,
        "idle_capital": round(idle, 0),
        "filtered_drops": filtered_drops,
        "skips_by_reason": skips,
        "new_buys_estimate": new_buys_estimate,
        "sizer_drops": sizer_drops,
        "alpha_pct": round(alpha_pct, 3),
        "leakage_rs_estimate": round(leakage_rs, 0),
    }


def emit(scan: dict, leakage: dict, human: list[str]) -> None:
    row = {
        "scan_ts": scan["ts"],
        "watchdog_ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "buy": scan["buy"],
        "deployed": scan.get("deployed"),
        "no_new_buys": scan.get("no_new_buys", False),
        "no_sized": scan.get("no_sized", False),
        **leakage,
    }
    with JSONL_FILE.open("a") as f:
        f.write(json.dumps(row) + "\n")
    line = (
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] scan@{scan['ts']}  "
        f"BUY={scan['buy']:>2}  held={leakage['held']}  "
        f"filter_drops={leakage['filtered_drops']} ({leakage['skips_by_reason']})  "
        f"new~{leakage['new_buys_estimate']}  sizer_drops={leakage['sizer_drops']}  "
        f"deployed={scan.get('deployed')}  idle=Rs {leakage['idle_capital']:,.0f}  "
        f"leak~Rs {leakage['leakage_rs_estimate']:,.0f}"
    )
    human.append(line)
    with HUMAN_LOG.open("a") as f:
        f.write(line + "\n")


def main() -> None:
    print(f"[watchdog] starting at {datetime.datetime.now().isoformat()}")
    print(f"  log:   {LOG_FILE}")
    print(f"  state: {STATE_FILE}")
    print(f"  out:   {JSONL_FILE}")
    print(f"  human: {HUMAN_LOG}")
    HUMAN_LOG.write_text(f"# v4 leakage watchdog — started {datetime.datetime.now().isoformat()}\n")
    seen = set()
    sent_digest = False
    while True:
        now = datetime.datetime.now()
        if now.time() >= END_OF_DAY:
            print("[watchdog] EOD reached, exiting")
            break
        scans = parse_scans(LOG_FILE)
        state = load_state()
        new_scans = []
        for s in scans:
            key = (s["ts"], s.get("buy"), s.get("deployed"))
            if key in seen:
                continue
            seen.add(key)
            new_scans.append(s)
        for s in new_scans:
            leakage = compute_leakage(s, state)
            emit(s, leakage, [])
        # Daily digest at 15:25
        if not sent_digest and now.time() >= DIGEST_TIME:
            digest = build_digest(scans, state)
            with HUMAN_LOG.open("a") as f:
                f.write("\n" + digest + "\n")
            telegram(digest)
            sent_digest = True
            print("[watchdog] digest sent")
        time.sleep(POLL_SEC)


def build_digest(scans: list[dict], state: dict) -> str:
    if not scans:
        return "v4 leakage watchdog: no scans observed today"
    total_buy = sum(s.get("buy") or 0 for s in scans)
    total_deployed = sum(s.get("deployed") or 0 for s in scans)
    total_filter_drops = sum(sum((s.get("skips_by_reason") or {}).values()) for s in scans)
    held = len(state.get("positions", []))
    realized = float(state.get("realized_pnl", 0) or 0)
    deployed_capital = float(state.get("total_deployed", 0) or 0)
    cash = float(state.get("cash", 0) or 0)
    last = scans[-1]
    last_leak = compute_leakage(last, state)
    avg_deploy_rate = (total_deployed / total_buy * 100) if total_buy else 0
    return (
        f"📊 v4 LEAKAGE WATCHDOG — EOD digest\n"
        f"Scans observed: {len(scans)}\n"
        f"Total BUYs scored: {total_buy}\n"
        f"Total deployed across scans: {total_deployed}\n"
        f"Deploy rate: {avg_deploy_rate:.1f}%\n"
        f"Filter drops total: {total_filter_drops} (held/corp_ban/loss_cap/watchlist)\n"
        f"Currently held: {held} positions\n"
        f"Realized P&L: Rs {realized:,.0f}\n"
        f"Cash idle (latest): Rs {last_leak['idle_capital']:,.0f}\n"
        f"Last scan @ {last['ts']}: BUY={last['buy']} → deployed={last.get('deployed')}\n"
        f"Estimated leakage: Rs {last_leak['leakage_rs_estimate']:,.0f}\n"
        f"Detail: docs/v4-leakage/{TODAY}.jsonl"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[watchdog] interrupted")
    except Exception as e:
        print(f"[watchdog] fatal: {e}")
        sys.exit(1)
