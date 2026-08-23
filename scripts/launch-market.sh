#!/bin/bash
# FULL BATTLE LAUNCH — everything needed for today's market.
# Use this as the single command after laptop restart or every morning.
# Triggered automatically Mon-Fri 08:50 IST via launchd (com.soumya.tradepilot-launch),
# 5 min after the 08:45 pmset wake. Launches the COMPLETE stack incl. profit + missed-opps
# validation watchdogs (TP-CLN-005). Redundant 09:10 market_go launcher disabled 2026-06-14
# to stop the double-launch/mid-session restart; launch-market self-gates via --smoke.
#
# Launches:
#   1. Rust engine (execution/risk layer)
#   2. Flask dashboard (localhost:5050) — also serves /team agent dashboard
#   3. daily-scores archiver (snapshots dashboard BUY/HOLD list — added 2026-04-23)
#   4. 3 paper-trade engines (v4, v5, v5_classic) — see Sprint 1 consolidation below
#   5. crash-watchdog (restart crashed engines)
#   6. telegram-digest (30-min P&L updates to Soumya)
#   7. laptop-heartbeat (15-min "alive" ping)
#   8. auto-stop-eod (kills everything at 15:35)
#   9. satish-schedule (4 trade-data updates/day — only if SATISH_TELEGRAM_CHAT_ID set)
#
# SPRINT 1 CONSOLIDATION (2026-05-15, CEO option 3B):
#   Active: v4 (control), v5 (primary rebuild target), v5_classic (frozen baseline)
#   Retired (commented in ENGINES array; state preserved, scripts unchanged):
#     v5_6  Darvas-box breakout
#     v5_7  Box mean-reversion
#     v5_8  v5 with regime slot-partition disabled
#     v6    v4 raw signals + Track A bolt-on
#   To re-enable: uncomment in ENGINES array. Re-introduction planned post-rebuild (~2026-07-15).
#
# Usage:
#   ./scripts/launch-market.sh              # full launch
#   ./scripts/launch-market.sh --stop       # kill everything
#   ./scripts/launch-market.sh --status     # show what's running
#
# EXIT CODES (S2-PM-006 — consumed by scripts/team/cadence/market_go.py).
# Any non-zero exit is treated as a SARATHI-CDE BLOCK by market_go.py: it pages
# Telegram and refuses to let the session pass silently. Distinct codes let the
# pager say *what* failed without scraping the log.
#
#   0   SUCCESS         Full happy-path launch (all critical components up).
#   2   SMOKE_FAILED    Pre-launch smoke test (sarathi-verify --smoke) failed —
#                       engines NOT started (hard gate, before anything deploys).
#   3   RUST_MISSING    Rust engine binary absent — the execution/risk layer never
#                       started. The rest of the stack is still launched (so the
#                       dashboard/engines come up), but we exit non-zero at the end
#                       so market_go.py pages: trades have no execution backstop.
#   4   ENGINE_MISSING  One or more paper-trade engine scripts were missing on disk;
#                       fewer engines launched than ENGINES defines. Stack continues,
#                       non-zero exit at the end so the shortfall is paged.
#
# Codes are reserved sequentially; --stop / --status always exit 0.

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

TODAY=$(date +%Y-%m-%d)
STAMP=$(date +%H%M%S)

# ──────────────────────── Exit codes (see header) ────────────────────────
# S2-PM-006: distinct, documented codes so market_go.py can page on the exact
# failure class. SMOKE_FAILED is a hard gate (exit immediately, no engines).
# RUST_MISSING / ENGINE_MISSING are *deferred* — the rest of the stack still
# launches (best-effort partial day), but EXIT_CODE is set and returned at the
# very end so a non-zero exit reaches market_go.py.
readonly EX_SMOKE_FAILED=2
readonly EX_RUST_MISSING=3
readonly EX_ENGINE_MISSING=4
EXIT_CODE=0   # promoted to a non-zero EX_* by deferred failures below

# ──────────────────────────── Sleep prevention ────────────────────────────
# Wednesday 2026-05-27 lost an entire trading session because the laptop slept
# at 08:45 right after engines warmed up. Until then, this script relied on a
# separately-managed caffeinate that wasn't guaranteed to exist. Now we own it:
# launch starts a dedicated caffeinate that survives until --stop (or auto-stop-eod).
CAFFEINATE_PID_FILE="/tmp/tradepilot-caffeinate.pid"

start_caffeinate() {
  if [ -f "$CAFFEINATE_PID_FILE" ] && kill -0 "$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null)" 2>/dev/null; then
    echo "  ✓ caffeinate already running (PID $(cat "$CAFFEINATE_PID_FILE"))"
    return 0
  fi
  # -d: prevent display sleep; -i: idle; -m: disk; -s: system; -u: user-active assertion
  nohup caffeinate -dimsu > /dev/null 2>&1 &
  local pid=$!
  echo "$pid" > "$CAFFEINATE_PID_FILE"
  echo "  ✓ caffeinate started (PID $pid) — laptop locked awake until --stop or 15:35 EOD"
}

