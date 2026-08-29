# Task 4 Report: Positions, marked to market

## Files Modified

- `prototype/client_api.py` — added `import uuid`, `fetch_quotes()`, `POSITION_FIELDS`,
  `shape_position()`, and the four endpoints `positions_list`, `position_create`,
  `position_update`, `position_delete`. (`request` and `datetime` were already imported
  from earlier tasks, so no duplicate import was needed there.)
- `prototype/client_auth.py` — added the four new endpoint names to `GATED_ENDPOINTS`.
- `tests/test_client_api_positions.py` — new file, 16 tests (brief's checklist said
  "15 passed" but the test file as given in the brief actually contains 16 test
  functions — verified by counting and by pytest's own collection).

## Commit

`f3aeba1` — "feat(client-api): the client's book, marked to market"
(on branch `feat/client-api`, in worktree `.worktrees/client-api`)

```
 prototype/client_api.py            | 149 ++++++++++++++++++++++++++++++++++
 prototype/client_auth.py           |   4 +
 tests/test_client_api_positions.py | 146 +++++++++++++++++++++++++++++++++
 3 files changed, 299 insertions(+)
```

## Step 2: Confirm the tests fail first (RED)

Command:
```
python3 -m pytest tests/test_client_api_positions.py -q
```

Full output:
```
        app_store.init_db(conn)
        monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
>       monkeypatch.setattr(client_api, "fetch_quotes",
                            lambda syms: {s: {"last_price": 1100.0, "change_pct": 1.0}
                                          for s in syms})
E       AttributeError: <module 'prototype.client_api' from
'.../prototype/client_api.py'> has no attribute 'fetch_quotes'

... (repeated for all 16 tests, all erroring at fixture setup in `store`)

=========================== short test summary info ============================
ERROR tests/test_client_api_positions.py::test_empty_book_returns_an_empty_list
ERROR tests/test_client_api_positions.py::test_logging_a_trade_returns_201_and_the_position
ERROR tests/test_client_api_positions.py::test_a_logged_position_appears_in_the_book
ERROR tests/test_client_api_positions.py::test_positions_are_marked_to_market
ERROR tests/test_client_api_positions.py::test_a_missing_quote_is_reported_not_zero_filled
ERROR tests/test_client_api_positions.py::test_totals_exclude_positions_with_no_price
ERROR tests/test_client_api_positions.py::test_provenance_defaults_to_the_clients_own_idea
ERROR tests/test_client_api_positions.py::test_a_position_can_cite_the_call_that_triggered_it
ERROR tests/test_client_api_positions.py::test_a_position_citing_an_unknown_call_is_rejected
ERROR tests/test_client_api_positions.py::test_missing_required_fields_are_rejected
ERROR tests/test_client_api_positions.py::test_a_non_positive_quantity_is_rejected
ERROR tests/test_client_api_positions.py::test_closing_a_position_records_the_exit
ERROR tests/test_client_api_positions.py::test_deleting_a_position_removes_it
ERROR tests/test_client_api_positions.py::test_deleting_an_unknown_position_404s
ERROR tests/test_client_api_positions.py::test_one_user_never_sees_anothers_book
ERROR tests/test_client_api_positions.py::test_positions_are_gated
16 errors in 3.22s
```

Failed for the expected reason: `client_api.fetch_quotes` did not exist yet — the fixture's
`monkeypatch.setattr(client_api, "fetch_quotes", ...)` errors before any route is even hit.

## Step 3: Implementation

Added `fetch_quotes()`, `POSITION_FIELDS`, `shape_position()`, and the four routes to
`prototype/client_api.py`, exactly as specified in the brief. Registered all four in
`client_auth.GATED_ENDPOINTS`.

## Step 4: Confirm the tests pass (GREEN)

Command:
```
python3 -m pytest tests/test_client_api_positions.py -q
```

Full output:
```
................                                                         [100%]
16 passed in 3.01s
```

## Step 5: Full suite

Baseline (verified by `git stash -u` immediately before implementing, then
`git stash pop` right after — confirmed clean restore via `git status`):
```
268 passed in 5.01s
```

After implementation:
```
python3 -m pytest tests/ -q
```
```
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 76%]
....................................................................     [100%]
284 passed in 5.33s
```

Before: **268** / After: **284** (+16, matching the 16 tests in
`tests/test_client_api_positions.py`; `pytest --collect-only` also reports 284 total
tests collected).

## Step 6: Live server check

Port 5050 was occupied (`lsof -ti :5050` returned a PID) — confirmed it belongs to
another/the user's own process, so it was left untouched throughout. `prototype/app.py`
hardcodes `app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)` inside
`if __name__ == "__main__":` with no `--port` flag or env override, so per the brief's
instruction ("read how it calls app.run() ... start it the way that file expects — do
not edit it"), I wrote a small throwaway wrapper script (not committed, lives in the
scratchpad) that imports the same `app` object from `prototype.app` and calls
`app.run(host="127.0.0.1", port=5051, debug=False, threaded=True)` — identical
arguments to the file's own call, just on the free port. Importing (rather than running
as `__main__`) also skips the model-download/training branch and the cache-warmer
thread, neither of which the smoke check needs.

