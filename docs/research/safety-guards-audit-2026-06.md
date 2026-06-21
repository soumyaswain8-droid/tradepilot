# Safety-Guards Audit — Same-Predicate Conflict Sweep

::: {.report-meta}

| | |
|:--|:--|
| **Sprint task** | `S2-PM-003` (medium) |
| **Type** | Read-only code audit |
| **Trigger** | 2026-05-18 incident: model-freshness guard vs SARATHI-ML CEO override disagreed, silently killed engine v5 for 10 min |
| **Repo** | `/Users/soumyaswain/Documents/tinker/projects/tradepilot` |
| **Created** | 2026-06-01 |
| **Author** | Soumya Swain |

:::

## 1. What this audits

On 2026-05-18, two independently-built guards both answered the predicate **"is the model OK to trade?"** but disagreed:

- `prototype/utils/signal_guards.py:check_model_freshness()` used `max_age_days=3`. The restored model was 9 days old → it raised `SystemExit`.
- The SARATHI-ML CEO override in `verification_report.json` had **approved** the stale model.

The freshness guard *does* now read that override (lines 231-249), but the two were built separately and the threshold (`3`) is hardcoded in a different layer from the source-of-truth that grants the exemption. This audit sweeps for every other place where two guards check the same predicate without a shared source of truth.

## 2. Guard / Check Inventory

::: {.metrics-table}

| file:line | function | predicate asserted | threshold / logic | failure-action | respects-override? |
|:--|:--|:--|:--|:--|:--:|
| `prototype/utils/signal_guards.py:203` | `check_model_freshness()` | model is fresh | `age_days > max_age_days` (default **3**) | `SystemExit` (abort) + Telegram | **YES** — reads `verification_report.json.override`, checks `expires` |
| `prototype/utils/signal_guards.py:~70` | `safe_qty()` / `atomic_write_json()` | qty sane / write atomic | n/a (utility) | sanitise / raise | n/a |
| `scripts/sarathi/verify.py:45` | `verify_ml()` | model passes SARATHI-ML (ML-001..008) | IC≥champion, IC≥floor, no leakage, CPCV PBO, reproducibility | `overall=BLOCK` (sets `override:null`) | emits override slot, does not self-honor |
| `scripts/team/gates/mlops_ic_gate.py:35` | `ensure_model_allowed()` | model allowed to load | wraps `verify_ml`; `BLOCK` unless `override.expires >= today` | `ModelBlockedError` / `sys.exit(1)` | **YES** — canonical override check |
| `scripts/sarathi/verify.py:279` | `verify_data_feed()` | data feed is fresh/valid | DAT-001 staleness, DAT-002 | `BLOCK`/`WARN` | no |
| `prototype/v4/preflight.py:~120` | `is_late_start()` | boot before 09:30 IST | `now > 09:30` | gates late-mode | n/a |
| `prototype/v4/preflight.py:165` | late-mode entry filter | entry not overextended | `±1.5%` long/short, `±2.5%` extended | `return False, reason` (skip stock) | no |
| `prototype/v4/config/tiers.json:4` | (config) tier staleness | tier data fresh | `staleness_cutoff_days: 30` | consumed downstream | no |
| `prototype/v4/position_sizer.py:55` | `size_positions(max_per_stock_pct=0.15)` | per-stock size ≤ cap | **15%** of capital (was 20% pre-05-08) | cap + redistribute | no |
| `prototype/v4/position_sizer.py:114` | BUY-count gate | universe large enough | `len(stocks) < min_buy_count` → skip | `return []` (no deploy) | no |
| `prototype/v5/risk_manager.py:210` | `check_position_size()` | single trade ≤ cap | **`BASELINE_MAX_POSITION_PCT=0.10`** (10%) | `return (False, reason)` | no |
| `prototype/v5/risk_manager.py:228` | `check_can_trade()` | pre-trade gate (composite) | kill-switch, breakers, bans, slot caps, sector cap | `return (False, reason)` | no |
| `prototype/v5/risk_manager.py:287` | total-positions cap | open positions ≤ cap | **`MAX_POSITIONS_TOTAL=20`** | `return (False, reason)` | no |
| `prototype/v5/risk_manager.py:300` | same-sector cap | sector concentration ≤ cap | **`MAX_SAME_SECTOR=3`** | `return (False, reason)` | no |
| `prototype/v5/risk_manager.py:~194` | daily-loss kill-switch | session P&L above floor | **`BASELINE_DAILY_LOSS_KILL_RS=-5000`** | trips kill-switch, no new entries | no |
| `prototype/v5/risk_manager.py:315` | Kelly cap | size ≤ Kelly fraction | **`KELLY_CAP=0.25`** (25%) | `min(sized, kelly_max)` | no |
| `prototype/v5/risk_manager.py:355` | `check_all_breakers()` | drawdown within `POOL_LIMITS` | daily/weekly/monthly % of pool | fire pool breaker | no |
| `prototype/v5/pool_manager.py:118` | `check_circuit_breakers()` | pool not tripped | per-pool limits | pause pool | no |
| `prototype/v5/rust_bridge.py:191` | `check_rust_risk()` | Rust risk status | proxies to Rust `/api/risk` | `None` if offline | no |
| `engine/src/risk/mod.rs:139` | `check_order()` | order passes ALL hard gates | see below | `RiskResult::Err` (reject) | **no — "CANNOT be bypassed"** |
| `engine/src/risk/mod.rs:148` | daily-loss gate | session P&L above floor | **`RUST_MAX_DAILY_LOSS=-20000`** | `DailyLossLimitBreached` | no |
| `engine/src/risk/mod.rs:157` | order-size gate | order value ≤ cap | **`RUST_MAX_ORDER_VALUE=100000`** | `OrderTooLarge` | no |
| `engine/src/risk/mod.rs:165` | total-positions gate | open positions ≤ cap | **`RUST_MAX_TOTAL_POSITIONS=150`** | `MaxPositionsReached` | no |
| `engine/src/risk/mod.rs:174` | per-symbol positions gate | per-symbol ≤ cap | **`RUST_MAX_POSITIONS_PER_SYMBOL=10`** | `MaxPositionsForSymbol` | no |
| `engine/src/risk/mod.rs:184` | deployment gate | deployment ≤ cap | **`RUST_MAX_DEPLOYMENT_PCT=0.80`** (80%) | `MaxDeploymentExceeded` | no |

