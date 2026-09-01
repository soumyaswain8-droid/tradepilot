# Accounts: auth core (project B1)

Replaces the identity stub the client dashboard was built against. When this
lands, `client_auth.current_user()` stops returning a hardcoded `"demo-user"`
and starts returning whoever is actually signed in.

**Companion spec:** `docs/superpowers/specs/2026-08-28-client-dashboard-design.md`.
Its two "Deferred from" sections are binding constraints on this project, not
background reading.

## Why this exists

The client dashboard at `/app` ships five screens over eight endpoints, three
public and five gated. The gate works -- `install_guard` refuses a gated
endpoint when `current_user()` returns `None` -- but `current_user()` cannot
return `None` today. It returns a fixed string.

Three consequences, all live in the merged code:

- Every `signedOut` branch in `screens.js` and `main.js` is unreachable by
  construction. They were written, reviewed, and have never once rendered.
- `positions.user_id` is a real column with a real index carrying one fake
  value.
- The manual checklist's only way to see a signed-out screen is to edit
  `client_auth.py` and remember to revert it -- a documented instruction that
  tells a human to modify application code and put it back.

## What B1 is not

Self-serve signup, email verification and password reset are **project B2**.
They are excluded here because every one of them depends on outbound email,
and this repository has no mail path: no `smtplib` usage, no provider, no SMTP
credentials, nothing. The only outbound channel that exists is Telegram.

Splitting on that line means B1 is testable end to end the day it lands, with
accounts created from the terminal, while the mail question stays open. B2 adds
a signup route against the same `users` table; nothing here is rebuilt.

**B2 requires transactional mail. The provider is chosen at B2 planning, not
now.** Deciding it here would commit to a vendor before the verification flow
that uses it has been designed.

Also out of scope: per-user Kite tokens, a closed-positions view, the
`/classic` redirect.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Who gets an account | Self-serve, eventually | B1 creates them from a script; B2 opens the front door |
| Login | Email + password | Self-contained, no third party, works offline and in tests |
| Session transport | Server-side table, opaque token | Real revocation, and no `SECRET_KEY` to manage |
| Session lifetime | 30 days sliding, 90-day hard cap | Familiar behaviour; the cap stops immortal sessions |
| CSRF | `SameSite=Lax` + `Origin` check | The cookie is not sent cross-site; the check covers the residual |
| Sign-in UI | Server-rendered `/app/login` | Password managers work; credentials never touch the fetch layer |

### Why not `flask.session`

Flask's session is a signed cookie: the data lives in the browser and a
`SECRET_KEY` makes it tamper-evident. **This application has no `SECRET_KEY`
anywhere** -- verified across `prototype/`. Adopting signed cookies therefore
means introducing secret management, and it carries two properties that suit a
private book badly: logout cannot revoke anything (clearing the cookie is
advisory; a copied one works until it expires), and rotating the key signs
every client out simultaneously.

An opaque random token sidesteps all of it. The cookie carries 256 bits of
`secrets` output and nothing else; the truth is a row. Because the token is
unguessable it needs no signature, so there is no key to store, rotate, or
leak. Logout becomes `DELETE`. "Sign out everywhere" becomes one statement.

The cost is one indexed SQLite read per gated request, and rows that must be
expired or the table grows without bound.

### Why the Kite flow cannot be the login

`/kite/login` and `/kite/callback` already exist in `app.py`, and the
resemblance is a trap. That flow is the operator's daily ritual: it exchanges a
request token and writes a single global `KITE_ACCESS_TOKEN=` line into `.env`,
expiring each evening. One token, one dotfile, no user attached to it.

Client sign-in via Zerodha would be a genuinely separate per-user OAuth flow
storing per-user tokens, and it would require every client to hold a Zerodha
account. Neither follows from the code that is already there.

## Schema

Added to `app_store.py`'s `init_db`, in the same idempotent style as `calls`
and `positions`. Both tables live in `tradepilot_app.db`, which is gitignored.