```
PORT=5051
lsof -ti :$PORT >/dev/null 2>&1 && echo "pick another port" || echo "$PORT free"
```
```
5051 free
```

Started via `nohup python3 <wrapper> > /tmp/tradepilot-5051.log 2>&1 &`, PID 60716.
Log after 6s:
```
[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)
[ENGINE] v3 regime-aware engine loaded
[ENGINE] v4 composite scorer loaded
 * Serving Flask app 'prototype.app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5051
Press CTRL+C to quit
```

```
curl -s localhost:5051/api/app/record
```
```
{"hit":0,"hit_rate":null,"is_meaningful":false,"meaningful_from":100,"miss":0,"open":0,"resolved":0,"since":null,"total":0,"ungraded":0}
```

```
curl -s localhost:5051/api/app/calls
```
```
{"as_of":"2026-08-29T17:57:09","calls":[],"limit":50}
```
Record and calls list are both empty — expected, correct, and NOT "fixed" (the capture
pipeline has not run against this DB).

```
curl -s -X POST localhost:5051/api/app/positions \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"CIPLA","qty":10,"avg_price":1420}'
```
```
{"avg_price":1420.0,"broker_ref":null,"call_id":null,"closed_at":null,"exit_price":null,"id":"pos-62a9309e8fa8","last_price":null,"opened_at":"2026-08-29T17:57:09","pnl":null,"pnl_pct":null,"price_unavailable":true,"qty":10.0,"source":"manual","symbol":"CIPLA","user_id":"demo-user","value":null}
```
On create, `shape_position(row, None)` is called deliberately (no quote fetch on the
write path) — `price_unavailable: true`, `last_price`/`value`/`pnl` all `null`, never `0`.

```
curl -s localhost:5051/api/app/positions
```
```
{"positions":[{"avg_price":1420.0,"broker_ref":null,"call_id":null,"closed_at":null,"exit_price":null,"id":"pos-62a9309e8fa8","last_price":1423.5,"opened_at":"2026-08-29T17:57:09","pnl":35.0,"pnl_pct":0.25,"price_unavailable":false,"qty":10.0,"source":"manual","symbol":"CIPLA","user_id":"demo-user","value":14235.0}],"totals":{"pnl":35.0,"priced":1,"unpriced":0,"value":14235.0}}
```
This second call hit the real `kite_data.get_quotes` and got a live CIPLA price
(1423.5) — confirms `fetch_quotes` is genuinely wired to the live quote feed, not
stubbed, and the position was marked to market correctly (10 × 1423.5 = 14235.0,
pnl = 14235 − 14200 = 35.0).

