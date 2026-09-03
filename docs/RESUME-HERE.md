# Resume here — updated 2026-09-04 early

## THE OTHER WEEKEND JOB — connect the client dashboard to the engine

The client product is finished and running. Accounts, sessions, sign-in, the waitlist
front door, invites and password reset all shipped and merged (447 pytest, 18 node).
What has never happened is a single call being published, so the dashboard's track
record is honestly empty.

**One defect was found and fixed tonight, and it matters for what comes next.**
`/api/picks` is not cached — it calls `score_stocks_v4()` and scores the whole universe
against live data on every request. Measured at **over 120 seconds**. `publish-calls.py`
had a 30-second timeout, chosen without measuring, so the 09:20 agent would have failed
every morning with an error reading like "the engine is down" — pointing at the healthy
component. Now 300s, overridable with `TP_PICKS_TIMEOUT` (commit `4e197d4`).

**Do this with the market open, not at night:**

1. Restart the long-running instance first — see the anomaly below.
2. `python3 scripts/publish-calls.py` around 09:20, and watch it. The field mapping is
   confirmed against live output: `direction` is `BUY`/`SELL`, and `target`/`stopLoss`
   are **percentages** under those exact names.
3. Read the dashboard. Calls, call detail and Track record should all populate.
4. Only if you are happy standing behind those calls, install the two agents:
   `deploy/launchd/co.tradepilot.{publish,resolve}-calls.plist`. Both carry a literal
   `/Users/YOURNAME` placeholder that must be replaced first. They are scheduled 09:20
   weekdays and have stayed uninstalled on purpose — they write to `calls`, which is the
   one table whose loss cannot be reconstructed.

### The "anomaly" — RESOLVED 2026-09-04, and it was not what this note guessed

This section originally described `/api/picks` answering in two minutes on a fresh
instance but not in ten on one that had been up all day, and guessed at "a cache that
has grown, a pool exhausted, a lock." **The cause was found the same night and it was
none of those.** The long-lived instance was holding a DEAD KITE TOKEN: Flask's
`app.run()` auto-loads `.env` into `os.environ` at startup, and `envcfg` reads environ
before the file, so the process served its boot-time token forever and every quote
timed out. Fixed with `load_dotenv=False` (commit `9592077`), verified by rotating the
token on disk with Flask running.

So: **restarting is no longer required, and the "capture state first" advice is moot.**
The `/api/_diag/creds` endpoint (loopback-only) shows the process's own token view if
this is ever in doubt again.

### Using the client app right now

A local instance of the merged code runs on **5051** (started 09-04, separate from the
5050 one, which is older code). Sign in at `http://127.0.0.1:5051/app/login` as
`soumya@sidewall.in`. The account was made with `scripts/add-client.py`, which needs no
email — the waitlist and reset flows do need `SMTP_USER`/`SMTP_PASS`, and nothing else
does.

`sidewall.in` now publishes SPF and a DKIM key at selector `google`;
`scripts/check-mail-dns.sh sidewall.in` exits 0. That also fixed ordinary business mail,
which had been quarantined because a GoDaddy default DMARC `p=quarantine` was published
with neither record behind it. **Every other domain on that account probably has the same
default** — `eazipay.in` did.

### Still the gate that governs all of it

**The SEBI Research Analyst / Investment Adviser question decides when `/app` can be
publicly reachable.** The front door was deliberately built so only you can open it:
approval is a terminal command, and nobody gets an account without one. Building the
machinery was never the decision. Publishing the link is.

Two deferred items in `docs/superpowers/specs/2026-09-03-accounts-signup-design.md` are
gated on the same answer — chiefly that `/app/forgot` reveals whether an address has an
account through response *timing*, which the identical response body cannot hide.

---

## THE WEEKEND JOB — Kite token automation, deferred deliberately

Everything is built and scheduled; only the credentials are missing. Deferred from
09-03 because completing it requires **re-enrolling TOTP in Kite**, and doing that late
at night before a trading day risks a lockout for no gain.

**Do this with time to spare, not before an open:**

1. kite.zerodha.com → profile → My profile → Settings → **Password & security**
2. **External TOTP** → Reset / Re-enable
3. Copy the **manual entry key / secret key** shown beside the QR — that is the seed. It
   is a long base32 string (16–32 chars, A–Z and 2–7), NOT the rotating 6-digit code.
4. **Re-scan the QR into your authenticator before leaving the page** — re-enrolling
   invalidates the old TOTP, and losing it locks you out of Kite login entirely.
5. In a real Terminal (getpass needs a TTY, so not through Claude):
   `cd ~/Documents/tinker/projects/tradepilot && python3 scripts/kite-setup-auto.py`
6. It prints a 6-digit code — confirm it matches your authenticator. If not, answer `n`;
   nothing is written.

A first attempt on 09-03 pasted the 6-digit code instead of the seed. The script caught
it and wrote nothing, which is exactly what that validation exists for.

**Until then the manual flow is fine.** The un-configured job exits at preflight without
alerting, so it makes no noise. The actual 09-03 failure was a rogue test writing dead
tokens into the live .env — that is fixed and rescheduled, so today's failure mode
cannot recur whether or not automation lands.

---

# Earlier state — as of 2026-09-01 evening

