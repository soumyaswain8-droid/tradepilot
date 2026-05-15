# SARATHI-LRN — Learning Verification

**Triggered on:** every `dp learn` invocation, every INSERT into DevPilot DB `learnings` table, every write to `.sdlc/learnings/`.

**Veto power:** YES — can REJECT a learning so it is not stored, or tag it `verification=UNVERIFIED` to prevent it being treated as canonical.

## Rules

### LRN-001 — Source cited
Every learning containing a numerical claim must have a `source` field with at least one of: URL, file path, commit SHA, paper DOI, dataset reference.

- **Check:** `source` field present and non-empty; if URL, must resolve at write-time (HTTP 200) — but `WARN` not `BLOCK` if temporarily down.
- **Fail action:** `REJECT` — learning not stored. Caller must add source and re-submit.

### LRN-002 — Numbers reproducible
If learning cites a metric (IC, Sharpe, WR, abnormal return %), the source must be re-fetchable. The check verifies the URL or file still produces the cited number — sample-checked weekly by Knowledge Archivist.

- **Check:** monthly Archivist sweep re-validates 10% of stored learnings at random.
- **Fail action:** `WARN` and downgrade existing `verification` to `PARTIAL`. Surface in dashboard.

### LRN-003 — Conflict detection
If new learning contradicts an existing learning at priority ≥ HIGH, escalate to Architect before storing.

- **Check:** simple keyword + sentiment overlap with existing high-priority learnings. False positives are acceptable; missed conflicts are not.
- **Fail action:** `ESCALATE` — Architect must review and either resolve conflict (mark one stale) or accept both with caveat note.

### LRN-004 — Fabrication guard
Round-number heuristic: claims with "75%", "11.2%", "₹2000cr", round Sharpes (1.0, 1.5, 2.0) get flagged for manual review unless the source is a primary research paper.

- **Check:** regex `\b(\d{1,2}(\.\d)?|\d{4})\s*(%|cr|crore|bps)\b` against suspicious-list `[75, 80, 50, 11.2, 2000, 1000]`.
- **Fail action:** `WARN` and mark `verification=UNVERIFIED` until reviewed.

### LRN-005 — India-context check
Learnings about Indian markets must cite India-specific evidence (SEBI, NSE, BSE, RBI, AMFI, or peer-reviewed paper using Indian data). Borrowing US/EU studies without Indian validation is allowed but flagged.

- **Check:** source URL/path contains India-context tokens, OR explicit `country=IN` tag, OR the learning marks itself as `cross_market=true`.
- **Fail action:** `WARN` and tag `verification=NEEDS_INDIA_VALIDATION`.

## Verification States

Every learning carries one of:
- `VERIFIED` — passes all applicable rules with primary sources
- `PARTIAL` — passes most rules; one or more WARN flags
- `NEEDS_INDIA_VALIDATION` — borrowed from non-India literature
- `UNVERIFIED` — failed LRN-004 or failed primary source check; not used by agents until cleared
- `REJECTED` — failed LRN-001; not stored

## Output Schema

Every check appends to `docs/sarathi/ledger/YYYY-MM-DD.jsonl`:
```json
{"ts":"...","family":"SARATHI-LRN","rule":"LRN-001","subject":"<learning-id>","result":"PASS|WARN|BLOCK","evidence":{...},"reason":"..."}
```

And to per-learning record `docs/sarathi/reports/learnings/<learning-id>.json`.

## Backward Sweep (Sprint 1)

Knowledge Archivist runs `scripts/sarathi/verify.py --sweep learnings` against all existing learnings in DevPilot DB:
1. Tag each with current verification state.
2. Specifically retag these Apr-8 master research claims (flagged by Agent E as uncorroborated):
   - "Insider buying cluster 3+/30d → 11.2% over 6 months" → `UNVERIFIED` (LRN-004)
   - "FII net sell > ₹2000cr → bearish 1-3d" → `NEEDS_INDIA_VALIDATION` (regime-dependent, weak in 2026)
   - "GIFT Nifty premium > 0.3% → 75% gap-up" → `PARTIAL` (75% directional; magnitude error 15-40pt)
3. Produce sweep report at `docs/sarathi/reports/learnings/_sweep_2026-05-15.md`.