stop_caffeinate() {
  if [ -f "$CAFFEINATE_PID_FILE" ]; then
    local pid
    pid=$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && echo "  ✓ caffeinate stopped (PID $pid)"
    fi
    rm -f "$CAFFEINATE_PID_FILE"
  fi
}

ENGINES=(
  # ── STANDBY, 2026-08-10 (Soumya) ─────────────────────────────────────────────
  # v4, v5_2..v5_8, v6, v7_regime are OFF and stay off. Verified inert: none of
  # them appears in this array or in crash-watchdog.sh's active list, so nothing
  # can start them on its own.
  #
  # BEFORE RE-ACTIVATING ANY OF THEM, add the session guard. They predate it and
  # would repeat v10's 2026-08-10 failure — 19 positions opened at 08:53, twenty
  # minutes before the open, at the previous session's closing prices, two of them
  # stopped out 75 seconds after the bell because their stops were set against
  # prices that no longer existed. Copy _session_open() from v10-paper-trade.py
  # and call it at the top of deploy_signals().
  # ─────────────────────────────────────────────────────────────────────────────
  # Active engines: 3 (post-foundation-review consolidation, 2026-06-11).
  # Rationale: run only validated, profit-making engines.
  #   v5         — VALIDATED: market-neutral alpha t=3.0 (NIFTY regression),
  #                survives honest fills (t=2.73) and realistic 23bps costs (t=2.52).
  #   v5_classic — real alpha t=2.39, market-neutral. Secondary.
  #   v7_regime  — regime-gate experiment (kept; see below).
  #
  # RETIRED 2026-06-11 (foundation review, TP-CLN-001) — state files preserved:
  #   v4 has NO significant alpha (regression alpha t=1.51 n.s.; beta-driven t=2.01).
  #   Its 2-month +273k was 72% from ONE over-leveraged day (2026-05-06: gate
  #   disabled, deployed Rs 6.8M); median day Rs 0; negative without top-3 days.
  #   Confirmed live: worst engine on 2 of its last 3 sessions (-13881, -5133, down days).
  #   To revive: uncomment here AND in crash-watchdog.sh together.
  # "v4|scripts/v4-paper-trade.py"
  # ── FLEET CONSOLIDATION, 2026-08-23 (Soumya) ────────────────────────────────
  # 15 engines retired in one decision: week 08-17..21 cycled Rs3.66 crore of
  # turnover for +Rs5,261 gross (+0.014% of flow) and Rs39k of modelled fees.
  # Five independent measurements: intraday OHLCV signal cannot clear the toll.
  # Survivors: v5_wide (only live net-positive track), v5_swing (own launchd),
  # real1k (manual pilot). Lessons harvested in 1cr-roadmap/ENGINE-GRAVEYARD.md.
  # Retired entries are commented, never deleted — data and code stay.
  "v5|scripts/v5-paper-trade.py"   # UN-RETIRED 2026-08-23 evening (Soumya: keep v5)
  # RETIRED 2026-08-23: "v5_classic|scripts/v5_classic-paper-trade.py"

  # RC-1 (TP-RCA, 2026-06-26): v5_long = v5 with shorts DISABLED (long-only), NIFTY-200.
  # Root-cause finding (11-agent investigation): the SHORT book is the entire net bleed —
  # longs +Rs1,149 vs shorts -Rs3,611 over 06-16..25; if shorts were flat v5 is net positive.
  # The April engine that made money was long-only. Same v5 code, SHORT_REQ_MAX_SCORE=-1 makes
  # shorts impossible. THE primary fix experiment. Compare net P&L + win-rate vs live v5.
  # RETIRED 2026-08-23: "v5_long|scripts/v5_long-paper-trade.py"

  # RETIRED 2026-06-26 (TP-RCA engine audit): v5_noml is REDUNDANT — config.py ships
  # ml_score=0 globally since 06-21, so v5_noml runs identical selection code to v5 (it was
  # literally running v5 twice). Experiment concluded (ML removed & committed). State preserved.
  # "v5_noml|scripts/v5_noml-paper-trade.py"

  # RETIRED 2026-06-26 (TP-RCA engine audit): v5_apr tracked v5 to within +Rs78 over 9
  # sessions — no information value. FLAT_EXIT-off question deferred to RC-6 (clean single-
  # variable test) if ever revisited. State preserved.
  # "v5_apr|scripts/v5_apr-paper-trade.py"

  # SHADOW (TP-QUANT, 2026-06-21): v5_cut = ML-removed + faster wrong-way cut + tighter
  # short-gate + ~450-name universe. Built from this week's watchdog findings to lift
  # the profit margin. Compare risk-adjusted vs v5. Re-comment to end.
  # RETIRED 2026-08-23: "v5_cut|scripts/v5_cut-paper-trade.py"

  # SHADOW (TP-RCA, 2026-06-30): v5_flip = fast intraday regime-flip. Re-checks the live
  # tape every 5 min and activates the existing BEAR 8/12 slot tilt on a CONFIRMED hard-down
  # (NIFTY < -0.6%), bidirectional (reverts on green), keeps both legs. Data-validated this
  # week (engine doesn't adapt its mix to the tape today). Compare red-day behaviour vs v5.
  # RETIRED 2026-08-23: "v5_flip|scripts/v5_flip-paper-trade.py"

  # SHADOW (spec 2026-07-17): v5_chop = TrendScore chop filter (trade less +
  # smaller in chop, full-size on confirmed trend). ML-free. Gate 2: 2 weeks
  # vs v5 -> promote on better net + lower cost drag + no worse DD.
  # RETIRED 2026-08-23: "v5_chop|scripts/v5_chop-paper-trade.py"

  # SHADOW (RRG Gate-1 PASS, 2026-07-20, commit d23726e): v5_rrg = same
  # 2-tier CHOP-throttle machinery as v5_chop, score producer swapped to
  # prototype/v5/rrg_regime.py's daily defensive-vs-cyclical rotation COUNT
  # sensor (form=count/extended/N=1/th=-0.2143, pc85/lc73 -- the sensor that
  # cleared 70/70 where TrendScore couldn't). Premarket tilt held constant
  # intraday ("tilt, not trigger"). Gate 2: 2 weeks vs v5, same criteria as
  # v5_chop -- promote on better net + lower cost drag + no worse DD; early-
  # kill if trailing v5 by >Rs5k after week 1. Re-comment to end.
  # RETIRED 2026-08-23: "v5_rrg|scripts/v5_rrg-paper-trade.py"

  # SHADOW (Gate-2, spec 2026-07-20_risk_gate_three_state_verdict.md, Phase
  # 1+2): v5_gate = same v5 code, RiskGate DRIVES execution (RISK_GATE_DRIVE=1)
  # instead of only logging verdicts (Phase 0 log-only shipped 2026-07-20,
  # commits df90250/5682b22). Adds INVALIDATION_MONITOR=1 (Phase 2): open
  # positions exit INVALIDATED on a triggered thesis falsifier, distinct from
  # STOP/TARGET/AGED. NO CHOP_FILTER — isolates the gate effect on its own for
  # clean four-way attribution (v5 / v5_chop / v5_rrg / v5_gate). Gate 2: 2
  # weeks vs live v5 — promote on fewer chop-day trades w/ equal-or-better
  # capture, gate never looser than inline, INVALIDATED exits beat the
  # eventual stop; early-kill if trailing v5 by >Rs5k after week 1.
  # Re-comment to end.
  # RETIRED 2026-08-23: "v5_gate|scripts/v5_gate-paper-trade.py"

  # MIGRATION CANARY (2026-08-04): v5_kite = v5 with NSE_DATA_SOURCE=kite. Exactly
  # ONE variable differs from live v5 — the data feed — so any divergence is
  # attributable to the feed and nothing else. yfinance silently dropped Monday
  # 2026-08-03 from ^NSEI/^BSESN (index-only; equities were fine), which made the
  # index read +0.00% on a -0.64% day. Measured before switching: 200/200 NIFTY
  # symbols at 0.000% price divergence, 0.40s vs 9.00s per batch. Promote to the
  # whole fleet only after trade count and P&L track v5 across a full week AND
  # kite_data.health() reports zero fallbacks — a session with fallbacks silently
  # ran on the control's feed and is not a clean comparison.
  # RETIRED 2026-08-23: "v5_kite|scripts/v5_kite-paper-trade.py"

  # SELECTIVITY SHADOW (2026-08-04): v5_pick = v5 + MIN_ENTRY_SCORE=70. Backtest over
  # v5's last 25 sessions: floor 70 -> 193 trades, net Rs 4,361 vs 414 trades, net Rs 256.
  # Gross is HIGHER with 53% fewer trades, so sub-70 entries lose before costs; costs
  # (Rs 14.30/trade) then eat 96% of gross. Direction-neutral — NOT a shorting change.
  # Expect turnover ~23%, below the 45-55% band: that tension is the point of the test.
  # PAUSED 2026-08-05 — tunes execution around a signal measured WORSE than
  # random entry (5/5 seeds, t 2.76-4.24). See 1cr-roadmap/plan/2026-08-05_signal-
  # rebuild-plan.md. State preserved; re-enable by uncommenting when there is a
  # signal worth tuning.
  # "v5_pick|scripts/v5_pick-paper-trade.py"

  # DEPLOYMENT SHADOW (2026-08-04): v5_deploy = v5 + POOL_ALLOC INTRADAY 60 / SWING 40.
  # POSITIONAL/INVESTMENT/RESERVE have received ZERO trades in all history (every signal
  # defaults to INTRADAY), so 45% of capital sat where no trade could reach it. Simulated:
  # 52.9% -> 96.1% deployed at the UNCHANGED sizer 0.15. Meets Soumya's 90% target without
  # touching position sizing. RISK: ~2x exposure on a red day — watch drawdown vs v5.
  # PAUSED 2026-08-05 — tunes execution around a signal measured WORSE than
  # random entry (5/5 seeds, t 2.76-4.24). See 1cr-roadmap/plan/2026-08-05_signal-
  # rebuild-plan.md. State preserved; re-enable by uncommenting when there is a
  # signal worth tuning.
  # "v5_deploy|scripts/v5_deploy-paper-trade.py"

  # TIME-GATE SHADOW (2026-08-04): v5_time = v5 + NO_ENTRY_HOURS=9. Over v5's last 30
  # sessions the 09:00 hour was the worst by a wide margin (121 trades, net -Rs 2,550,
  # -21/trade) while 13:00 was the only profitable one (+Rs 16/trade). Skipping 09h:
  # net -3,425 -> -875. EVIDENCE IS THIN: only 9 of 30 sessions traded that hour, 6 of 9
  # negative, and one -Rs 2,253 day carries much of it. Direction consistent, magnitude not
  # established. Pure subtractive gate — matches the SYNTHESIS rule that any candidate
  # which raises trade count is rejected outright.
  # PAUSED 2026-08-05 — tunes execution around a signal measured WORSE than
  # random entry (5/5 seeds, t 2.76-4.24). See 1cr-roadmap/plan/2026-08-05_signal-
  # rebuild-plan.md. State preserved; re-enable by uncommenting when there is a
  # signal worth tuning.
  # "v5_time|scripts/v5_time-paper-trade.py"

  # EXIT-STRUCTURE SHADOW (2026-08-04): v5_hold = MAX_HOLD_DAYS=3 + REVERSAL_EXIT_PCT=0.5.
  # v5 reaches TARGET on only 4.6% of trades; target wins (+9,484) and stop losses (-9,503)
  # cancel, so nearly all profit comes from TIME_EXIT — the give-up exit. PDH/PDL backtest:
  # 1-day hold net -12,409 (70% unresolved) vs 3-day +33,913 (9% unresolved). RISK: a 1%
  # stop is jumped by 24% of overnight gaps, so the backtest ceiling is optimistic.
  # RETIRED 2026-08-23: "v5_hold|scripts/v5_hold-paper-trade.py"

  # UNIVERSE SHADOW (2026-08-05): v5_wide = v5 on 837 liquidity-SCREENED stocks vs 200.
  # Not a "trade more" change: v5_cut proves 2.23x universe gives only 1.14x trades because
  # MAX_POSITIONS_TOTAL=20 binds first — so this tests SELECTION quality, not frequency.
  # Every symbol passed a 60-day screen (median turnover, consistency, our market impact,
  # share granularity, and mean/median <=3x so spike-day names like NIACL are excluded).
  "v5_wide|scripts/v5_wide-paper-trade.py"

  # RETIRED 2026-07-30, superseded by v10. v8 claimed to be the "April-recipe replica"
  # but runpy'd into TODAY's 1421-line v5 engine with April params as env vars — it tested
  # today's code wearing April's settings, never April's code. Its params were not even a
  # faithful April match (it set RESCORE=999/top-5/long-only; the real April engine ran
  # RESCORE=30, 4 pools, and its signal_engine emitted SHORT signals). Result over 17
  # sessions: -2,827 at 28% WR against a +1%/day, 65%-WR target. State files preserved.
  # "v8|scripts/v8-paper-trade.py"

  # V10 (2026-07-30): the ACTUAL April engine, vendored verbatim from git 9d7db34.
  # Frozen decision path (engine + signal_engine + risk_manager + composite_scorer +
  # config + April-21 ML model @ ml_score=0.25). Data layer stays CURRENT — April's
  # data_nse writes the shared cache the whole fleet reads and predates the 2026-05-08
  # cache-poisoning guards. Spec: 1cr-roadmap/design/2026-07-30-v10-april-replica-design.md
  # RETIRED 2026-08-23: "v10|scripts/v10-paper-trade.py"
  # RETIRED 2026-08-23: "v5_1L|scripts/v5_1L-paper-trade.py"
  # RETIRED 2026-08-23: "v5_cut_1L|scripts/v5_cut_1L-paper-trade.py"
  # RETIRED 2026-08-23: "v5_long_1L|scripts/v5_long_1L-paper-trade.py"

  # SMALL-CAPITAL SHADOWS (2026-08-03): same strategies at Rs 1,00,000 instead of
  # Rs 10,00,000. At Rs 10L the position sizer is never the binding constraint; at
  # Rs 10,000, with NIFTY-200 names at Rs 500-5,000/share, sizing becomes the whole
  # story and each engine can hold only a handful of names. That is the experiment.
  # Shadows, so the 9 live engines and the existing A/B series are untouched.
  # NOTE both _10k variants below INLINE their parent's params rather than chaining:
  # v5_cut/v5_long set ENGINE_NAME themselves and would clobber the shadow, writing
  # small-capital state into the LIVE directory. Caught pre-launch 2026-08-03.

  # Retired 2026-05-15 (Sprint 1) — state files preserved, scripts unchanged.
  # Uncomment to re-introduce after primary rebuild completes (~2026-07-15).
  # "v5_6|scripts/v5_6-paper-trade.py"     # Darvas-box breakout
  # "v5_7|scripts/v5_7-paper-trade.py"     # Box mean-reversion
  # "v5_8|scripts/v5_8-paper-trade.py"     # v5 with regime slot-partition disabled
  # "v6|scripts/v6-paper-trade.py"         # v4 raw signals + Track A bolt-on

  # RETIRED 2026-06-26 (TP-RCA engine audit): v7_regime beat v5 by only +Rs1,684 over 9
  # sessions and daily-gate WFO showed no edge (DSR 0.12). Parked from daily rotation; the
  # long-only book (v5_long) tests the "do shorts help?" question more cleanly. State preserved.
  # "v7_regime|scripts/v7_regime-paper-trade.py"

  # Still retired from earlier rounds:
  # "v5_2|scripts/v5_2-paper-trade.py"
  # "v5_3|scripts/v5_3-paper-trade.py"

  # SHADOW (spec 1cr-roadmap/research/2026-08-10_cost-cliff-position-sizing.md):
  # v5_size = same v5 code, FEWER AND LARGER positions. Zerodha brokerage is
  # "0.03% or Rs20/order, whichever is LOWER", so above Rs66,667 per position the
  # flat Rs20 binds and cost FALLS with size. Measured across 3,526 live trades:
  # median position Rs7,252, max ever Rs44,992 -- not one trade in 3 months
  # crossed that cliff, because base = 15% of REMAINING pool cash across 20 slots
  # decays Rs45k -> Rs7.5k by the 12th. Every measured gross edge (+0.051% to
  # +0.091%) clears cost at Rs1-2L/position and none clears at Rs7,252.
  # POOL_ALLOC={"INTRADAY":1.0} + MAX_POSITIONS_TOTAL=5 -> median Rs108,375 at
  # 0.0788% vs 0.1060%, a saving of 0.0272%/trade. Position size is the ONLY
  # variable; v5 continues unchanged as the control. WATCH: median position must
  # exceed Rs66,667 or the experiment did not happen; and slippage, since the whole
  # gain is ~3bps and a Rs1.5L order that moves the book >2bps erases it.
  # RETIRED 2026-08-23: "v5_size|scripts/v5_size-paper-trade.py"
)