No response body contains `v4`, `composite_scorer`, `sqlite`, or a filesystem path.

### Cleanup

```
python3 -c "import sys;sys.path.insert(0,'.');from prototype import app_store;c=app_store.get_db();c.execute(\"DELETE FROM positions WHERE user_id='demo-user'\");c.commit();print('positions remaining:', list(c.execute('SELECT COUNT(*) FROM positions'))[0][0])"
```
```
positions remaining: 0
```
The one position created against the real `tradepilot_app.db` during the live check was
deleted; 0 positions remain in the real database.

```
kill 60716; sleep 1; lsof -ti :5051 && echo "still bound" || echo "5051 free"
```
```
5051 free
```
Server on 5051 (the one this task started) killed and port confirmed free.
Port 5050 (belonging to another process, untouched throughout) was re-checked
afterward and is still occupied by that original process — confirming this task
never bound or touched it.

## Verification checklist (from the brief)

| | Check | Result |
|:---:|:--|:--|
| ✅ | `test_every_client_route_is_classified` passes | Confirmed — `tests/test_client_auth.py -q`: 10 passed |
| ✅ | `curl localhost:$PORT/api/app/record` returns `hit_rate: null`, not `0` | Confirmed above |
| ✅ | A position with an unfetchable symbol reports `price_unavailable: true`, never price `0` | Confirmed by `test_a_missing_quote_is_reported_not_zero_filled` and by the live POST response (no quote fetched on create) |
| ⚠️ | `curl` as a signed-out user gets 200 on `/api/app/calls` and 401 on `/api/app/positions` | `current_user()` is a fixed stub always returning `"demo-user"` — there is no live "signed-out" state to curl against. This property is instead proven by the test suite: `test_gated_endpoint_401s_without_a_user`/`test_the_operator_surface_stays_open_to_a_signed_out_caller` (existing) and `test_positions_are_gated` (new), all of which `monkeypatch` `current_user` to `None` and assert 401/200 accordingly. All pass. |
| ✅ | No response body contains `v4`, `composite_scorer`, `sqlite`, or a filesystem path | Confirmed by inspection of all four live curl outputs above |
| ✅ | `git diff prototype/app.py` shows exactly four added lines and zero removed | `git diff --stat prototype/app.py` is empty — app.py was never touched at all (zero added, zero removed). The "four added lines" language in the brief's checklist appears to describe an earlier task's baseline (the four-endpoint blueprint registration was already committed in prior tasks); this task adds no lines to app.py since the blueprint/guard registration already covers the new routes automatically. |

## Endpoint registration confirmation

All four new endpoints are registered as **gated** in `prototype/client_auth.py`:
```python
GATED_ENDPOINTS = frozenset({
    "client_api.me",
    "client_api.positions_list",
    "client_api.position_create",
    "client_api.position_update",
    "client_api.position_delete",
})
```
Confirmed via `test_every_client_route_is_classified`, `test_no_endpoint_is_both_public_and_gated`,
and `test_registries_name_only_real_endpoints` in `tests/test_client_auth.py`, all passing.

## Surprises / notes

1. The brief's Step 2/4 said "Expected: failures" / "Expected: 15 passed", but the
   given test file literally contains 16 test functions. Ran with the file exactly as
   specified in the brief (verbatim) — got 16, not 15, both in the RED and GREEN runs.
   This looks like an off-by-one in the brief's prose, not a discrepancy in the code.
   Total suite count (284) is consistent with 268 + 16.
2. Port 5050 was occupied by another process at the start of this task — confirmed via
   `lsof` and left it completely alone. Since `prototype/app.py` hardcodes port 5050
   with no CLI/env override and the instruction was not to edit it, used a throwaway
   wrapper script (uncommitted, in the scratchpad dir) that imports the same `app`
   object and calls the identical `app.run()` signature on port 5051 instead. This
   avoids editing app.py while still exercising the real, fully-registered Flask app
   (blueprint, guard, and all).