Paused mid-thread. This is what is running, what is waiting on you, and what the open
questions are. Everything below is committed and pushed (`dev` and `main` at `e80aece`).

---

## Waiting on you — one action unblocks a scheduled job

**Add three keys to `.env`**, then the daily token refresh can be scheduled:

```
KITE_USER_ID=...
KITE_PASSWORD=...
KITE_TOTP_SECRET=...        # the base32 seed from 2FA setup, NOT the 6-digit code
```

Verify with `python3 scripts/kite-auto-login.py --dry-run`. If the seed is lost, you have
to re-enrol 2FA in Kite to see it again.

This was previously declined on purpose. Storing the seed means anyone who can read
`.env` can log into the trading account — a compromised machine now reaches the account
by itself, which it could not before. The script's docstring records that trade-off in
full; it is a deliberate choice, not an oversight.

**Then:** schedule `scripts/kite-auto-login.py` at ~08:30 daily and drop the three
human-nag jobs it replaces.

---

## Running unattended right now

| What | State |
|---|---|
| Agent floor | **shadow**, `SWEEP_RECLAIM` only, `TARGET_R` 1.85, ₹3,000 × 8 = ₹24,000 |
| News collector | live, 14 feeds, every 15 min, **24/7 including overnight** |
| Disk watch | hourly, currently **WARN** |
| Telegram bot | now filtered on `chat_id`, fails closed |

**The floor takes no positions in shadow.** That is correct, not a regression — it is
accumulating toward `SHADOW_GATE` (150 trades, 8 days, net ≥ 0.05%/trade, t ≥ 2.0) under
the reworked geometry.

---

## Housekeeping worth doing when you return

**Docker is holding 8.9 GB.** Disk is at 5.8 GB free / WARN. The earlier prune reclaimed
build cache but `Docker.raw` does not shrink without quitting and relaunching Docker.
That single action is the largest reclaim available and should return you to OK.

---

## Open questions, in the order I would take them

1. **Did the overnight news watch work?** Open the terminal's News tab, filter
   **Overnight**, or run `python3 scripts/news-watch.py --stats` and read the
   "collected while India slept" line. If it is still 0 after a night, the 15-minute job
   is not firing overnight and that is the first thing to fix — the whole global-feed
   argument rests on it.

2. **Is the reworked floor geometry any better?** It needs 8 sessions of shadow before
   the gate can even be evaluated. Do not judge it early; the 31 Aug lesson was that
   n=120 settles a question that n=5 cannot.

3. **The news test itself is not designed yet.** Pre-register what would count as a real
   effect BEFORE looking at the ledger. Given how many lanes here have died to post-hoc
   thresholds, writing that down while there is no data is the cheapest insurance
   available.

---

## Cloud migration — researched, deferred

Three documents in `docs/research/cloud/`. Deferred for constraints, not for lack of a
plan. The findings that will still matter whenever it resumes:

- **Oracle Cloud Mumbai Always Free** is the recommendation (₹0), fallback AWS Lightsail
  Mumbai $10/mo. A ₹24,000 book earns ~₹720/mo, so a ₹1,584/mo VM is a 79% drag on
  notional — the free tier is not thrift, it is the only proportionate choice.
- **Region barely matters.** Kite's own WebSocket latency is 700 ms–1 s and Zerodha state
  it "is not meant for HFT". Mumbai wins on jitter, not speed.
- **Oracle's idle-reclaim rule fires on exactly this workload** (CPU, network AND memory
  all under 20% for 7 days). Provision the *smaller* shape deliberately so normal usage
  clears the threshold.
- **The floor's `flock` is per-host.** Two machines each acquire it cleanly and both
  stream, and the tick-counter detector is blind to it because they write different log
  files. The floor is a hard cutover, never parallel.

---

## Known bugs, unfixed and recorded

- **`us-paper-trade` fires at 19:00 IST**, which is 09:30 ET *only under EDT*. Under EST
  it runs an hour before the US open. A fixed IST wall-clock cannot track a DST market.
- **Two scripts still execute from outside the repo**
  (`~/Library/Application Support/tradepilot/`). Recovered into `scripts/orphaned/` as
  backups, but the running copies are still the off-repo ones. The real fix is moving
  them into `scripts/` and repointing the three plists.
- **`/kite/callback` (app.py:3616)** is an unauthenticated GET that writes a credential
  into `.env`. Harmless bound to loopback; disqualifying if the dashboard is ever
  exposed. Gate any exposure on fixing it.
- **`/api/paper/reset` (app.py:2629)** wipes positions and history with no auth or
  confirmation.

---

## What the research programme concluded

Worth re-reading before starting anything new, because it closes a lot of doors:
`docs/research/overnight/OVERNIGHT-REPORT.md`.

Ten lanes, all negative. The precursors predict **magnitude, not direction** — the same
model finds tomorrow's top-50 winners at 4.87× and its losers at 6.28×. The positional
lane failed on both its rationales (`docs/research/positional/`). Every price-derived
idea from the original search is now tested and closed.

**News is the one input class never tried**, which is why the collector exists and why it
only observes. It is also the only plausible entry signal for a multi-week hold — a real
catalyst has a mechanism for persisting that "the stock rose 5% yesterday" does not.
