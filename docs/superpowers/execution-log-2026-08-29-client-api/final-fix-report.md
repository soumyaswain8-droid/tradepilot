# Final fix wave -- client API layer

Branch `feat/client-api`, merge-base `717a7d7`. All five items from the final
whole-branch review applied in one pass, committed once.

## FIX 1 -- `opened_at` unvalidated, 500s on non-string input

`prototype/client_api.py`, `position_create`: added a validation block
(mirroring PATCH's `elif value is not None and not isinstance(value, str)`
predicate) before `open_store()` is called, and switched the INSERT to use
the validated local `opened_at` instead of re-reading `body.get("opened_at")`.

Test added: `test_create_rejects_a_non_string_opened_at` in
`tests/test_client_api_positions.py`.

### Manual verification against a throwaway database

```
$ python3 - <<'EOF'
... (see command in session; creates a tmp sqlite db, points open_store/fetch_quotes
     at it, boots prototype.app, and POSTs three payloads)
EOF
[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)
[ENGINE] v3 regime-aware engine loaded
[ENGINE] v4 composite scorer loaded
dict opened_at -> 400 {'error': 'opened_at must be a string'}
list opened_at -> 400 {'error': 'opened_at must be a string'}
normal create -> 201 {'avg_price': 1000.0, 'broker_ref': None, 'call_id': None,
  'closed_at': None, 'exit_price': None, 'id': 'pos-28e8c3535f59',
  'last_price': None, 'opened_at': '2026-08-29T18:34:31', 'pnl': None,
  'pnl_pct': None, 'price_unavailable': True, 'qty': 10.0, 'source': 'manual',
  'symbol': 'CIPLA', 'user_id': 'demo-user', 'value': None}
```

dict -> 400, list -> 400, normal create -> 201. Matches the required behaviour.

## FIX 2 -- deferred items persisted to the spec

Appended a `## Deferred from the API layer` section to
`docs/superpowers/specs/2026-08-28-client-dashboard-design.md` (after the
existing `## Deferred` section, at end of file -- that section's own content
was not touched). Covers: the closed-position one-way-door constraint on the
Book screen, `since` vs `resolved` honesty for the Track Record screen,
mark-to-market using `kite_data.get_quotes` not `/api/scores`, and CORS being
app-wide and unscoped for `/api/app/*` (documented only, not changed).

Also corrected the reused-endpoints prose line that named `/api/scores` for
mark-to-market -- now names `kite_data.get_quotes` and explains why
`/api/scores` cannot serve this (empty list on a cold cache, by design).

## FIX 3 -- cross-user isolation only tested on GET

Added to `tests/test_client_api_positions.py`:
- `test_another_user_cannot_patch_your_position` -- a real position id
  belonging to `demo-user`, PATCHed as `someone-else`, expects 404.
- `test_another_user_cannot_delete_your_position` -- same id, DELETEd as
  `someone-else` (expects 404), then confirms the position still exists when
  read back as its real owner (proves the row survived, not just that the
  foreign caller was rejected).

## FIX 4 -- schema DDL ran on every request, including anonymous public ones

`prototype/client_api.py`: `open_store()` no longer calls `app_store.init_db`.
It is now a one-line `return app_store.get_db()`, with a docstring explaining
why (schema execution belongs at boot, not on every request, least of all
public anonymous ones, against the one unrecoverable database).

`prototype/app.py`: added `app_store.init_db(app_store.get_db())` before
`app.register_blueprint(_client_api_bp)`, combined with the `app_store` import
on one new line (`from prototype import app_store; app_store.init_db(...)`) so
the diff against merge-base is a pure insertion -- no existing line touched,
keeping `git diff --numstat` at 0 removed.

Test fixtures (`tests/test_client_api_positions.py`, `test_client_api_calls.py`,
`test_client_api_record.py`) already call `app_store.init_db(conn)` themselves
in their `store` fixture and monkeypatch `open_store` to a bare
`app_store.get_db(path)` -- unaffected by this change, confirmed by the full
suite passing.

Confirmed schema exists after fresh boot (see command output below).

## FIX 5 -- unscoped post-UPDATE read

`prototype/client_api.py`, `position_update`: the re-read after a successful
scoped UPDATE now also filters `WHERE id = ? AND user_id = ?`, matching the
UPDATE's own scope, so its safety no longer depends on inference from the
preceding rowcount check.

## Verification

### 1. Full test suite

```
$ python3 -m pytest tests/ -q
........................................................................ [ 24%]
........................................................................ [ 49%]
........................................................................ [ 73%]
........................................................................ [ 98%]
....                                                                     [100%]
292 passed in 4.92s
```

289 baseline + 3 new (`test_create_rejects_a_non_string_opened_at`,
`test_another_user_cannot_patch_your_position`,
`test_another_user_cannot_delete_your_position`) = 292. No drop, no forcing.

### 2. `opened_at` manual check

See FIX 1 above -- dict: 400, list: 400, normal: 201.

### 3. `app.py` numstat against merge-base

```
$ git diff --numstat 717a7d7 -- prototype/app.py
5	0	prototype/app.py
```

5 added, 0 removed, as required.

### 4. Schema exists after fresh boot

```
$ python3 - <<'EOF'
import os, sys
sys.path.insert(0, os.getcwd())
from prototype import app_store
import prototype.app  # fresh boot import
conn = app_store.get_db()
rows = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('calls','positions')"
).fetchall()
print("tables found:", sorted(r[0] for r in rows))
conn.close()
EOF
[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)
[ENGINE] v3 regime-aware engine loaded
[ENGINE] v4 composite scorer loaded
tables found: ['calls', 'positions']
```

Both tables exist after importing `prototype.app` fresh, before any request
is served.

## What was NOT changed

- `shape_position` rounding stayed `round()` (banker's rounding) -- not
  switched to half-up. `_rate()` in `record()` (hit rate) is the one that
  needs half-up, per the earlier ruling; `value`/`pnl` come from float
  multiplication where exact ties are rare.
- No closed-positions retrieval endpoint was added. The one-way-door problem
  it would solve is recorded as a constraint on the next (screens) plan
  instead, per FIX 2.
- CORS configuration in `prototype/app.py` is unchanged
  (`CORS(app, origins=[...])`, `supports_credentials` unset/`False`). Only
  documented as a forward-looking risk in the spec's Deferred section.
- The existing `## Deferred` section in the spec (Kite broker sync, landing
  page relighting, delayed public calls, notifications) was left untouched;
  the new material was appended as a separate `## Deferred from the API
  layer` section.
- No subagents were dispatched; everything ran in the foreground.
- Nothing under `.superpowers/` was staged or committed (it is gitignored;
  this report lives there for reference only).