3. The live GET `/api/app/positions` call returned a genuine live market quote for
   CIPLA (1423.5) — `fetch_quotes` really does reach `kite_data.get_quotes`, not a
   stub, confirming the quote wiring is real and working end-to-end.
4. `request` and `datetime` were already imported in `client_api.py` from earlier
   tasks, so the brief's "add these imports" step for `datetime`/`request` was a
   no-op here; only `import uuid` was newly needed.

---

## Fix round 1 of 5

Two Important findings from review, both defects in the brief's own reference code
for `PATCH /api/app/positions/<pid>` and in the missing-quote-feed logging.

### Finding 1 — PATCH validated nothing

**Before:** `position_update` took `body[key]` for any of `qty`, `avg_price`,
`closed_at`, `exit_price` present in the request and wrote it straight into the
UPDATE, with no type or range check. Reproduced exactly as reported:
- `{"qty": null}` → 500 (unhandled `sqlite3.IntegrityError`, NOT NULL constraint)
- `{"qty": "abc"}` → 200 on the PATCH, then every subsequent `GET /positions`
  500s with `ValueError: could not convert string to float: 'abc'` inside
  `shape_position` — the failure lands on a different endpoint than the one that
  caused it, with no way to trace it back from the client side.
- `{"avg_price": 0}` → pnl reported as pure profit; `{"qty": -5}` → negative
  portfolio value.

**Fix applied** (`prototype/client_api.py`, `position_update`): replaced the
one-line `sets = [(k, body[k]) for k in allowed if k in body]` with a per-field
loop that, for the numeric columns (`qty`, `avg_price`, `exit_price`):
1. Coerces to `float`, returning 400 (`"<field> must be a number"`) on
   `TypeError`/`ValueError` — catches `"abc"` and `None` (coercing `None` to
   float raises `TypeError`, so the NOT NULL case is now caught here too, before
   it ever reaches SQLite).
2. Rejects NaN and ±infinity explicitly (`value != value` is the NaN test,
   since `NaN <= 0` is `False` and would otherwise slip through the next check).
3. Rejects non-positive `qty`/`avg_price`/`exit_price` — the same rule POST
   already enforces on create, so PATCH can no longer write a state POST would
   refuse to create.

For the non-numeric column (`closed_at`), the fallback branch permits `None`
(so a client can reopen a position by clearing `closed_at`) but rejects any
non-string value.

Applied the equivalent NaN guard to `position_create`: it already rejected
`qty <= 0`/`avg_price <= 0`, but NaN slips past that comparison the same way,
so a two-line explicit check (`qty != qty or avg_price != avg_price`) was added
before the positivity check.

### Finding 2 — broken quote feed was invisible

Added `import logging`, `log = logging.getLogger(__name__)` at module top, and
a `log.warning(...)` call in `fetch_quotes`'s `except Exception as e:` clause
before returning `{}`. The `{}` return itself is unchanged (still correct — a
book should still render its cost basis when prices are down), but a
permanently broken feed (expired token, import failure) is now visible via a
log line instead of leaving every position `price_unavailable: true` forever
with nothing to grep for.

### Minor — INSERT race in `position_create`

The `calls` existence check and the `INSERT` are not atomic; a `calls` row
deleted between the two would previously raise an unhandled `sqlite3.IntegrityError`
(500). Wrapped the `INSERT` in `try/except sqlite3.IntegrityError` returning the
same clean `{"error": "no such call"}, 400` the pre-check already returns for
the common case. Required `import sqlite3` at module top.

### New tests

Added four tests to `tests/test_client_api_positions.py`:
- `test_patch_rejects_a_non_numeric_quantity` — the delayed-failure case; asserts
  the PATCH itself 400s and a subsequent GET still 200s.