:::

## 3. Conflicts Found

Each pair below asserts the **same predicate** through **different thresholds** or **no shared source of truth**. The Rust risk module is explicitly documented as "Hard limits that CANNOT be bypassed" — yet Python enforces *tighter* limits the Rust layer never sees, so the two layers silently disagree on which order is legal.

### CONFLICT-1 — Model freshness vs SARATHI-ML override *(known / the trigger)*
- **Predicate:** "is the model OK to trade?"
- **Guard A:** `signal_guards.py:check_model_freshness()` — hardcoded `max_age_days=3`.
- **Guard B:** SARATHI-ML override in `verification_report.json`, enforced canonically by `mlops_ic_gate.py:ensure_model_allowed()`.
- **Conflict:** the `3`-day threshold lives in a different layer than the source-of-truth (`verification_report.json`) that grants exemptions. Guard A bolt-on reads the override, but neither references a shared constant nor the gate's verdict.
- **Severity:** HIGH (already caused a 10-min outage).
- **Fix:** freshness threshold + override verdict must come from one place — have `check_model_freshness` call `ensure_model_allowed()` (or read its cached verdict) rather than re-deriving "OK to trade" from a private constant.

### CONFLICT-2 — Single-position size cap (10% vs 15% vs 25% vs Rs 100k)
- **Predicate:** "is this single position size allowed?"
- **Guards:** `risk_manager.py:check_position_size()` **10%** · `position_sizer.py` `max_per_stock_pct` **15%** · `risk_manager.py:get_position_size()` Kelly **25%** · `engine/src/risk/mod.rs` `max_order_value` **Rs 100,000** absolute.
- **Conflict:** four independent ceilings for the same predicate, none referencing a shared constant. The sizer can build a 15% position that `check_position_size()` then rejects at 10%; Kelly allows 25% above both; Rust caps by absolute rupees, blind to all three percentages.
- **Severity:** HIGH (sizing/gate disagreement = silently dropped or rejected trades).
- **Fix:** one `MAX_POSITION_PCT` source of truth; sizer caps at it, gate asserts it, Rust derives its rupee cap from `pct * capital`.

### CONFLICT-3 — Total open-positions cap (20 in Python vs 150 in Rust)
- **Predicate:** "are we under the max open-positions limit?"
- **Guards:** `risk_manager.py:MAX_POSITIONS_TOTAL = 20` vs `engine/src/risk/mod.rs:max_total_positions = 150` (`RUST_MAX_TOTAL_POSITIONS`).
- **Conflict:** a **7.5×** gap. Python refuses the 21st position; Rust would happily accept up to 150. After a Python/Rust desync (`sync_positions_from_state` drift) the two layers disagree on whether the book is full.
- **Severity:** HIGH (Rust is the "hard, un-bypassable" layer but is the *looser* one — the safety floor is weaker than the soft layer above it).
- **Fix:** single shared `MAX_POSITIONS_TOTAL`; Rust default must equal the Python cap (or be passed in at startup), not an independent env default.

### CONFLICT-4 — Daily-loss kill-switch (Rs -5,000 Python vs Rs -20,000 Rust)
- **Predicate:** "has the daily loss floor been breached → stop trading?"
- **Guards:** `risk_manager.py:BASELINE_DAILY_LOSS_KILL_RS = -5000` vs `engine/src/risk/mod.rs:max_daily_loss = dec!(-20000)`.
- **Conflict:** **4×** gap. Python kills at -Rs 5k; Rust keeps trading until -Rs 20k. If Python is bypassed/offline, the "hard" Rust kill-switch lets losses run 4× deeper than intended.
- **Severity:** HIGH (direct capital-loss exposure).
- **Fix:** one `DAILY_LOSS_KILL_RS` constant injected into both; Rust env default must not silently diverge.

