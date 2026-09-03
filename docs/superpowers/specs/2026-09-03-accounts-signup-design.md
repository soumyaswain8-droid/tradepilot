# Accounts: the front door (project B2)

Adds the public way in. B1 built accounts, sessions and sign-in, but the only
way to create an account is the operator running `scripts/add-client.py`. This
project adds a waitlist anyone can join, a CLI to approve from it, the invite
that turns an approval into an account, and password reset.

**Companion spec:** `docs/superpowers/specs/2026-08-31-accounts-auth-core-design.md`.
Its decisions bind this project — read its "Deferred from the auth core" and
"Mail: what B2 inherits" sections before implementing.

## Why this exists

`add-client.py` requires a terminal, the repository, and the operator. That is
correct for a phase with a handful of hand-picked clients and wrong for
anything else: there is no way for an interested person to register interest,
and no way for an existing client who forgets their password to recover
without the operator editing the database by hand.

## The shape, and why it is smaller than it looks

The obvious build is signup, then email verification, then separately a
password reset. A waitlist collapses the first two and shares machinery with
the third.

Nobody gets an account by signing up. They get a row on a list. When the
operator approves that row, the system emails a one-time link, and **clicking
that link is simultaneously the proof they control the address and the moment
they choose their password.** There is no separate confirmation step because
confirmation and credential arrive together.

That also makes "an unverified account can do nothing" true by construction
rather than by enforcement. No `verified_at` column, no check inside
`check_login`, no half-live account to reason about — until the link is
clicked there is no account at all.

Password reset is the same mechanism pointed at an existing user: a
single-use, time-limited, emailed link ending at a set-a-password form. Two
features, one token table, one page.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Who can register | Anyone joins a waitlist; the operator approves | Keeps the audience chosen while the regulatory question is open |
| Approval surface | `scripts/waitlist.py` | Matches `add-client.py`; no web surface to secure, no `is_admin` to invent |
| Unverified access | None — no account exists until the link is used | Falls out of the design rather than being enforced |
| Abuse defence | None for this phase | The list is private and approval is manual, so junk costs the operator scrolling, not exposure |
| From address | `soumya@sidewall.in` | Already exists, already authenticates, and replies reach a human |
| Invite lifetime | 72 hours, then back to pending | The operator re-approves; there is no self-service path in |
| Reset lifetime | 1 hour | A reset link is a live account-takeover credential; an invite link only creates an account that does not exist yet |

## Schema

Added to `app_store.py`'s `SCHEMA`, same idempotent style as the rest.

```sql
CREATE TABLE IF NOT EXISTS waitlist (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    requested_at  TEXT NOT NULL,
    approved_at   TEXT,
    user_id       TEXT REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_waitlist_pending
    ON waitlist (approved_at, requested_at);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash  TEXT PRIMARY KEY,
    purpose     TEXT NOT NULL,
    email       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT
);

CREATE INDEX IF NOT EXISTS ix_auth_tokens_email
    ON auth_tokens (email, purpose);
```

`purpose` is `'invite'` or `'reset'`.

The `waitlist` row is deliberately not deleted when an account is created;
`user_id` links it, so the list remains a record of where each client came
from. Note there is **no unique index on `waitlist.email`** — the abuse
decision was to accept duplicates, and a person submitting twice simply
appears twice.

## Tokens

The link carries `secrets.token_urlsafe(32)`; the database stores its SHA-256,
through the same `accounts._hash_token` that sessions use. A leaked table
yields digests, not working links. That helper is currently private by
underscore; B2 may use it as-is or promote it, but must not reimplement the
hashing — two implementations of one transformation is how they drift.

### Consuming a token is one statement, not two

The natural implementation reads the row, checks `used_at IS NULL`, and then
updates. Two nearly simultaneous requests can both pass the check before
either writes, and a single-use link gets used twice. This is not exotic:
double-clicks happen, and several mail clients prefetch links to scan them.

The check and the claim must be the same statement:

```sql
UPDATE auth_tokens SET used_at = ?
WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?
```

Zero rows affected means the token was already used, expired, or never
existed — all of which are refused identically. A separate `SELECT` afterwards
may fetch the email, but it must not be what decides validity.

## Mail

`prototype/mailer.py`. Stdlib `smtplib` over `smtp.gmail.com:587` with
STARTTLS, credentials from `SMTP_USER` and `SMTP_PASS`, no Flask import.

The module takes a transport function so tests inject a recorder and never
open a socket; the default transport is the real SMTP send. Testing mail by
mocking `smtplib` internals couples the tests to the standard library's shape;
injecting the seam keeps them about the message.

