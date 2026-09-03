# Task 6 Report: Waitlist Approval CLI

## Status
✅ **DONE**

## Commit
- SHA: `8e9a1be`
- Message: "feat(accounts): waitlist list and approve"

## Test Counts
- CLI tests (test_waitlist_cli.py): **9 passed**
- Full suite (tests/): **440 passed** (431 baseline + 9 new = 440)

## Step 5 Verification (Ordering Proof)

The test `test_a_failed_send_leaves_the_row_pending` proves the send-before-mark ordering is essential:

**RED (incorrect order — UPDATE before send):**
```
>       assert row["approved_at"] is None
E       AssertionError: assert '2026-09-03T01:27:59.731566+00:00' is None
```

**GREEN (correct order — send before UPDATE):**
```
tests/test_waitlist_cli.py::test_a_failed_send_leaves_the_row_pending PASSED [100%]
```

The RED failure demonstrates that marking approved before sending leaves a row that looks satisfied while the client never receives an invite.

## Step 6: Live Database Verification
Product database (`prototype/tradepilot_app.db`):
- **Tables present:** `[]` (empty — no tables)
- **Specifically absent:** `waitlist`, `auth_tokens`
- **Status:** ✅ Confirmed uncontaminated

The empty product database proves all tests operated on temporary test databases via the monkeypatched `open_store()` seam. No test accidentally reached production schema.

## Deliverables
- ✅ `scripts/waitlist.py` — CLI for `list` and `approve` subcommands
- ✅ `tests/test_waitlist_cli.py` — 9 comprehensive tests
- ✅ Requirements.txt unchanged (byte-identical)
- ✅ All 440 tests pass