### CONFLICT-5 — Per-symbol / sector concentration (Python sector=3 vs Rust per-symbol=10)
- **Predicate:** "are we over-concentrated in one name/sector?"
- **Guards:** `risk_manager.py:MAX_SAME_SECTOR = 3` (sector-level) vs `engine/src/risk/mod.rs:max_positions_per_symbol = 10` (symbol-level).
- **Conflict:** related-but-misaligned predicates with no linkage — Python caps a *sector* at 3 stocks; Rust allows **10 of the same symbol**. Concentration is governed by two unrelated numbers.
- **Severity:** MEDIUM.
- **Fix:** define concentration policy once (sector + symbol) and share it across layers.

### CONFLICT-6 — Staleness windows scattered (3d / 30d / data-feed DAT)
- **Predicate:** "is this input stale?"
- **Guards:** model freshness **3d** (`signal_guards.py`) · tier staleness **30d** (`tiers.json`) · data-feed DAT-001 (`verify.py`) · late-start **09:30 IST** (`preflight.py`).
- **Conflict:** four different staleness regimes, four owners, no shared "freshness policy" registry. Acceptable that *values* differ (model vs tier vs feed), but there is no single place that enumerates them, so a future guard can pick yet another arbitrary number.
- **Severity:** LOW-MEDIUM (governance/drift risk, not an active bug).
- **Fix:** central `freshness_policy` table/constant mapping each input-class → max age + override source.

## 4. Proposed Rule — SARATHI-SPR (Same-Predicate Reconciliation)

> **Naming note:** `docs/sarathi/rules/SARATHI-SPR.md` is already taken by "Sprint Verification." The task asked for the new rule to be `SARATHI-SPR`. To avoid clobbering an applied rule, this audit proposes the rule under the working code **`SARATHI-SPR` (Same-Predicate Reconciliation)** but recommends filing it as a distinct family (e.g. `SARATHI-RCN`) so the existing Sprint rule is untouched. Final ID is the Architect's call. The rule body, in the style of the existing SARATHI-* families:

---

### SARATHI-SPR — Same-Predicate Reconciliation

**Triggered on:** any new guard/check/gate added; CI lint of `prototype/`, `scripts/`, `engine/`; pre-deploy.

**Veto power:** YES — can BLOCK a deploy if two guards assert the same predicate with unlinked thresholds.

#### SPR-R1 — One predicate, one source of truth
No two guards may assert the same predicate (model fresh, position size allowed, max positions, daily-loss floor, concentration, staleness) using **different hardcoded thresholds**. Each predicate has exactly one named constant / config key; every guard imports it.

- **Check:** static scan — for each predicate class, collect all literal thresholds across `prototype/`, `scripts/`, `engine/`. More than one distinct value for the same predicate → fail.
- **Fail action:** `BLOCK` — deploy refused until thresholds unified behind a shared constant.

#### SPR-R2 — Cross-layer parity (Python ↔ Rust)
Where a limit is enforced in both the Python orchestrator and the Rust engine, the Rust default MUST equal the Python value (or be injected at startup). The "hard" layer must never be *looser* than the soft layer above it.

- **Check:** assert `RUST_MAX_TOTAL_POSITIONS == MAX_POSITIONS_TOTAL`, `RUST_MAX_DAILY_LOSS == BASELINE_DAILY_LOSS_KILL_RS`, `RUST_MAX_ORDER_VALUE` derivable from `BASELINE_MAX_POSITION_PCT * capital`.
- **Fail action:** `BLOCK` — divergence between the soft and hard layer is a safety inversion.

#### SPR-R3 — Override linkage
A guard that can be bypassed (CEO override, legacy exemption) MUST read its verdict from the **canonical override authority** for that predicate — never re-derive "OK?" from a private constant.

- **Check:** `check_model_freshness` (and peers) call the SARATHI-ML gate verdict, not a local `max_age_days`.
- **Fail action:** `BLOCK` if a guard hardcodes a threshold for a predicate that has an override authority.

#### SPR-R4 — Freshness registry
All staleness windows live in one registry mapping `input_class → {max_age, override_source}`. Differing values are allowed; *scattered ownership* is not.

- **Check:** every `max_age` / `staleness_cutoff` / freshness literal resolves through the registry.
- **Fail action:** `WARN` (governance), upgraded to `BLOCK` if the new literal duplicates an existing predicate (then SPR-R1 applies).

#### Output Schema
Per-scan reconciliation report at `docs/sarathi/reports/guards/<date>.json`:
```json
{
  "scanned_at": "...",
  "predicates": [
    {"predicate":"max_positions_total","thresholds":[{"loc":"risk_manager.py:50","value":20},
     {"loc":"engine/src/risk/mod.rs:68","value":150}],"result":"BLOCK","rule":"SPR-R2"}
  ],
  "overall": "BLOCK"
}
```

---

## 5. Reproducibility
All findings derived by static grep/read only — no engine or script was executed. Threshold values cited inline with `file:line`. Re-run the sweep with the grep patterns: `_guard`, `def check_`, `def verify_`, `max_age`, `freshness`, `staleness`, `_ok`, `is_allowed`, `ensure_` across `prototype/`, `scripts/`, `engine/`.
