# Task 3 Report: The Mailer

**Status: DONE**

**Commit:** e5233e7

**Test Results:**
- Mailer tests: 7 pass
- Full suite: 404 pass

**DNS Check:**
- `./scripts/check-mail-dns.sh sidewall.in` → exit 0
- MX, SPF, DKIM all OK; DMARC p=quarantine present

**Transport Seam Verification:**
All 7 tests in `tests/test_mailer.py` pass a `transport=` argument:
- test_it_sends_to_the_right_recipient ✓
- test_the_message_carries_the_subject_and_body ✓
- test_it_sends_from_the_configured_address ✓
- test_it_uses_the_workspace_smtp_endpoint ✓
- test_sending_without_credentials_raises ✓
- test_a_missing_password_alone_also_raises ✓
- test_nothing_is_sent_when_credentials_are_missing ✓

No test path can reach `_smtp_transport`.

---

## Fix Round 1 of 5

**Status: DONE**

**Finding 1 Fixed: `test_it_sends_from_the_configured_address` now pins the literal**
- Changed assertion from `== mailer.FROM_ADDRESS` to `== "soumya@sidewall.in"`
- Proof: With wrong address → `F` (FAILED), restored → `.` (PASSED)

**Finding 2 Fixed: Guard now tested for empty strings**
- Added `test_a_missing_user_alone_raises`
- Added `test_an_empty_password_raises` (realistic deployment failure)
- Added `test_an_empty_user_raises`
- Proof: With `is None` guard (broken) → `.FF` (two empty-string tests fail), restored → `...` (all pass)

**Commit:** 0ee3ffb

**Test Results:**
- Full suite: 407 pass (404 + 3 new tests)
- `git diff prototype/mailer.py`: empty ✓