```sql
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    disabled_at    TEXT,
    failed_count   INTEGER NOT NULL DEFAULT 0,
    locked_until   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email
    ON users (lower(email));

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_sessions_user
    ON sessions (user_id);
```

Email is unique case-insensitively -- `Priya@x.com` and `priya@x.com` are one
account. Storing the address as typed while indexing it lowered keeps the
display honest without allowing a duplicate.

`positions.user_id` is unchanged. It is `TEXT NOT NULL` with no foreign key,
which already accepts a real user id. **Both tables are empty today** (verified:
zero rows in `calls` and `positions`), so no migration of `"demo-user"` data is
required. A later project may add the foreign key; doing it now would constrain
a column no data occupies.

## Two hashes, chosen differently

**Passwords** use `werkzeug.security.generate_password_hash` /
`check_password_hash`. Werkzeug 3.1.3 is already a dependency, so this adds
nothing to `requirements.txt`. Use its default method rather than pinning one:
`check_password_hash` reads whatever format is stored, so werkzeug's default
can advance over time and existing hashes keep verifying. Pinning an algorithm
here would freeze a security parameter at today's value forever.

**Session tokens** are `secrets.token_urlsafe(32)`, stored as a plain
`hashlib.sha256` digest.

The asymmetry is deliberate. Slow hashing exists to make guessing expensive,
which matters only for secrets drawn from a space an attacker can enumerate --
that is, ones a human chose. A session token is 256 bits of CSPRNG output with
no dictionary behind it, so a slow KDF would buy nothing while charging its
cost on **every gated request**, where a password KDF is charged once per
login.

Hashing the token at all still matters: if the database leaks, the attacker
holds digests rather than working cookies.

## Files

| File | Change | Responsibility |
|---|---|---|
| `prototype/accounts.py` | new | users + sessions data access; pure functions over a connection |
| `prototype/accounts_web.py` | new | `GET`/`POST /app/login`, `POST /app/logout` |
| `prototype/templates/login.html` | new | Jinja form, no JavaScript |
| `prototype/client_auth.py` | rewritten | `current_user()` reads the cookie; guard gains the `Origin` check |
| `prototype/app.py` | ~5 lines | register the blueprint, scope CORS |
| `scripts/add-client.py` | new | create an account from the terminal (see below) |

`app.py` is already large; it gains registration lines only, the same footprint
the client API took. `/app` itself is defined at `app.py:102` and does not move.

`client_auth.py` keeps its `PUBLIC_ENDPOINTS` / `GATED_ENDPOINTS` registries
and the enumeration tests that assert every client endpoint appears in exactly
one of them. That structure is why auth here is one audited seam rather than a
per-route decorator hunt across roughly seventy routes, and it survives intact.

### Creating an account

```
$ python3 scripts/add-client.py priya@example.com
Password: (not echoed)
Confirm:  (not echoed)
created user u-8f21c4
```

The password is read with `getpass`, never taken as an argument. A password
passed on the command line lands in shell history and in the process list,
where any other user on the machine can read it.

The script refuses an email that already exists rather than overwriting the
password of a live account, and it is the only account-creation path in B1.

## Session and cookie behaviour

```
Set-Cookie: tp_session=<43 url-safe chars>
            HttpOnly; SameSite=Lax; Path=/; Secure (when the request is HTTPS)
```

`Secure` is conditional on `request.is_secure` so that local HTTP development
still works. Setting it unconditionally would make sign-in silently fail on
localhost -- the cookie is set, the browser discards it, and the only symptom
is a login that appears to succeed and lands you signed out.

`HttpOnly` is not optional: no client script has any reason to read this value,
and `api.js` never touches it. The browser attaches it automatically.

**Lifetime.** `expires_at` is pushed to `now + 30 days` on each authenticated
request; `created_at + 90 days` is an absolute ceiling that sliding cannot
cross. A session that has passed either bound is treated as absent.

**Expiry sweep.** Expired rows are deleted opportunistically on session
creation, not by a scheduled job. A cron for a table this size would be
machinery without a purpose.

**Logout** deletes the row and clears the cookie. Because the row is the
authority, a cookie copied before logout stops working immediately -- which is
the property signed cookies cannot offer.