**Sending with no credentials configured raises.** A mailer that silently
no-ops when unconfigured is how a deployment discovers, weeks later, that no
invite ever arrived and nothing anywhere recorded a failure.

DNS is ready: `sidewall.in` publishes SPF and a DKIM key at selector `google`,
and `scripts/check-mail-dns.sh sidewall.in` exits 0. **B2's first task should
verify that still holds** — the mail path is worthless if the domain stops
authenticating, and the failure is invisible from inside the app.

## Two functions `accounts.py` does not yet have

B1 can create a user and check a password. It cannot **change** one — nothing
in `accounts.py` ever updates `password_hash` — so reset needs a new function.
It also cannot revoke a user's sessions, which reset needs for a reason worth
stating.

```python
def set_password(conn, user_id, password)      # updates password_hash
def revoke_all_sessions(conn, user_id)         # deletes that user's sessions
```

### A completed reset must end every existing session

Someone resets a password for one of two reasons: they forgot it, or they
believe the account is compromised. In the second case, leaving existing
sessions alive defeats the entire exercise — the attacker's cookie keeps
working for up to ninety days while the victim believes they have locked the
door. Sessions are server-side rows precisely so this is one `DELETE`.

`POST /app/set-password` on a `reset` token therefore does three things in
order: set the new password, revoke every session for that user, then create a
fresh session for the browser completing the reset. The order matters — revoke
before issuing, or the new session is deleted along with the old ones and the
user is bounced to the login page immediately after a successful reset.

This also closes a gap B1's final review recorded as unachievable: with
`revoke_all_sessions` in place, disabling an account can be made to take
effect immediately rather than waiting out the sessions already issued.

An `invite` token skips both — there is no prior password and no prior
session, because there was no account.

## Routes

All four are added by a blueprint in `prototype/accounts_web.py`, beside the
existing login and logout.

| Route | Behaviour |
|---|---|
| `GET /app/signup` | The form: one email field |
| `POST /app/signup` | Insert a `waitlist` row; always the same response |
| `GET /app/forgot` | The form: one email field |
| `POST /app/forgot` | If the address has an account, issue a `reset` token and mail it; always the same response |
| `GET /app/set-password` | Validate `?t=`, render the form, or say the link is no longer valid |
| `POST /app/set-password` | Consume the token; create the user (invite) or change the password (reset); sign them in |

`set-password` serves both purposes because they end identically — someone
proving control of an address and choosing a password. Only whether a `users`
row already exists differs, and `purpose` records which case it is.

### Every POST carries the Origin check

`client_auth.foreign_origin()`, exactly as login and logout do. B1's final
review found login CSRF because `accounts_web`'s routes sit outside the gated
registries and the guard returns early for anything not in them. These three
new POSTs have the same shape and the same exposure, and `SameSite=Lax` does
not defend a form that requires no cookie.

### Both address-taking forms answer identically, always

An unknown address, one already waitlisted, and one that already has an
account all produce the same page. Anything else turns either form into an
account enumerator, which is the rule `check_login` already follows.

For `/app/signup` this means a person who already has an account and forgets
lands on the waitlist rather than being told so. That is accepted: the
operator sees the duplicate at approval time, where `waitlist.py approve`
refuses an address that already has a user.

## The approval CLI

```
$ python3 scripts/waitlist.py list
  3 waiting
  priya@example.com     2 Sep
  rahul@example.com     2 Sep

$ python3 scripts/waitlist.py approve priya@example.com
  invite sent, expires in 72h
```

`approve` **sends the mail before marking the row approved**, and exits
non-zero having changed nothing if the send fails. The other order leaves a
row marked approved with no invite in existence and no signal that anything
went wrong — the operator would see a satisfied list and the client would see
silence.

`approve` refuses an address that already has a user, and refuses one not on
the list.

Follows `add-client.py`'s structure: `main(argv, ...) -> int` with distinct
exit codes, its own `open_store()` seam, and injectable side effects so tests
never send mail or touch a terminal.

## Failure handling

**`/app/forgot` cannot tell the user that mail failed** without revealing
whether the address has an account. It logs server-side and shows the same
message regardless. This is a deliberate asymmetry: the operator can see the
failure, the visitor cannot.

**An expired or already-used link** renders a page saying the link is no
longer valid, with no way to request another — re-approval is the operator's,
which is what makes the waitlist a gate. That page must not reveal whether the
token ever existed.

## Testing

Tests ship with the code that introduces them.

**Tokens.** Issue and consume; consuming twice fails the second time; an
expired token fails; a token for the wrong purpose fails; the stored value is
a SHA-256 of the emitted token and never the token itself. **Prove single-use
under concurrency** — call consume twice in a row and assert exactly one
succeeds, then break the atomic UPDATE into a read-then-write and confirm the
test goes red.

