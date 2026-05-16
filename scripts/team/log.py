"""
Team activity + audit logger.

Shared by all 9 agents. Append-only JSONL files.

  log_activity(agent, kind, summary, links=None)
    → docs/team/activity/YYYY-MM-DD.jsonl

  log_audit(agent, action, decision, subject, evidence, reason, vetoable_by=None)
    → docs/team/audit/YYYY-MM-DD.jsonl
    → docs/sarathi/ledger/YYYY-MM-DD.jsonl (mirror for Sarathi family decisions)

  update_status(agent, status, last_action=None, next_due=None, extra=None)
    → docs/team/status/<agent>.json (overwritten each call)
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACTIVITY_DIR = PROJECT_ROOT / "docs" / "team" / "activity"
AUDIT_DIR    = PROJECT_ROOT / "docs" / "team" / "audit"
STATUS_DIR   = PROJECT_ROOT / "docs" / "team" / "status"
SARATHI_DIR  = PROJECT_ROOT / "docs" / "sarathi" / "ledger"

for d in (ACTIVITY_DIR, AUDIT_DIR, STATUS_DIR, SARATHI_DIR):
    d.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    # IST-aware timestamp; works across all platforms without external deps
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).isoformat(timespec="seconds")


def _date_stamp() -> str:
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d")


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    # Single-line append, atomic on POSIX for sub-PIPE_BUF writes
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_activity(agent: str, kind: str, summary: str,
                 links: dict[str, str] | None = None) -> None:
    """Append a non-blocking activity event."""
    record = {
        "ts": _now_iso(),
        "agent": agent,
        "kind": kind,
        "summary": summary,
        "links": links or {},
    }
    _append_jsonl(ACTIVITY_DIR / f"{_date_stamp()}.jsonl", record)


def log_audit(agent: str, action: str, decision: str,
              subject: str, evidence: dict[str, Any],
              reason: str, vetoable_by: list[str] | None = None,
              rule_family: str | None = None) -> dict:
    """Append a blocking-or-gating decision. Returns the record (for callers)."""
    assert decision in ("PASS", "WARN", "BLOCK", "REJECT", "ESCALATE", "OVERRIDE"), \
        f"Unknown decision: {decision}"
    record = {
        "ts": _now_iso(),
        "agent": agent,
        "action": action,
        "decision": decision,
        "subject": subject,
        "evidence": evidence,
        "reason": reason,
        "vetoable_by": vetoable_by or [],
        "rule_family": rule_family,
        "override": None,
    }
    _append_jsonl(AUDIT_DIR / f"{_date_stamp()}.jsonl", record)
    if rule_family and rule_family.startswith("SARATHI-"):
        _append_jsonl(SARATHI_DIR / f"{_date_stamp()}.jsonl", record)
    return record


def update_status(agent: str, status: str,
                  last_action: str | None = None,
                  next_due: str | None = None,
                  extra: dict[str, Any] | None = None) -> None:
    """Overwrite the agent's status card. Used by the /team dashboard."""
    assert status in ("idle", "running", "blocked", "warning", "scheduled", "paged"), \
        f"Unknown status: {status}"
    card = {
        "agent": agent,
        "status": status,
        "ts": _now_iso(),
        "last_action": last_action,
        "next_due": next_due,
    }
    if extra:
        card.update(extra)
    path = STATUS_DIR / f"{agent}.json"
    # Unique tmp filename to prevent races when multiple processes update
    # the same agent's status file concurrently (e.g. parallel Sarathi calls).
    tmp = path.with_suffix(f".json.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic on POSIX


def read_status(agent: str) -> dict | None:
    path = STATUS_DIR / f"{agent}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def tail_activity(n: int = 60, since_ts: str | None = None) -> list[dict]:
    """Read newest N activity events across today + yesterday."""
    out: list[dict] = []
    today = _date_stamp()
    files = sorted(ACTIVITY_DIR.glob("*.jsonl"))[-2:]  # yesterday + today
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if since_ts and r["ts"] <= since_ts:
                continue
            out.append(r)
    out.sort(key=lambda r: r["ts"], reverse=True)
    return out[:n]


def tail_audit(n: int = 60, decision_filter: list[str] | None = None) -> list[dict]:
    """Read newest N audit events. Optional filter (e.g. only BLOCK)."""
    out: list[dict] = []
    files = sorted(AUDIT_DIR.glob("*.jsonl"))[-2:]
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if decision_filter and r["decision"] not in decision_filter:
                continue
            out.append(r)
    out.sort(key=lambda r: r["ts"], reverse=True)
    return out[:n]


if __name__ == "__main__":
    # Quick smoke test
    log_activity("architect", "test", "log helper smoke test")
    log_audit("architect", "self-test", "PASS",
              subject="scripts/team/log.py",
              evidence={"smoke": "ok"},
              reason="Initial bootstrap",
              vetoable_by=[],
              rule_family=None)
    update_status("architect", "idle", last_action="bootstrap log helper",
                  next_due="next code review")
    print("OK")
