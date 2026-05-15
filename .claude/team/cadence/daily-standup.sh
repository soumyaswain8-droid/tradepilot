#!/usr/bin/env bash
# Daily 15:50 IST automated standup card.
# Reads docs/team/status/*.json + activity + audit, emits docs/team/standup/YYYY-MM-DD.md
# Add to cron: 50 15 * * 1-5  (Mon-Fri at 15:50 IST)

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

python3 - <<'PYEOF'
import json, sys, glob, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ist = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(ist).strftime("%Y-%m-%d")
PR = Path(".")
status_dir = PR / "docs/team/status"
activity_p  = PR / f"docs/team/activity/{today}.jsonl"
audit_p     = PR / f"docs/team/audit/{today}.jsonl"

def jsonl(p):
    if not p.exists(): return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

agents = sorted([json.loads(p.read_text()) for p in status_dir.glob("*.json")],
                key=lambda r: r["agent"])
audit  = jsonl(audit_p)
activity = jsonl(activity_p)

blocks = [r for r in audit if r.get("decision") in ("BLOCK","REJECT")]
warns  = [r for r in audit if r.get("decision") == "WARN"]
passes = [r for r in audit if r.get("decision") == "PASS"]

out = []
out.append(f"# TradePilot Standup — {today}\n")
out.append(f"_Generated {datetime.now(ist).isoformat(timespec='seconds')}_\n")
out.append("\n## Agent Status\n")
out.append("| Agent | Status | Last action |")
out.append("|---|---|---|")
for a in agents:
    out.append(f"| {a['agent']} | {a.get('status','?')} | {a.get('last_action','—')} |")

out.append(f"\n## Audit Today\n")
out.append(f"- **{len(passes)} passes** · **{len(warns)} warns** · **{len(blocks)} blocks**")
if blocks:
    out.append("\n### Blocks\n")
    for b in blocks:
        out.append(f"- `{b['rule_family'] or '?'}` · {b['action']} · {b['subject']} — {b['reason']}")

out.append(f"\n## Activity (last 10)\n")
for r in activity[-10:][::-1]:
    out.append(f"- `{r['ts']}` **{r['agent']}** · {r['summary']}")

out_path = PR / f"docs/team/standup/{today}.md"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Standup written: {out_path}")
PYEOF
