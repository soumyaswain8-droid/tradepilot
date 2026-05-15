"""
MLOps IC Gate — engine-side wrapper for SARATHI-ML.

The May-13 prevention. Every engine calls this at startup; refuses to load
a model that the gate BLOCKs (unless verification_report.json has a valid
non-expired CEO override).

Usage as a library (in engine startup):

    from scripts.team.gates.mlops_ic_gate import ensure_model_allowed
    ensure_model_allowed("prototype/v4/models/lgbm_intraday.txt")
    # raises ModelBlockedError if blocked

Usage as CLI:

    python3 scripts/team/gates/mlops-ic-gate.py prototype/v4/models/lgbm_intraday.txt
    # exit 0 = allowed, 1 = blocked
"""
from __future__ import annotations
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.team.log import log_audit  # noqa: E402


class ModelBlockedError(RuntimeError):
    pass


def ensure_model_allowed(model_path: str | Path,
                         *, raise_on_block: bool = True) -> dict:
    """
    Check verification_report.json next to model. Returns the report dict.
    Raises ModelBlockedError on BLOCK unless raise_on_block=False.
    """
    model_path = Path(model_path).resolve() if not Path(model_path).is_absolute() else Path(model_path)
    report_path = model_path.parent / "verification_report.json"

    if not report_path.exists():
        msg = (f"No verification_report.json next to {model_path.name}. "
               f"Run: python3 scripts/sarathi/verify.py --family ML --model {model_path}")
        log_audit("mlops-sentinel", action="ensure-allowed",
                  decision="BLOCK",
                  subject=str(model_path),
                  evidence={"report_present": False},
                  reason=msg, vetoable_by=["CEO"],
                  rule_family="SARATHI-ML")
        if raise_on_block:
            raise ModelBlockedError(msg)
        return {"overall": "BLOCK", "reason": msg}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    overall = report.get("overall", "BLOCK")
    override = report.get("override")

    # Check override validity
    override_ok = False
    if override:
        try:
            expires = override.get("expires")
            if expires:
                override_ok = date.fromisoformat(expires) >= date.today()
            else:
                override_ok = True  # no expiry = permanent override
        except Exception:
            override_ok = False

    if overall == "BLOCK" and not override_ok:
        msg = f"Model BLOCKED. Blocking rules: {report.get('blocking_rules', [])}"
        log_audit("mlops-sentinel", action="ensure-allowed",
                  decision="BLOCK",
                  subject=str(model_path),
                  evidence={"blocking": report.get("blocking_rules", []),
                            "override": override},
                  reason=msg, vetoable_by=["CEO"],
                  rule_family="SARATHI-ML")
        if raise_on_block:
            raise ModelBlockedError(msg)
        return report

    log_audit("mlops-sentinel", action="ensure-allowed",
              decision="PASS" if overall != "BLOCK" else "OVERRIDE",
              subject=str(model_path),
              evidence={"overall": overall, "override_ok": override_ok},
              reason=("CEO override active" if override_ok and overall == "BLOCK"
                      else "verification report PASS"),
              vetoable_by=[],
              rule_family="SARATHI-ML")
    return report


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    model_path = Path(sys.argv[1])
    try:
        report = ensure_model_allowed(model_path)
        print(f"[mlops-gate] {model_path.name}: ALLOWED ({report.get('overall')})")
        sys.exit(0)
    except ModelBlockedError as e:
        print(f"[mlops-gate] {model_path.name}: BLOCKED — {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