# Expected number of active engines — derived from the ENGINES array length so the
# verify/launch lines never drift from reality (S2-PM-004: the old hardcoded "/7"
# was a leftover from the retired 7-engine setup; only 3 are active post-Sprint-1).
EXPECTED_ENGINES=${#ENGINES[@]}

send_telegram() {
  local msg="$1"
  if [ -f .env ]; then
    local token chat
    token=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
    chat=$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
    if [ -n "$token" ] && [ -n "$chat" ]; then
      curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${msg}" --max-time 5 > /dev/null 2>&1
    fi
  fi
}

# ═══════════════════════════ STATUS ═══════════════════════════
if [ "${1:-}" = "--status" ]; then
  echo "═══ TradePilot process status ═══"
  echo ""
  echo "Rust engine:     $(pgrep -lf 'tradepilot-engine' | head -1 || echo 'NOT RUNNING')"
  echo "Flask dashboard: $(lsof -iTCP:5050 -sTCP:LISTEN -n -P 2>/dev/null | tail -1 | awk '{print $1, $2}' || echo 'NOT RUNNING')"
  echo ""
  echo "Engines:"
  for entry in "${ENGINES[@]}"; do
    IFS='|' read -r name script <<< "$entry"
    pid=$(pgrep -f "$script" | head -1)
    printf "  %-12s %s\n" "$name" "${pid:-NOT RUNNING}"
  done
  echo ""
  echo "Monitors:"
  printf "  %-18s %s\n" "crash-watchdog"   "$(pgrep -f 'crash-watchdog.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "telegram-digest"  "$(pgrep -f 'telegram-digest.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "laptop-heartbeat" "$(pgrep -f 'laptop-heartbeat.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "auto-stop-eod"    "$(pgrep -f 'auto-stop-eod.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "satish-schedule"  "$(pgrep -f 'satish-schedule.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "profit-watchdog"  "$(pgrep -f 'profit-watchdog.py' | head -1 || echo '-')"
  printf "  %-18s %s\n" "missed-opps-wd"   "$(pgrep -f 'missed-opportunities-watchdog.py' | head -1 || echo '-')"
  echo ""
  # Show OUR caffeinate (PID-tracked, owned by launch-market.sh) rather than any
  # stranger caffeinate that might happen to be on the system.
  if [ -f "$CAFFEINATE_PID_FILE" ] && kill -0 "$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null)" 2>/dev/null; then
    echo "Caffeinate (ours): $(cat "$CAFFEINATE_PID_FILE") — wake-lock held"
  else
    echo "Caffeinate (ours): NOT RUNNING — laptop free to sleep (Wed-2026-05-27 risk)"
  fi
  exit 0
fi

# ═══════════════════════════ STOP ═══════════════════════════
if [ "${1:-}" = "--stop" ]; then
  echo "Stopping TradePilot stack..."
  pkill -f "scripts/v[0-9].*paper-trade.py" 2>/dev/null
  pkill -f "scripts/crash-watchdog.sh"  2>/dev/null
  pkill -f "scripts/telegram-digest.sh" 2>/dev/null
  pkill -f "scripts/laptop-heartbeat.sh" 2>/dev/null
  pkill -f "scripts/auto-stop-eod.sh"   2>/dev/null
  pkill -f "scripts/satish-schedule.sh" 2>/dev/null
  pkill -f "profit-watchdog.py"         2>/dev/null
  pkill -f "missed-opportunities-watchdog.py" 2>/dev/null
  pkill -f "tradepilot-engine"          2>/dev/null
  if [ -f /tmp/tradepilot-wifi-watchdog.pid ]; then
    kill "$(cat /tmp/tradepilot-wifi-watchdog.pid)" 2>/dev/null && echo "  ✓ wifi-watchdog stopped"
    rm -f /tmp/tradepilot-wifi-watchdog.pid
  fi
  pkill -f "scripts/wifi-watchdog.sh" 2>/dev/null
  stop_caffeinate
  sleep 2
  remaining=$(ps aux | grep -cE "paper-trade|crash-watchdog|telegram-digest|laptop-heartbeat|auto-stop-eod|satish-schedule|tradepilot-engine" | grep -v grep)
  echo "Remaining: ${remaining}"
  send_telegram "🛑 TradePilot stopped at $(date +%H:%M). Full stack shut down."
  exit 0
fi

# ═══════════════════════════ LAUNCH ═══════════════════════════
echo "════════════════════════════════════════════════════════════"
echo "  TradePilot FULL LAUNCH — $TODAY $STAMP"
echo "════════════════════════════════════════════════════════════"

# [0/9] Sleep prevention FIRST — before anything else can fail and leave the
# laptop free to nap through the market session (lost Wed 2026-05-27 this way).
echo "[0/9] Locking laptop awake (caffeinate)..."
start_caffeinate

# [0/9] Network guardian — keep laptop on hotspot "Pro" through the session (2026-06-05)
WIFI_WATCHDOG_PID_FILE="/tmp/tradepilot-wifi-watchdog.pid"
mkdir -p "$HOME/Library/Logs/tradepilot"
if [ -f "$WIFI_WATCHDOG_PID_FILE" ] && kill -0 "$(cat "$WIFI_WATCHDOG_PID_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "[0/9] wifi-watchdog already running (PID $(cat "$WIFI_WATCHDOG_PID_FILE"))"
else
  echo "[0/9] Starting wifi-watchdog (network -> hotspot 'Pro')..."
  WIFI_TARGET_SSID="Pro" nohup bash "$ROOT/scripts/wifi-watchdog.sh" > "$HOME/Library/Logs/tradepilot/wifi-watchdog.log" 2>&1 &
  echo $! > "$WIFI_WATCHDOG_PID_FILE"
  echo "  ✓ wifi-watchdog started (PID $!) — target SSID 'Pro'"
fi

# [0/9] Kill stale processes
echo "[0/9] Cleaning stale processes..."
pkill -f "scripts/v[0-9].*paper-trade.py" 2>/dev/null
pkill -f "scripts/crash-watchdog.sh"  2>/dev/null
pkill -f "scripts/telegram-digest.sh" 2>/dev/null
pkill -f "scripts/laptop-heartbeat.sh" 2>/dev/null
pkill -f "scripts/auto-stop-eod.sh"   2>/dev/null
pkill -f "scripts/satish-schedule.sh" 2>/dev/null
pkill -f "tradepilot-engine"          2>/dev/null
sleep 2

# [0.5/9] Pre-launch verification — catches import/syntax bugs BEFORE engines deploy.
# Added 2026-05-11 after Monday morning's v4 crash (preflight import path was wrong,
# crashed at 09:30 IST market open). Runs only the smoke section (~2s) for speed.
#
# 2026-05-12 FIX: previous version was `if cmd 2>&1 | tail -5; then` which checks
# tail's exit code (always 0), NOT the upstream verify script's. Result: gate
# always passed even when smoke failed. Fixed by capturing output first, then
# checking the script's actual exit code separately.
echo "[0.5/9] Pre-launch verification (smoke test — would have caught Monday's crash)..."
SMOKE_OUTPUT=$(./scripts/sarathi-verify.sh --smoke --quiet 2>&1)
SMOKE_EXIT=$?
echo "$SMOKE_OUTPUT" | tail -5
if [ "$SMOKE_EXIT" -eq 0 ]; then
  echo "  ✓ Engine scripts import + compile clean"
else
  echo ""
  echo "  ✗ PRE-LAUNCH SMOKE FAILED (exit $SMOKE_EXIT) — refusing to start engines."
  echo "  → Run: ./scripts/sarathi-verify.sh   (full output)"
  echo "  → Fix the issue, then re-launch."
  exit $EX_SMOKE_FAILED
fi

# [0.6/9] Git-hygiene guard — warn (never block) if live engine code is uncommitted.
# Added 2026-07-06 after root-causing 15-day silent drift of the v5_flip roster.
echo "[0.6/9] Git-hygiene check (uncommitted-code drift guard)..."
./scripts/git-hygiene-check.sh || true

# [1/9] Rust engine
echo "[1/9] Starting Rust engine (execution + risk)..."
if [ -f "./engine/target/release/tradepilot-engine" ]; then
  nohup ./engine/target/release/tradepilot-engine > /tmp/rust-engine.log 2>&1 &
  echo "  ✓ Rust engine launched (PID $!)"
  sleep 2
  # Health check
  if curl -s http://localhost:8080/health | grep -q success; then
    echo "  ✓ Rust /health OK (risk config loaded from .env)"
  else
    echo "  ⚠ Rust started but /health not responding — continuing"
  fi
else
  echo "  - Rust engine DISABLED (2026-06-05 decision: dropped as optional layer)."
  echo "    Python engines run solo via rust_bridge offline-fallback. To re-enable:"
  echo "    cd engine && cargo build --release"
  # Rust is OPTIONAL now — do NOT set RUST_MISSING; this is not a failure.
fi

# [2/9] Flask dashboard
echo "[2/9] Starting Flask dashboard (localhost:5050)..."
if lsof -iTCP:5050 -sTCP:LISTEN -n -P > /dev/null 2>&1; then
  echo "  ✓ already running on :5050"
else
  cd prototype && nohup python3 app.py > /tmp/flask.log 2>&1 &
  cd "$ROOT"
  echo "  ✓ Flask launched (PID $!)"
fi

# [3/9] Capture today's dashboard score snapshot (added 2026-04-23)
# Foundation for consensus-pick analysis: archives the BUY/HOLD list BEFORE
# engines start trading. ~10-15s. Run in background so it doesn't gate engines.
echo "[3/9] Archiving today's dashboard scores in background..."
nohup python3 ./scripts/archive-daily-scores.py > "logs/archive-scores-${TODAY}.log" 2>&1 &
echo "  ✓ daily scores archiver (PID $!) → docs/dashboard-scores/${TODAY}.json"

# [4/9] Engines
echo "[4/9] Launching ${EXPECTED_ENGINES} paper-trade engines..."
for entry in "${ENGINES[@]}"; do
  IFS='|' read -r name script <<< "$entry"
  if [ ! -f "$script" ]; then
    echo "  ✗ $name — script missing"
    # Deferred failure (S2-PM-006): a defined engine is missing on disk. Don't
    # clobber a prior RUST_MISSING (3) — only set ENGINE_MISSING if still clean.
    [ "$EXIT_CODE" -eq 0 ] && EXIT_CODE=$EX_ENGINE_MISSING
    continue
  fi
  nohup python3 "$script" > "logs/${name}-${TODAY}.log" 2>&1 &
  echo "  ✓ $name (PID $!)"
  sleep 1
done

# [5/9] Crash watchdog
echo "[5/9] Launching crash-watchdog..."
nohup ./scripts/crash-watchdog.sh > "logs/watchdog-${TODAY}.log" 2>&1 &
echo "  ✓ watchdog (PID $!)"

# [6/9] Telegram digest (30-min)
echo "[6/9] Launching telegram-digest (30-min Soumya updates)..."
nohup ./scripts/telegram-digest.sh > "logs/telegram-digest-${TODAY}.log" 2>&1 &
echo "  ✓ digest (PID $!)"

# [7/9] Laptop heartbeat (15-min)
echo "[7/9] Launching laptop-heartbeat..."
nohup ./scripts/laptop-heartbeat.sh > "logs/laptop-heartbeat-${TODAY}.log" 2>&1 &
echo "  ✓ heartbeat (PID $!)"

# [8/9] Auto-stop-EOD
echo "[8/9] Launching auto-stop-eod (fires 15:35)..."
nohup ./scripts/auto-stop-eod.sh > "logs/auto-stop-${TODAY}.log" 2>&1 &
echo "  ✓ auto-stop (PID $!)"

# [9/9] Satish schedule — only if his chat ID is set
echo "[9/9] Satish schedule check..."
if grep -q "^SATISH_TELEGRAM_CHAT_ID=[0-9]" .env 2>/dev/null; then
  nohup ./scripts/satish-schedule.sh > "logs/satish-schedule-${TODAY}.log" 2>&1 &
  echo "  ✓ satish-schedule launched (PID $!) — will send 4 trade reports to Satish today"
else
  echo "  ⊘ SATISH_TELEGRAM_CHAT_ID not set — skipping. Run manually once Satish messages bot."
fi

# [10/11] Profit-watchdog — 30-min P&L snapshots (TP-CLN-005: was started by hand every morning)
echo "[10/11] Launching profit-watchdog (validation: what we're earning)..."
if pgrep -f "profit-watchdog.py" > /dev/null 2>&1; then
  echo "  ✓ already running"
else
  nohup python3 ./scripts/profit-watchdog.py > "logs/profit-watchdog-${TODAY}.log" 2>&1 &
  echo "  ✓ profit-watchdog (PID $!)"
fi

# [11/11] Missed-opportunities-watchdog — 180s cycle (TP-CLN-005)
# Kill any stale instance first (it has no EOD self-stop, and a survivor would keep
# the old undated log and skip a fresh dated one) — so every day gets ONE clean
# dated log 09:00..15:35. Fixes the 2026-06-18 mixed-multi-day-log bug.
echo "[11/11] Launching missed-opps-watchdog (validation: left on the table)..."
pkill -f "missed-opportunities-watchdog.py" 2>/dev/null && sleep 1
nohup python3 ./scripts/missed-opportunities-watchdog.py > "logs/missed-opps-watchdog-${TODAY}.log" 2>&1 &
echo "  ✓ missed-opps-watchdog (PID $!) — fresh dated log logs/missed-opps-watchdog-${TODAY}.log"

# Verify
echo ""
echo "[verify] Checking process health..."
sleep 3
alive=$(pgrep -f "scripts/v[0-9].*paper-trade.py" | wc -l | tr -d ' ')
wd=$(pgrep -f "scripts/crash-watchdog.sh" | wc -l | tr -d ' ')
rust=$(pgrep -f "tradepilot-engine" | wc -l | tr -d ' ')
echo "  Engines: $alive/${EXPECTED_ENGINES}  |  Watchdog: $wd/1  |  Rust: $rust/1"

# If fewer engines came up alive than defined (e.g. one crashed on boot), flag a
# deferred ENGINE_MISSING — unless a higher-priority RUST_MISSING already stands.
if [ "$alive" -lt "$EXPECTED_ENGINES" ] && [ "$EXIT_CODE" -eq 0 ]; then
  EXIT_CODE=$EX_ENGINE_MISSING
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  FULL LAUNCH COMPLETE — $(date +%H:%M:%S)"
echo "  Status check:  ./scripts/launch-market.sh --status"
echo "  Quick digest:  python3 scripts/status-digest.py"
echo "  Stop all:      ./scripts/launch-market.sh --stop"
echo "════════════════════════════════════════════════════════════"

send_telegram "🚀 TradePilot FULL LAUNCH at $(date +%H:%M).
Engines: ${alive}/${EXPECTED_ENGINES} · Rust: ${rust}/1 · Watchdog: ${wd}/1
ML model: fixed (best_iter=1726, india_vix #1)
Rust cap: 150 (was 30)
Ready for battle."

# S2-PM-006: return the deferred failure code (0 on a clean happy-path launch).
# market_go.py reads this — any non-zero triggers a SARATHI-CDE BLOCK + page.
exit $EXIT_CODE