## CSRF: `SameSite=Lax` plus an `Origin` check

A cross-site `POST`, `PATCH` or `DELETE` does not carry a `SameSite=Lax`
cookie, so the position endpoints are already unreachable from a hostile page.
The `Origin` check is the belt to that pair of braces: within the existing
`before_request` guard, an unsafe method aimed at a gated endpoint whose
`Origin` is not ours is refused with 403.

Roughly six lines, inside the guard that already knows which endpoints are
gated. No token, no second cookie, no header for `api.js` to attach.

`SameSite` is scoped by *site*, not origin, and what counts as a site is
determined by the Public Suffix List. The production host is a subdomain of a
shared deployment domain, so **confirm that domain's PSL status when
provisioning**; if it were not a public suffix, a sibling subdomain would count
as same-site and `Lax` alone would not separate them. The `Origin` check holds
in either case, which is a second reason to have it.

## CORS: scope it by deleting, not by configuring

`app.py:53` applies `CORS(app, origins=["http://localhost:*", ...])` to the
whole application, which now includes `/api/app/*`. `supports_credentials` is
unset and therefore `False`, so nothing is exploitable today. The hazard is the
obvious next step: B2 or a future change sets `supports_credentials=True` to
let the dashboard send cookies, and `http://localhost:*` becomes a credentialed
wildcard over a client's private book.

The fix is to notice that the question does not arise. `/app` and `/api/app/*`
are served from one origin, and a same-origin request never consults CORS.
Scope the existing rule to the legacy `/api/*` paths that have external
consumers, and leave `/api/app/*` outside it entirely: no headers, no wildcard,
and no `supports_credentials` decision available to get wrong later.

## Login flow

```
GET  /app/login   -> Jinja form (email, password, optional ?next=)
POST /app/login   -> verify -> create session -> Set-Cookie -> 302
POST /app/logout  -> delete session -> clear cookie -> 302 /app
```

**`?next=` is validated as a local path** before any redirect, and ignored
otherwise. An open redirect on a login page is a phishing primitive: the
attacker sends a link to the genuine site, the victim signs in for real, and
the redirect lands them on a copy that asks again.

**Failed attempts** increment `failed_count`. At **10 consecutive failures**
`locked_until` is set to **15 minutes** ahead, and login is refused while it
holds. A successful login resets both to their defaults.

Those two numbers are a trade-off, not a convention. Ten is high enough that a
person mistyping a password they genuinely know is not locked out, and low
enough that online guessing dies immediately. Fifteen minutes is short on
purpose: because the lock is keyed on the email address, anyone who knows a
client's address can trigger it deliberately, so the lock has to expire faster
than it is worth an attacker's time to maintain. A longer lock would trade a
guessing risk for a denial-of-service one.

This is deliberately minimal -- no new table, no IP tracking -- but an
unthrottled password endpoint on a public host is not acceptable, and the
column is cheaper than the incident.

**The response must not distinguish an unknown email from a wrong password.**
One message for both, or the login form becomes an account enumerator.

## Two dead things become live

The dashboard's final review recorded `#who` in `app.html` as an element that
is never populated, and `/api/app/me` as the one endpoint no screen consumes.
They are each other's answer.

`#who` shows the signed-in address and a sign-out control, or a link to
`/app/login` when signed out, fed by `me`. The screens' existing "Sign in to
see your book" text finally has somewhere to point.

And `docs/APP_MANUAL_CHECKS.md` gets shorter. Its signed-out procedure
currently instructs a human to edit `client_auth.py` and revert it afterwards,
with a bold warning about the five endpoints left exposed if they forget. That
entire section is replaced by clicking sign out. **Update that document as part
of this project** -- a checklist that still says to edit source will be followed
by someone who does not know it is obsolete.

## Testing

Follows the repository's existing rule that tests ship with the code that
introduces them, not in a later sprint.

**Data layer.** Create and fetch a user; reject a duplicate email differing
only in case; verify a correct password and reject a wrong one; refuse a
disabled account; create a session and look it up; reject an expired one;
confirm sliding renewal moves `expires_at`; confirm the 90-day cap is not
crossed by renewal; confirm logout removes the row.

