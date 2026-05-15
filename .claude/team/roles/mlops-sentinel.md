# MLOps Sentinel — Model Promotion Authority

**Tier 2 (Operations). Veto power: YES on model promotion.**

## Mission
The May-13 incident never happens again. Every retrain is gated. Every promotion is logged. Every model in production has a verification report attached.

## Cadence
- **Every retrain attempt** — runs SARATHI-ML rules (all 8)
- **Daily post-close** — verifies live model still matches expected hashes; checks no silent file changes
- **Champion-challenger continuous** — if a challenger model exists, runs daily A/B comparison

## Rule Family Owned
- `SARATHI-ML` — 8 rules → `docs/sarathi/rules/SARATHI-ML.md`

## Inputs
- Candidate model files in `prototype/v4/models/` or `prototype/v5/models/`
- Training metrics JSON
- Walk-forward / CPCV report
- Champion model file + meta

## Outputs
- `verification_report.json` next to each model file
- Per-model report at `docs/sarathi/reports/models/<model-sha>.json`
- Audit log entry for every gate decision
- Champion-challenger comparison dashboard panel

## Veto Authority
**BLOCK** any model promotion that fails any SARATHI-ML rule. The engine then refuses to load that model — startup crashes with clear error.

CEO override is possible but requires explicit override entry in `verification_report.json`:
```json
"override": {"by":"soumya","ts":"...","reason":"...","expires":"YYYY-MM-DD"}
```

## KPI
- 0 worse-IC models reaching live
- 100% of deployed models have valid `verification_report.json`
- Champion-challenger comparison always available

## Implementation
**Rule-based**, deterministic. No LLM. CLI:
```bash
python3 scripts/team/gates/mlops-ic-gate.py \
    --candidate prototype/v4/models/lgbm_intraday.txt \
    --champion prototype/v4/models/archive/champion/lgbm_intraday.txt
```

Returns exit code 0 (PASS) or 1 (BLOCK). Stdout = human-readable report; stderr = blocking reasons.

Integrated into:
- `prototype/v4/ml_engine.py` retrain function (refuses to save bad model)
- Engine startup (refuses to load bad model)
- `dp model promote` CLI (refuses to promote bad model)
