#!/usr/bin/env python3
"""End-to-end smoke test of the 2026-05-01 baseline protection layer.

Tests:
  1. risk_manager imports clean
  2. blacklist.json auto-loads VEDL
  3. corp_actions.json auto-loads VEDL ex-date ban
  4. check_can_trade refuses VEDL
  5. set_session_pnl trips kill-switch at threshold
  6. After kill-switch trip, check_can_trade refuses ALL symbols
  7. check_position_size refuses oversized trade
  8. All 11 paper-trade scripts compile (no syntax errors)
"""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype"))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def t(label: str, ok: bool, detail: str = ""):
    tag = PASS if ok else FAIL
    print(f"  [{tag}] {label}" + (f"  ({detail})" if detail else ""))
    return ok


results = []

print("\n=== Baseline Protection Smoke Test ===\n")

# 1. Import
try:
    from prototype.v5 import risk_manager as rm_mod
    from prototype.v5.risk_manager import (
        RiskManager,
        BASELINE_DAILY_LOSS_KILL_RS,
        BASELINE_MAX_POSITION_PCT,
        BLACKLIST_PATH,
        CORP_ACTIONS_PATH,
    )
    results.append(t("risk_manager imports", True,
                     f"kill={BASELINE_DAILY_LOSS_KILL_RS}, size={BASELINE_MAX_POSITION_PCT}"))
except Exception as e:
    results.append(t("risk_manager imports", False, str(e)))
    sys.exit(1)

# 2. Files exist
results.append(t("blacklist.json exists", BLACKLIST_PATH.exists(), str(BLACKLIST_PATH)))
results.append(t("corp_actions.json exists", CORP_ACTIONS_PATH.exists(), str(CORP_ACTIONS_PATH)))

# 3. Instantiate RiskManager (uses mock pool manager since pool_manager.py needs full setup)
from prototype.v5.risk_manager import PoolManager
pm = PoolManager(total_capital=5_000_000)
risk = RiskManager(pm, regime="SIDEWAYS", vix=15.0)

# 4. Blacklist auto-loaded VEDL
vedl_ban = risk.stock_bans.get("VEDL")
results.append(t("VEDL banned via blacklist or corp_actions", vedl_ban is not None,
                 f"source={vedl_ban.get('source') if vedl_ban else 'NONE'}, "
                 f"until={vedl_ban.get('until') if vedl_ban else 'N/A'}"))

# 5. check_can_trade refuses VEDL
ok, reason = risk.check_can_trade("SWING", "VEDL", "LONG")
results.append(t("check_can_trade refuses VEDL", not ok, reason[:80]))

# 6. check_can_trade allows a normal stock
ok, reason = risk.check_can_trade("SWING", "RELIANCE", "LONG")
results.append(t("check_can_trade allows RELIANCE", ok, reason))

# 7. Kill-switch — trip it
tripped_at_minus_4k = risk.set_session_pnl(-4000)
results.append(t("kill-switch holds at -Rs 4K (above floor)", not tripped_at_minus_4k,
                 f"tripped={risk.kill_switch_tripped}"))

tripped_at_minus_6k = risk.set_session_pnl(-6000)
results.append(t("kill-switch trips at -Rs 6K (below floor)", tripped_at_minus_6k,
                 f"tripped={risk.kill_switch_tripped}"))

# 8. After trip, ALL entries blocked
ok, reason = risk.check_can_trade("SWING", "RELIANCE", "LONG")
results.append(t("after kill-switch trip, RELIANCE blocked", not ok, reason[:80]))

# 9. Sticky kill-switch — even if P&L recovers
risk.set_session_pnl(2000)
ok, reason = risk.check_can_trade("SWING", "RELIANCE", "LONG")
results.append(t("kill-switch sticky after recovery", not ok, reason[:80]))

# 10. Position-size cap — fresh RM
risk2 = RiskManager(PoolManager(5_000_000), regime="SIDEWAYS", vix=15.0)
# SWING pool capital = 5M * 0.2 = 1M; 10% cap = 100K
ok, reason = risk2.check_position_size(50_000, "SWING")
results.append(t("position size Rs 50K under cap", ok, reason))

ok, reason = risk2.check_position_size(150_000, "SWING")
results.append(t("position size Rs 150K refused (over 10% of Rs 1M)", not ok, reason[:80]))

# 11. AUTO-POLL kill-switch — no explicit set_session_pnl call needed
risk3 = RiskManager(PoolManager(5_000_000), regime="SIDEWAYS", vix=15.0)
ok, _ = risk3.check_can_trade("SWING", "RELIANCE", "LONG")
results.append(t("auto-poll: fresh RM allows trade", ok))

# Inject a big loss into one pool to simulate aggregate hitting kill threshold
risk3.pm.pools["SWING"].daily_pnl = -8000
ok, reason = risk3.check_can_trade("SWING", "RELIANCE", "LONG")
results.append(t("auto-poll: kill-switch trips on pool aggregate", not ok, reason[:80]))
results.append(t("auto-poll: kill_switch_tripped flag set", risk3.kill_switch_tripped))

# 12. Compile-check all paper-trade scripts
print("\n  Compile-checking paper-trade scripts:")
script_paths = sorted((ROOT / "scripts").glob("v*-paper-trade.py"))
script_paths += [ROOT / "scripts" / "fetch_corp_actions.py"]
all_compile = True
for sp in script_paths:
    proc = subprocess.run(["python3", "-m", "py_compile", str(sp)],
                          capture_output=True, text=True)
    ok = proc.returncode == 0
    all_compile = all_compile and ok
    results.append(t(f"{sp.name}", ok, proc.stderr.strip()[:120] if not ok else ""))

# Summary
passed = sum(1 for r in results if r)
total = len(results)
print(f"\n=== {passed}/{total} checks passed ===\n")
sys.exit(0 if passed == total else 1)