**Guard.** A gated endpoint with no cookie returns 401; with a valid cookie
returns 200; with a tampered or unknown token returns 401; an unsafe method
carrying a foreign `Origin` returns 403. The existing enumeration tests -- every
client endpoint classified in exactly one registry -- must stay green.

**Login.** Wrong password is refused; the refusal message is identical for an
unknown email; lockout engages past the threshold and clears on success; a
`next=` pointing off-site is ignored; the `Set-Cookie` header carries
`HttpOnly` and `SameSite`.

**A test that cannot fail is worse than no test.** For each assertion that
guards a security property, break the property, watch the test go red, and
restore it. This branch's predecessor shipped seven tests satisfied by prose in
a comment rather than behaviour in the code; the pattern is not hypothetical.

## Global constraints

- Flask + Jinja; vanilla ES5 for anything client-side. No framework, no build
  step.
- No new dependencies. `werkzeug` (hashing) and `sqlite3`, `secrets`,
  `hashlib` (stdlib) cover everything here.
- SQLite through stdlib `sqlite3`, via `app_store.get_db()`. All DDL uses
  `IF NOT EXISTS`.
- The login page is server-rendered and contains no JavaScript.
- `fetch` stays confined to `prototype/static/app/api.js`.
- Port 5050 belongs to a separate running process. Use 5051 or above.

## Deploy gates

Unchanged and still binding: **the SEBI Research Analyst / Investment Adviser
position must be settled before `/app` is publicly reachable.** Publishing
buy and sell calls with a track record to people who are not you is the
regulated activity, and authentication does not alter that -- it only makes the
audience easier to grow.

## Open items carried forward

- **Mail provider for B2** -- deliberately undecided.
- **PSL status of the production deployment domain** -- confirm at provisioning;
  see the CSRF section.
- **A foreign key from `positions.user_id` to `users.id`** -- deferred while the
  table is empty and B2 may reshape account creation.
- **`record()` cannot distinguish an absent `callsFailed` from a false one** --
  carried from the dashboard spec. Unchanged by this project; revisit when a
  second caller appears.

## Deferred from the auth core

Recorded here because the execution workspace that held them is disposable.

### The login timing oracle

`check_login` returns early for an unknown email, a disabled account and a
locked one, so only an active account pays the password-hashing cost. Timing
therefore distinguishes "this address has a live account" from everything
else -- a wider signal than the unknown-vs-wrong-password trade-off the spec
already accepts.

Left as-is deliberately. The fix is to hash unconditionally, which turns the
login endpoint into a CPU amplifier: an attacker submits unknown addresses and
the server burns a KDF on each one. That trades a weak timing signal for a
real denial-of-service surface. B2's self-serve signup will reveal which
addresses are taken far more cheaply than timing ever could, so revisit the
question there rather than here.

### `safe_next` rejects every colon

A benign local target such as `/app?t=12:30` falls back to `/app`. This is
over-broad and fails safe. Narrowing it to catch only scheme-like colons is
exactly the cleverness that reopens the hole the function exists to close, so
the cost -- a lost query parameter in a redirect -- is accepted.

### The test-suite database net has one gap

`tests/conftest.py` repoints `app_store.DB_PATH` at a temporary file for the
whole run, so a fixture that forgets to patch one of the four `open_store`
seams cannot reach the real product database. Autouse fixtures run after
collection, though, so a `get_db()` call at a test module's import time would
still resolve the real path. No such call exists today. Anyone adding one
should not assume the net covers it.

### Deployment still owes two answers

**The Public Suffix List status of the production domain** decides whether
`SameSite=Lax` separates sibling subdomains on a shared deployment host. The
`Origin` check holds either way, which is a second reason it exists.

**Nothing here handles `X-Forwarded-*`, deliberately.** The `Origin` check
compares hosts rather than whole origins precisely so it works behind a
TLS-terminating proxy without trusting a spoofable header. If a future change
needs the scheme, scope the trust to a known proxy rather than reaching for
`ProxyFix` app-wide -- it would change all ~70 operator routes to repair one
comparison.