**Mail.** The transport receives a message addressed to the right recipient
containing the right link; sending with credentials unset raises; nothing in
the suite opens a socket.

**Routes.** Signup inserts a row and returns the standard response; the
response for an unknown address is byte-identical to one that already has an
account; a foreign `Origin` on each POST is refused; set-password creates a
user and signs them in; a reset changes the password and the old one stops
working; an expired link refuses without saying whether it existed.

**Reset revokes.** Create two sessions for a user, complete a reset, and
confirm the *older* token no longer resolves while the browser that completed
the reset is signed in. Assert on re-presenting the old raw token explicitly —
a test that merely re-requests proves nothing, because the client's cookie jar
has already moved on. B1 shipped exactly that vacuous test and it passed with
revocation stubbed out.

**CLI.** `list` shows pending only; `approve` sends then marks; a failing
send leaves the row untouched and exits non-zero; approving an address with an
existing account is refused.

**A test that cannot fail is worse than no test.** For each assertion guarding
a security property, break the property, watch it go red, restore it. The two
predecessor projects shipped nine such tests between them; the pattern is not
hypothetical.

## Global constraints

- No new dependencies. `smtplib`, `secrets`, `hashlib`, `sqlite3` are stdlib;
  `werkzeug` is already present.
- All DDL uses `IF NOT EXISTS`.
- Server-rendered Jinja, no JavaScript on any of these pages.
- `fetch` stays confined to `prototype/static/app/api.js`.
- Never store a raw token — session, invite or reset.
- Both address-taking forms answer identically regardless of what is known.
- Port 5050 belongs to a separate process; use 5051 or above.

## Out of scope

No admin web surface and no `is_admin` concept. No rate limiting. No decline
state — ignoring a waitlist row is declining it. No email change, no account
deletion, no "resend my invite". Per-user Kite tokens and the closed-positions
view remain later work.

## Deploy gate

**The SEBI Research Analyst / Investment Adviser question still gates linking
the signup form where the public can find it.** This project can be built,
tested and merged without settling it: the machinery is inert until the form
is reachable and the operator approves someone. Building it is not the
decision; publishing the link is.

## Deferred from the front door

Recorded here because the execution workspace that held them is disposable.

### `/app/forgot` leaks account existence through timing

The identical response body is real, but a known address does a `SELECT`, an
`INSERT` and a **synchronous SMTP round-trip**, while an unknown one does a
single indexed `SELECT`. Seconds against sub-milliseconds, separable over a
network by anyone willing to average a few samples. Every test on this route
compares status and content, so nothing in the suite can see it.

The honest fix is to stop sending inline, which means a background execution
model this codebase does not have: a thread whose failures are invisible
without its own logger, a daemon thread that can lose a reset email on process
exit, and a second injectable seam purely to keep the tests deterministic.
That is a design change, not a bug fix.

**This is a deploy gate.** It costs nothing while the signup form is
unreachable, and it is a live enumeration oracle the moment the form is
linked. `/app/login` has the same shape for the same reason — werkzeug's slow
KDF runs only when the row exists — so whatever answer is chosen should cover
both.

### The mail net does not fail loudly on one route

`tests/conftest.py` makes the real SMTP transport raise, so no test can send
mail. On `/app/forgot` that raise is swallowed: `AssertionError` is an
`Exception` subclass and `send_mail` sits inside that route's broad handler,
so a test which forgot its `sent` fixture gets a quiet 200 instead of a
failure. No mail is sent either way — the net's purpose holds — but the
mistake is invisible there. Raising something derived from `BaseException`
would fix it in one line.

### Smaller things, all correct today

- `peek_token` and `consume_token` each spell their own liveness predicate.
  They agree; nothing keeps them in step.
- `except ValueError` around `create_user` is scoped to the right statement
  but not the right meaning. If `create_user` ever grew input validation, a
  real validation failure would render as "that link is no longer valid".
- `auth_tokens` has no expiry sweep, unlike `sessions`. Spent and expired rows
  accumulate. They are inert — a raw token's value exists only in the request
  that carried it and is never logged.
- `TRADEPILOT_URL` is read at import time in the CLI and per-request in the
  web layer. Same value, two call sites.

### Still the gate that matters

**The SEBI Research Analyst / Investment Adviser question governs linking the
signup form where the public can find it.** This project deliberately ships a
front door that only the operator can open: approval is a terminal command,
and nobody gets an account without it. Building the machinery was never the
decision. Publishing the link is.
