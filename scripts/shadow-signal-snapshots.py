#!/usr/bin/env python3
"""
shadow-signal-snapshots — sidecar for the regime-shadow experiment (2026-09-08).
Every 60s, if an engine's daily state file changed, copy its `last_signals`, `regime`,
`risk_state` and open positions to docs/research/shadows/<engine>/<date>/<HHMMSS>.json.
Read-only: never touches the engine or its files. EOD tooling re-runs the regime-dependent
gates on each snapshot under the alternate regime and prices the difference from candles.
"""
import json, os, sys, time
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ENGINES = sys.argv[1].split(",") if len(sys.argv) > 1 else ["v5", "v5_wide"]
DATE = datetime.now().strftime("%Y-%m-%d")
seen = {}
while datetime.now().strftime("%H:%M") < "15:40":
    for e in ENGINES:
        f = ROOT / "docs/paper-trades" / e / f"{DATE}.json"
        try:
            m = os.path.getmtime(f)
        except OSError:
            continue
        if seen.get(e) == m: continue
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        out = ROOT / "docs/research/shadows" / e / DATE; out.mkdir(parents=True, exist_ok=True)
        snap = {"at": datetime.now().strftime("%H:%M:%S"), "state_mtime": datetime.fromtimestamp(m).strftime("%H:%M:%S"),
                "regime": d.get("regime"), "risk_state": d.get("risk_state"), "last_rescore_time": d.get("last_rescore_time"),
                "last_signals": d.get("last_signals", []),
                "positions": {p: [{k: x.get(k) for k in ("symbol", "position_type", "entry_price", "qty", "entry_time", "sl_price", "target_price", "score")} for x in v.get("positions", [])] for p, v in d.get("pools", {}).items()},
                "closed_n": sum(len(v.get("closed", [])) for v in d.get("pools", {}).values())}
        (out / f"{snap['at'].replace(':', '')}.json").write_text(json.dumps(snap, default=str))
        seen[e] = m
        print(f"[{snap['at']}] {e}: snapshot ({len(snap['last_signals'])} signals, regime {snap['regime']})", flush=True)
    time.sleep(60)
print("done for the day", flush=True)