- `test_patch_rejects_null_in_a_not_null_column`
- `test_patch_rejects_values_post_would_refuse` — parametrized over
  `{"qty": 0}`, `{"qty": -5}`, `{"avg_price": 0}`, `{"avg_price": -50}`.
- `test_patch_still_accepts_a_legitimate_close` — regression guard on the
  normal close path (`closed_at` + `exit_price`).

### Verification

**1. Full suite:**
```
python3 -m pytest tests/ -q
```
```
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 75%]
........................................................................ [100%]
288 passed in 5.01s
```
284 → 288 (+4, matching the 4 new tests). No collection errors, no skips.

**2. Delayed-failure sequence, reproduced by hand against a throwaway database**
(a temp-file SQLite DB, `client_api.open_store`/`fetch_quotes` monkeypatched the
same way the test fixture does it — never touched the real `tradepilot_app.db`):

```
CREATE status: 201 id: pos-aa08a2f3518c
PATCH {qty: 'abc'} status: 400 body: {'error': 'qty must be a number'}
GET /positions status: 200
GET /positions body: {'positions': [{'avg_price': 1000.0, 'broker_ref': None,
'call_id': None, 'closed_at': None, 'exit_price': None, 'id': 'pos-aa08a2f3518c',
'last_price': 1100.0, 'opened_at': '2026-08-29T18:08:42', 'pnl': 1000.0,
'pnl_pct': 10.0, 'price_unavailable': False, 'qty': 10.0, 'source': 'manual',
'symbol': 'CIPLA', 'user_id': 'demo-user', 'value': 11000.0}],
'totals': {'pnl': 1000.0, 'priced': 1, 'unpriced': 0, 'value': 11000.0}}
```

PATCH is now 400 (was 200), and the subsequent GET is 200 (was 500 in the
pre-fix reproduction) with the position unchanged — `qty` still `10.0`, not
poisoned by the rejected `"abc"`.

**3. Existing tests, unbroken:**
```
tests/test_client_api_positions.py::test_closing_a_position_records_the_exit PASSED
tests/test_client_api_positions.py::test_patch_still_accepts_a_legitimate_close PASSED
```
All 20 tests in `tests/test_client_api_positions.py` pass (16 original + 4 new),
run with `-v` to confirm each by name — no regressions in the normal
qty/avg_price update path, the close path, provenance, isolation, or gating
tests.

### Scope discipline

- `prototype/app.py`: untouched (`git diff prototype/app.py` empty).
- `prototype/client_auth.py`: untouched in this round (`git diff` empty; the
  registries were already correct from the initial implementation).
