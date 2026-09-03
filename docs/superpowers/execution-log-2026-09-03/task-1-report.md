# Task 1 Report: Token Storage

**Status:** DONE

**Commit SHA:** fe2b732

**Test Counts:**
- Token tests: 11 passing
- Full auth/accounts suite: 35 passing (11 new + 24 existing)

## Step 6: Atomicity Proof

**RED (without AND used_at IS NULL):**
```
tests/test_auth_tokens.py::test_a_token_can_only_be_consumed_once FAILED [100%]

>       assert second == (None, None)
E       AssertionError: assert ('invite', 'p...@example.com') == (None, None)
E         At index 0 diff: 'invite' != None
```

**GREEN (with AND used_at IS NULL restored):**
```
tests/test_auth_tokens.py::test_a_token_can_only_be_consumed_once PASSED [100%]

1 passed in 0.07s
```

## Analysis

The sequential test proves single-use works in one-at-a-time execution: without the `AND used_at IS NULL` clause, the second consume succeeds and returns data instead of (None, None). With the clause, the second attempt correctly returns (None, None).

**What this does NOT prove:** atomicity under true concurrency. The test runs sequentially in one SQLite process; two simultaneous HTTP requests are beyond its scope. The atomic UPDATE is what **would** prevent a race: if two requests execute the SELECT→UPDATE pattern at nearly the same time, both could pass the old read-then-write check before either writes. One atomic UPDATE that checks `used_at IS NULL` in the WHERE clause ensures only one succeeds—the database serializes the writes, and the second's UPDATE matches zero rows.

This test demonstrates the mechanism; true concurrency testing would need separate processes hitting the same database and prefetching links in mail clients to be real.
