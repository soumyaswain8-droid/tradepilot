# Resume here — state as of 2026-09-01 evening

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