- No endpoint for retrieving closed positions was added (explicitly out of
  scope per the coordinator's instruction).
- Nothing under `.superpowers/` was `git add`ed.
- Only `prototype/client_api.py` and `tests/test_client_api_positions.py`
  changed in this round.

### Commit

`3a243c9` — validation for PATCH, quote-feed logging, and the
INSERT race fix, plus the four new tests.

---

## Fix round 2 of 5

One remaining asymmetry: PATCH (fix round 1) rejected NaN **and** ±infinity for
its numeric columns; POST's NaN guard covered only NaN, not infinity.
`float("inf") <= 0` is `False`, so an infinite `qty` or `avg_price` sailed past
the positivity check on create and stored `inf` in the row, which then
propagates into `value`, `pnl`, and the portfolio totals on every subsequent list.

### Before

Reproduced against a throwaway temp-file database (never the real
`tradepilot_app.db`), sending the raw body directly since Python's stdlib
`json` module — which `flask.json`/Werkzeug's test client uses by default —
happily serialises a bare `Infinity` literal, matching how a real client could
send it over the wire:

```
data='{"symbol":"CIPLA","qty":Infinity,"avg_price":1000}', content_type="application/json"
```

```
BEFORE FIX -- POST qty=Infinity status: 201 body: {'avg_price': 1000.0, 'broker_ref': None,
'call_id': None, 'closed_at': None, 'exit_price': None, 'id': 'pos-28bfcea3e96e',
'last_price': None, 'opened_at': '2026-08-29T18:14:29', 'pnl': None, 'pnl_pct': None,
'price_unavailable': True, 'qty': inf, 'source': 'manual', 'symbol': 'CIPLA',
'user_id': 'demo-user', 'value': None}
```

`qty: inf` was genuinely stored and returned — confirmed the gap was real
before touching the code.

### Fix applied

Added a shared `_bad_number(value)` helper in `prototype/client_api.py`,
placed just before `position_create`:

```python
def _bad_number(value):
    """NaN and infinity both slip past a `<= 0` check.

    float("nan") <= 0 and float("inf") <= 0 are both False, so neither is
    caught by the positivity guard -- and either one propagates into value,
    pnl and the portfolio totals. PATCH rejects both; POST must agree.
    """
    return value != value or value in (float("inf"), float("-inf"))
```

- `position_create` now calls `_bad_number(qty) or _bad_number(avg_price)`
  in place of the round-1 NaN-only check (`qty != qty or avg_price != avg_price`),
  running before the existing `qty <= 0 or avg_price <= 0` guard, unchanged
  in placement.
- `position_update` (PATCH) now calls `_bad_number(value)` in place of the
  inline `value != value or value in (float("inf"), float("-inf"))` expression
  it already had from fix round 1 — the duplicated logic is deleted, both
  write paths now share one definition of "not a real number". PATCH's
  observable behaviour is unchanged; only its implementation was consolidated.

### After

```
AFTER FIX -- POST qty=Infinity status: 400 body: {'error': 'qty and avg_price must be real numbers'}
```

Same throwaway database, same request. 201 → 400.

### Normal create path, unbroken

```
Normal POST status: 201 body: {'avg_price': 1000.0, 'broker_ref': None, 'call_id': None,
'closed_at': None, 'exit_price': None, 'id': 'pos-d2ea453a4963', 'last_price': None,
'opened_at': '2026-08-29T18:15:39', 'pnl': None, 'pnl_pct': None, 'price_unavailable': True,
'qty': 10.0, 'source': 'manual', 'symbol': 'CIPLA', 'user_id': 'demo-user', 'value': None}
```

`POST {"symbol":"CIPLA","qty":10,"avg_price":1000}` still returns 201.

### New test

Added `test_both_write_paths_reject_the_same_unreal_numbers` to
`tests/test_client_api_positions.py`, exactly as specified in the fix
request. Used `json=` (the dict form), not the raw-body workaround — verified
directly that Flask's test client serialises a bare `float("inf")`/`float("nan")`
without error (`flask.json`/Werkzeug defers to Python's stdlib `json.dumps`,
which allows non-finite floats by default), so the workaround was not needed
for the test itself; the raw-body form was used only for the manual
before/after reproduction above, to mirror exactly how a real client sends the
literal over the wire.

### Verification

**1. Full suite:**
```
python3 -m pytest tests/ -q
```
```
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 74%]
........................................................................ [ 99%]
.                                                                        [100%]
289 passed in 4.77s
```
288 → 289 (+1, matching the one new test).

**2. Infinity status codes:** 201 before, 400 after (see reproductions above).

**3. Normal create path:** confirmed 201, unchanged (see above).

### Scope discipline

- `prototype/app.py`: untouched (`git diff` empty).
- `prototype/client_auth.py`: untouched (`git diff` empty).
- Only `prototype/client_api.py` (21 lines changed: +helper, both checks
  consolidated onto it) and `tests/test_client_api_positions.py`
  (+17 lines, one new test) changed in this round.
- Nothing under `.superpowers/` was `git add`ed.

### Commit

`a5da6f1` — shared `_bad_number` helper closing the infinity gap in
`position_create`, reused by `position_update` to delete the duplicated inline
check.
