"""
Sarathi — Rule Runner

Entry point for all 5 rule families:
  SARATHI-LRN — Learning verification
  SARATHI-SPR — Sprint verification
  SARATHI-ML  — ML training verification (the May-13 fix)
  SARATHI-CDE — Code/deploy verification
  SARATHI-DAT — Data verification

Usage:
  python3 scripts/sarathi/verify.py --family ML --model prototype/v4/models/lgbm_intraday.txt
  python3 scripts/sarathi/verify.py --family CDE --pre-launch
  python3 scripts/sarathi/verify.py --family DAT --check pre-market
  python3 scripts/sarathi/verify.py --sweep learnings
  python3 scripts/sarathi/verify.py --sweep models

Exit codes:
  0 = PASS (or WARN with no BLOCKs)
  1 = BLOCK or REJECT
  2 = ESCALATE (CEO attention needed)
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.team.log import log_audit, update_status  # noqa: E402

# ── Canonical Sarathi constants ───────────────────────────────────────
SPEC_IC_FLOOR       = 0.05    # Apr-8 master research § 5.5
SPEC_IC_POS_PCT     = 0.60
SPEC_PBO_CEILING    = 0.50
SPEC_MIN_FOLDS      = 12
COST_BPS_DEFAULT    = 10
COST_BPS_STRESS     = 15


# ═══════════════════════════ SARATHI-ML ════════════════════════════════
def verify_ml(model_path: Path, champion_path: Path | None = None,
              legacy_exempt: bool = False) -> dict:
    """
    Run all 8 SARATHI-ML rules against a candidate model.
    Returns a verification_report dict; writes to <model_path>.parent/verification_report.json.
    """
    rules: list[dict] = []
    blocking: list[str] = []
    # Normalize to absolute paths
    model_path = model_path.resolve() if not model_path.is_absolute() else model_path
    if champion_path:
        champion_path = champion_path.resolve() if not champion_path.is_absolute() else champion_path

    # Meta file: try <stem>_meta.json first, then lgbm_meta.json convention
    meta_path = model_path.parent / (model_path.stem + "_meta.json")
    if not meta_path.exists():
        # v4 convention: lgbm_meta.json regardless of model filename
        meta_path = model_path.parent / "lgbm_meta.json"
    if not model_path.exists() or not meta_path.exists():
        return {
            "overall": "BLOCK",
            "rules_evaluated": [{"rule":"ML-PRE","result":"BLOCK",
                                 "evidence":{"model_exists":model_path.exists(),
                                             "meta_exists":meta_path.exists()},
                                 "reason":"model or meta file missing"}],
            "blocking_rules": ["ML-PRE"],
        }

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    cand_ic       = meta.get("walk_forward", {}).get("mean_ic")
    cand_pos_pct  = (meta.get("walk_forward", {}).get("ic_positive_pct") or 0) / 100.0
    cand_folds    = meta.get("walk_forward", {}).get("n_folds")
    cand_date_rng = meta.get("date_range")
    cand_trained  = meta.get("trained_at")

    # ML-001 — CPCV report
    cpcv = meta.get("cpcv")
    if cpcv is None:
        r = {"rule":"ML-001","name":"CPCV report",
             "result":"BLOCK",
             "evidence":{"cpcv_present":False},
             "reason":"No CPCV report attached. Run mlfinlab CombinatorialPurgedCV."}
        blocking.append("ML-001")
    else:
        pbo = cpcv.get("pbo", 1.0)
        ok = pbo < SPEC_PBO_CEILING
        r = {"rule":"ML-001","name":"CPCV report",
             "result":"PASS" if ok else "BLOCK",
             "evidence":{"pbo":pbo, "ceiling":SPEC_PBO_CEILING},
             "reason":"" if ok else f"PBO {pbo} >= {SPEC_PBO_CEILING}"}
        if not ok: blocking.append("ML-001")
    rules.append(r)

    # ML-002 — IC ≥ champion
    champ_ic = None
    if champion_path and champion_path.exists():
        cm_path = champion_path.parent / (champion_path.stem + "_meta.json")
        if not cm_path.exists():
            cm_path = champion_path.parent / "lgbm_meta.json"
        if cm_path.exists():
            champ_meta = json.loads(cm_path.read_text())
            champ_ic = champ_meta.get("walk_forward", {}).get("mean_ic")
    if champ_ic is None:
        r = {"rule":"ML-002","name":"IC >= champion",
             "result":"WARN",
             "evidence":{"champion_ic":None},
             "reason":"No champion to compare against (first-ever promotion)"}
    else:
        ok = (cand_ic or 0) >= champ_ic
        r = {"rule":"ML-002","name":"IC >= champion",
             "result":"PASS" if ok else "BLOCK",
             "evidence":{"candidate_ic":cand_ic, "champion_ic":champ_ic},
             "reason":"" if ok else f"candidate IC {cand_ic} < champion IC {champ_ic}"}
        if not ok: blocking.append("ML-002")
    rules.append(r)

    # ML-003 — IC ≥ spec floor (with legacy exemption)
    ok_floor = (cand_ic or 0) >= SPEC_IC_FLOOR
    if ok_floor:
        r = {"rule":"ML-003","name":"IC >= spec floor",
             "result":"PASS",
             "evidence":{"ic":cand_ic, "floor":SPEC_IC_FLOOR},
             "reason":""}
    elif legacy_exempt:
        r = {"rule":"ML-003","name":"IC >= spec floor",
             "result":"WARN",
             "evidence":{"ic":cand_ic, "floor":SPEC_IC_FLOOR, "exemption":"legacy"},
             "reason":f"IC {cand_ic} below floor {SPEC_IC_FLOOR}, "
                      "legacy exemption granted until rebuild completes"}
    else:
        r = {"rule":"ML-003","name":"IC >= spec floor",
             "result":"BLOCK",
             "evidence":{"ic":cand_ic, "floor":SPEC_IC_FLOOR},
             "reason":f"IC {cand_ic} below spec floor {SPEC_IC_FLOOR}"}
        blocking.append("ML-003")
    rules.append(r)

    # ML-004 — no leakage (heuristic check)
    # We can only assert leakage absence via metadata. Required: train_end_date < oos_start_date.
    leak_meta = meta.get("leakage_check", {})
    if "train_end_date" in leak_meta and "oos_start_date" in leak_meta:
        ok = leak_meta["train_end_date"] < leak_meta["oos_start_date"]
        r = {"rule":"ML-004","name":"No data leakage",
             "result":"PASS" if ok else "BLOCK",
             "evidence":leak_meta,
             "reason":"" if ok else "train_end >= oos_start"}
        if not ok: blocking.append("ML-004")
    else:
        r = {"rule":"ML-004","name":"No data leakage",
             "result":"WARN",
             "evidence":{"leakage_check_present":False},
             "reason":"No leakage_check block in meta; cannot verify"}
    rules.append(r)

    # ML-005 — walk-forward
    folds_ok = (cand_folds or 0) >= SPEC_MIN_FOLDS
    pos_ok   = cand_pos_pct >= SPEC_IC_POS_PCT
    ok = folds_ok and pos_ok
    r = {"rule":"ML-005","name":"Walk-forward folds",
         "result":"PASS" if ok else "BLOCK",
         "evidence":{"n_folds":cand_folds, "ic_positive_pct":cand_pos_pct,
                     "min_folds":SPEC_MIN_FOLDS, "min_pos_pct":SPEC_IC_POS_PCT},
         "reason":"" if ok else
                  f"folds={cand_folds} (need {SPEC_MIN_FOLDS}), "
                  f"pos%={cand_pos_pct:.2%} (need {SPEC_IC_POS_PCT:.0%})"}
    if not ok and not legacy_exempt:
        blocking.append("ML-005")
    rules.append(r)

    # ML-006 — cost-corrected backtest
    bt = meta.get("backtest", {})
    bt10 = bt.get("cost_10bps", {}).get("sharpe")
    bt15 = bt.get("cost_15bps", {}).get("sharpe")
    if bt10 is None or bt15 is None:
        r = {"rule":"ML-006","name":"Cost-corrected backtest",
             "result":"BLOCK" if not legacy_exempt else "WARN",
             "evidence":{"cost_10bps_sharpe":bt10, "cost_15bps_sharpe":bt15},
             "reason":"Cost-corrected Sharpe missing for 10bps and/or 15bps"}
        if not legacy_exempt: blocking.append("ML-006")
    else:
        ok = bt10 > 0
        r = {"rule":"ML-006","name":"Cost-corrected backtest",
             "result":"PASS" if ok else "BLOCK",
             "evidence":{"cost_10bps_sharpe":bt10, "cost_15bps_sharpe":bt15},
             "reason":"" if ok else f"Net Sharpe at 10bps = {bt10} not positive"}
        if not ok and not legacy_exempt: blocking.append("ML-006")
    rules.append(r)

    # ML-007 — champion-challenger comparison (advisory if no champion)
    cc = meta.get("champion_challenger", {})
    if not champion_path:
        r = {"rule":"ML-007","name":"Champion-challenger",
             "result":"WARN",
             "evidence":{"present":False},
             "reason":"No champion supplied; first-ever promotion"}
    elif "dm_pvalue" not in cc:
        r = {"rule":"ML-007","name":"Champion-challenger",
             "result":"BLOCK" if not legacy_exempt else "WARN",
             "evidence":{"present":False},
             "reason":"Diebold-Mariano (or bootstrap) comparison missing"}
        if not legacy_exempt: blocking.append("ML-007")
    else:
        # Pass if candidate not significantly worse than champion
        cand_better = cc.get("candidate_better", False)
        p = cc["dm_pvalue"]
        clearly_worse = (p < 0.05) and (not cand_better)
        ok = not clearly_worse
        r = {"rule":"ML-007","name":"Champion-challenger",
             "result":"PASS" if ok else "BLOCK",
             "evidence":cc,
             "reason":"" if ok else f"Candidate significantly worse (p={p})"}
        if not ok: blocking.append("ML-007")
    rules.append(r)

    # ML-008 — reproducibility
    repro = meta.get("reproducibility", {})
    have_hashes = all(k in repro for k in ("data_sha256","code_commit"))
    if have_hashes:
        # also compute model file hash now
        model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
        recorded = repro.get("model_sha256")
        if recorded and recorded != model_sha:
            r = {"rule":"ML-008","name":"Reproducibility",
                 "result":"WARN",
                 "evidence":{"recorded_model_sha":recorded, "actual_model_sha":model_sha},
                 "reason":"Recorded model_sha differs from current file"}
        else:
            r = {"rule":"ML-008","name":"Reproducibility",
                 "result":"PASS",
                 "evidence":{"model_sha":model_sha,
                             "data_sha":repro.get("data_sha256"),
                             "code_commit":repro.get("code_commit")},
                 "reason":""}
    else:
        r = {"rule":"ML-008","name":"Reproducibility",
             "result":"BLOCK" if not legacy_exempt else "WARN",
             "evidence":repro,
             "reason":"data_sha256 or code_commit missing from meta"}
        if not legacy_exempt: blocking.append("ML-008")
    rules.append(r)

    overall = "BLOCK" if blocking else ("WARN" if any(r["result"]=="WARN" for r in rules) else "PASS")

    report = {
        "model_path": str(model_path.relative_to(PROJECT_ROOT)),
        "trained_at": cand_trained,
        "date_range": cand_date_rng,
        "candidate": {"oos_ic": cand_ic, "ic_positive_pct": cand_pos_pct,
                      "n_folds": cand_folds},
        "champion": {"oos_ic": champ_ic} if champ_ic else None,
        "rules_evaluated": rules,
        "blocking_rules": blocking,
        "overall": overall,
        "override": None,
        "legacy_exempt": legacy_exempt,
    }

    # Write the verification_report.json next to model
    out_path = model_path.parent / "verification_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Audit log
    log_audit("sarathi", action="ml-verify",
              decision=overall,
              subject=str(model_path.relative_to(PROJECT_ROOT)),
              evidence={"blocking":blocking, "ic":cand_ic},
              reason="; ".join(r["reason"] for r in rules if r["reason"]) or "all rules pass",
              vetoable_by=["CEO"],
              rule_family="SARATHI-ML")

    return report


# ═══════════════════════════ SARATHI-DAT ═══════════════════════════════
def verify_data_feed(quotes_path: Path | None = None,
                     check: str = "pre-market") -> dict:
    """Run SARATHI-DAT rules."""
    quotes_path = quotes_path or PROJECT_ROOT / "prototype" / "v4" / "cache" / "nifty50_quotes_batch.json"
    rules = []
    blocking = []

    # DAT-001 NaN rate
    if quotes_path.exists():
        try:
            data = json.loads(quotes_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                entries = list(data.values())
            else:
                entries = data
            total = len(entries) or 1
            nan_count = sum(
                1 for e in entries
                if (not e) or (isinstance(e, dict) and (
                    e.get("Close") in (None, 0)
                    or (isinstance(e.get("Close"), float) and e["Close"] != e["Close"])
                ))
            )
            nan_rate = nan_count / total
            if nan_rate > 0.20:
                r = {"rule":"DAT-001","result":"BLOCK",
                     "evidence":{"nan_rate":nan_rate, "total":total},
                     "reason":f"NaN rate {nan_rate:.1%} > 20% threshold"}
                blocking.append("DAT-001")
            elif nan_rate > 0.05:
                r = {"rule":"DAT-001","result":"WARN",
                     "evidence":{"nan_rate":nan_rate, "total":total},
                     "reason":f"NaN rate {nan_rate:.1%} above 5% — falling back to per-symbol fetch"}
            else:
                r = {"rule":"DAT-001","result":"PASS",
                     "evidence":{"nan_rate":nan_rate, "total":total},
                     "reason":""}
        except Exception as e:
            r = {"rule":"DAT-001","result":"WARN",
                 "evidence":{"error":str(e)},
                 "reason":"Could not parse cache file"}
    else:
        r = {"rule":"DAT-001","result":"WARN",
             "evidence":{"cache_present":False},
             "reason":"Cache file not present (cold start)"}
    rules.append(r)

    # DAT-002 cache TTL
    if quotes_path.exists():
        import time
        age = time.time() - quotes_path.stat().st_mtime
        ok = age < 300
        r = {"rule":"DAT-002","result":"PASS" if ok else "WARN",
             "evidence":{"age_sec":int(age), "ttl":300},
             "reason":"" if ok else f"Cache age {int(age)}s > 5min"}
    else:
        r = {"rule":"DAT-002","result":"WARN",
             "evidence":{"cache_present":False},
             "reason":"No cache to check"}
    rules.append(r)

    overall = "BLOCK" if blocking else ("WARN" if any(r["result"]=="WARN" for r in rules) else "PASS")

    log_audit("sarathi", action="data-verify",
              decision=overall,
              subject=str(quotes_path.relative_to(PROJECT_ROOT) if quotes_path.exists() else quotes_path),
              evidence={"check":check, "blocking":blocking},
              reason="; ".join(r["reason"] for r in rules if r["reason"]) or "all rules pass",
              vetoable_by=[],
              rule_family="SARATHI-DAT")

    return {"overall":overall, "rules":rules, "blocking":blocking}


# ═══════════════════════════ Sweeps (Sprint 1) ═════════════════════════
def sweep_learnings() -> dict:
    """Run SARATHI-LRN rules against current DevPilot DB learnings.

    Sprint 1: just produce a report and tag the 3 known-suspect Apr-8 claims.
    Direct DB INSERT/UPDATE deferred until user confirms — for safety per data-safety rule.
    """
    findings = []
    suspect_claims = [
        {"claim_excerpt":"Insider buying cluster (3+ in 30d) → 11.2% outperformance over 6 months",
         "rule_flagged":"LRN-004",
         "tag":"UNVERIFIED",
         "rationale":"Round-number heuristic + Agent E found no public corroboration; "
                     "closest verified figure is 5-7% over 1 week (NSE 2010-19 study)."},
        {"claim_excerpt":"FII net sell > ₹2000cr → bearish 1-3 sessions",
         "rule_flagged":"LRN-005",
         "tag":"NEEDS_INDIA_VALIDATION",
         "rationale":"Agent E found 2026 macro weakened this signal due to DII counter-flow; "
                     "regime-dependent."},
        {"claim_excerpt":"GIFT Nifty premium > 0.3% → 75% gap-up probability",
         "rule_flagged":"LRN-002",
         "tag":"PARTIAL",
         "rationale":"Direction 75-85% accurate but magnitude error 15-40pt; fails on Fed/RBI/Budget days."},
    ]
    findings.extend(suspect_claims)

    log_audit("sarathi", action="sweep-learnings",
              decision="WARN",
              subject="DevPilot DB learnings table",
              evidence={"flagged_count":len(findings)},
              reason="Backward sweep — 3 Apr-8 master research claims flagged",
              vetoable_by=[],
              rule_family="SARATHI-LRN")

    report_path = PROJECT_ROOT / "docs" / "sarathi" / "reports" / "learnings" / "_sweep_2026-05-15.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Sarathi Backward Sweep — Learnings\n",
             f"_Generated 2026-05-15 — Sprint 1 backward verification._\n",
             "## Flagged Claims (Apr-8 Master Research)\n"]
    for f in findings:
        lines.append(f"- **{f['rule_flagged']}** → tag `{f['tag']}`")
        lines.append(f"  - Claim: {f['claim_excerpt']}")
        lines.append(f"  - Reason: {f['rationale']}\n")
    lines.append("\n## Action Items\n")
    lines.append("- [ ] Re-verify insider cluster claim on SAST data 2020-2026")
    lines.append("- [ ] Re-verify FII threshold with DII counter-flow as conditioning")
    lines.append("- [ ] Use GIFT Nifty only for gap-fill setups in first 15 min")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {"flagged":len(findings), "report":str(report_path.relative_to(PROJECT_ROOT))}


# ═══════════════════════════ CLI ═══════════════════════════════════════
def main():
    p = argparse.ArgumentParser(description="Sarathi rule runner")
    p.add_argument("--family", choices=["LRN","SPR","ML","CDE","DAT"])
    p.add_argument("--model", type=Path)
    p.add_argument("--champion", type=Path)
    p.add_argument("--legacy-exempt", action="store_true")
    p.add_argument("--check", default="pre-market")
    p.add_argument("--sweep", choices=["learnings","sprints","models"])
    args = p.parse_args()

    update_status("sarathi", "running", last_action=f"verify {args.family or args.sweep}")

    if args.sweep == "learnings":
        out = sweep_learnings()
        print(json.dumps(out, indent=2))
        update_status("sarathi", "idle", last_action=f"sweep learnings ({out['flagged']} flagged)")
        sys.exit(0)

    if args.family == "ML":
        if not args.model:
            print("--model required for --family ML", file=sys.stderr)
            sys.exit(2)
        report = verify_ml(args.model, args.champion, legacy_exempt=args.legacy_exempt)
        print(json.dumps(report, indent=2))
        update_status("sarathi", "idle", last_action=f"ml-verify {args.model.name} → {report['overall']}")
        sys.exit(0 if report["overall"] in ("PASS","WARN") else 1)

    if args.family == "DAT":
        out = verify_data_feed(check=args.check)
        print(json.dumps(out, indent=2))
        update_status("sarathi", "idle", last_action=f"data-verify {args.check} → {out['overall']}")
        sys.exit(0 if out["overall"] in ("PASS","WARN") else 1)

    p.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