## Mail: what B2 inherits

Findings from a DNS survey on 2026-09-01. B1 sends no mail; all of this binds
B2, where signup verification and password reset first need it.

### Both candidate domains carry a DMARC policy with nothing behind it

`sidewall.in` and `eazipay.in` publish an identical record:

```
v=DMARC1; p=quarantine; adkim=r; aspf=r; rua=mailto:dmarc_rua@onsecureserver.net
```

Neither domain has any TXT record at all, so neither publishes SPF. No DKIM
was found at the common selectors -- selector names are arbitrary, so one may
exist under a name not guessed, but SPF's absence is definitive because SPF
has exactly one place to live.

DMARC passes only when SPF or DKIM passes *and* aligns with the From domain.
With neither published, both legs evaluate to "none", DMARC fails, and
`p=quarantine` instructs every enforcing receiver -- Gmail, Outlook, Yahoo --
to file the message as spam.

The `rua` address belongs to GoDaddy, which runs DNS for both domains. This
looks like a per-domain default that was applied without the SPF and DKIM
records that make it survivable, so **every other domain on that account is
worth checking too.**

### What each domain is

| | `sidewall.in` | `eazipay.in` |
|---|---|---|
| MX | `smtp.google.com` (Google Workspace) | none -- cannot receive mail |
| Sends today | yes, real business correspondence | nothing |
| A record | -- | `18.61.146.3`, an existing server |
| Reputation at stake | the founder's actual email | none |

**`sidewall.in` is probably being quarantined today.** Not a future problem
introduced by B2 -- a present one affecting ordinary mail, worth fixing on its
own merits regardless of what this project decides.

### The trade-off B2 has to settle

Sending from `sidewall.in` means Google Workspace SMTP (`smtp.gmail.com:587`,
stdlib `smtplib`, no new dependency, roughly 2,000 recipients/day) and an App
Password, which requires 2FA on the account and lives as a long-lived
credential in the deployment environment.

Its cost is reputation coupling. A public signup form attracts junk and
mistyped addresses; the resulting bounces and spam complaints attach to the
sending domain. Tying that to the domain carrying the founder's real
correspondence puts ordinary business email behind the behaviour of a
registration form.

`eazipay.in` inverts this. It has no correspondence to protect, which makes it
the better sending identity -- but it has no mailbox provider either, so it can
neither receive bounces nor accept replies to a verification email a user
answers. That gap has to be closed before it can be used, not after.

**Decided 2026-09-01: `sidewall.in` sends the mail.** Google Workspace SMTP,
stdlib `smtplib`, no new vendor and no new dependency. `eazipay.in` was the
better identity on reputation grounds but has no MX at all, so it can neither
receive bounces nor accept a reply to a verification email -- a gap that would
have to be closed before it could send, and closing it is more work than this
phase justifies.

The reputation coupling is accepted knowingly: a public signup form's bounces
and complaints will attach to the domain carrying the founder's real
correspondence. Revisit if signup volume grows enough for that to bite; a
`mail.sidewall.in` subdomain is the cheapest way out, because a subdomain's
sending reputation is separable from the apex.

**This does not unblock B2 yet.** `sidewall.in` publishes DMARC
`p=quarantine` with no SPF and no DKIM behind it, so it cannot deliver
authenticated mail today. Run `scripts/check-mail-dns.sh sidewall.in` -- it
exits non-zero until the two records are in place, and it is the gate B2's
first task should depend on.

### The order of operations, whichever domain wins

1. Publish SPF for the sending domain, and enable DKIM at the provider.
2. Confirm DMARC passes before writing any code that depends on delivery.
3. Give bounces somewhere to land -- an unmonitored bounce stream is how a
   sending reputation degrades without anyone noticing.
4. Only then build verification and reset, whose entire behaviour assumes a
   message actually arrives.

Skipping step 1 produces the worst failure mode this project can have: signup
appears to work, the code is correct, and every verification email silently
lands in spam.
