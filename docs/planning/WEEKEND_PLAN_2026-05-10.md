# Weekend Plan — Cloud Migration Phase 1
**Dates:** 2026-05-10 (Sat) and 2026-05-11 (Sun)
**Goal:** Move TradePilot Flask dashboard to Render free tier. Laptop continues running engines. Validate cloud setup before Phase 2.

---

## Why this weekend

Owner travels frequently. Laptop in backpack with lid closed during market hours is fundamentally fragile. Five distinct laptop-environment bugs in past 2 weeks (cache poisoning, NaN guard, TCC block, caffeinate gap, regex misses) all share one root cause: this software was never designed to run on a personal laptop in someone's backpack.

Cloud is not an upgrade — it's the only architecture that addresses the actual constraints (stay-awake-in-backpack, battery, thermal, network, SEBI static-IP requirement for real-money trading).

Full research + decision rationale: `docs/research/2026-05-08_cloud_migration_master.pdf`

## Scope this weekend (Phase 1 only)

**IN scope:**
- Render free tier account
- Flask dashboard deploy
- Public URL with HTTPS (something.onrender.com)
- Parallel run: cloud dashboard alongside laptop engines
- Verification gates (6 must-pass items)

**OUT of scope (defer to Phase 2/3):**
- Engines on cloud (still on laptop)
- Real money / Kite Connect (paper only)
- Static IP / SEBI compliance (Phase 2 with AWS Lightsail)
- JWT auth, rate limiting, audit logs (Phase 3)
- Custom domain (optional, can wait)

---

## Friday 2026-05-09 — Pre-flight (~2 hrs)

| Time | Task |
|:--|:--|
| Evening | Render account · sign up · add payment method (free tier still requires it) |
| Evening | Connect GitHub repo to Render · grant access to `soumyaswain8-droid/tradepilot` |
| Evening | Review existing `render.yaml` and `Dockerfile` · note any laptop-specific paths |
| Evening | Backup current state: `git push origin main` + verify `~/Desktop/TradePilot/` archive is current |
| Evening | Read the master PDF end-to-end (15 min) · confirm phase order makes sense |

**Pre-flight gate (all must be TRUE Friday EOD):**
- [ ] Render account works · can see dashboard at render.com
- [ ] GitHub repo connected
- [ ] Local `docker build .` succeeds (test the Dockerfile actually builds)
- [ ] Latest commit (`79b60fc` or newer) pushed to origin
- [ ] You slept >6 hours · stable internet · Saturday morning is free

If any item is FALSE, postpone Phase 1 to next weekend (2026-05-17/18).

---

## Saturday 2026-05-10 — Phase 1 deploy

| Time IST | Task | Effort | Verifies |
|:--|:--|:--|:--|
| 09:00 | Pre-flight gate review (above) | 15 min | Ready to proceed |
| 09:15 | Render: New Web Service · pick repo · `python prototype/app.py` start command | 30 min | Service created |
| 09:45 | Add env vars in Render dashboard (anything from `.env`, sanitised) | 15 min | Config ready |
| 10:00 | Trigger first deploy · watch build logs | 15 min | Build succeeds |
| 10:15 | Hit the .onrender.com URL · confirm dashboard renders | 15 min | HTTP 200 |
| 10:30 | Compare cloud `/api/engine-status` vs laptop's | 30 min | Data parity |
| 11:00 | Take screenshots from phone — verify mobile-accessible | 15 min | Phone access |
| 11:15 | Set up Telegram bot token in Render env (if dashboard pulls from Telegram) | 30 min | No secrets in code |
| 11:45 | Watch parallel run during market hours · don't change anything else | Watch only | Stability over time |
| 15:30 | Market closes · spot-check cloud rendered same EOD numbers as laptop | 30 min | EOD parity |
| 16:30 | Stop work · take a break · don't touch anything until Sunday | — | Mental space |

**Cutover gates — Saturday must pass all 6 before declaring Phase 1 success:**
1. [ ] Cloud dashboard returns HTTP 200 from any device on any network
2. [ ] HTTPS certificate valid (browser shows lock icon, no warnings)
3. [ ] `/api/engine-status` data matches laptop's data within 60 seconds
4. [ ] Logs visible in Render dashboard
5. [ ] Zero 500 errors in first 6 hours
6. [ ] You can interpret cloud logs without help

If 1-2 fail: deploy didn't work. Investigate, retry, or postpone.
If 3-6 fail: deploy works but something's off. Diagnose Sunday.

---

## Sunday 2026-05-11 — Validate + decide

| Time IST | Task | Effort |
|:--|:--|:--|
| 09:00 | Read Saturday's cloud logs · scan for errors | 30 min |
| 09:30 | Run cloud dashboard read-only all day · pretend you're on the road | Watch |
| 10:00 | Send yourself a Telegram message: "Cloud at .onrender.com — Phase 1 day 2" | 5 min |
| 14:00 | Decision time: go/no-go for Phase 2 next weekend | 15 min |
| 14:15 | Document any issues found · save to `docs/planning/WEEKEND_PLAN_2026-05-10.md` (this file) | 30 min |
| 15:00 | If go: book Saturday 2026-05-17 09:00 in calendar for Phase 2 | 5 min |
| 15:15 | Sync updated Desktop archive: re-run snapshot to capture cloud config | 15 min |

**Decision matrix:**

| Saturday outcome | Sunday verdict | Next step |
|:--|:--|:--|
| All 6 gates passed | All quiet, no errors | Schedule Phase 2 for 2026-05-17 |
| 4-5 gates passed | Minor issues identified | Fix, re-test, then Phase 2 next weekend |
| <4 gates passed | Real problems | Roll back, reassess. Maybe skip Render and go directly to AWS Lightsail Phase 2 only |

---

## Rollback runbook (if anything breaks Monday morning)

| Step | Action | Time |
|:--|:--|:--|
| 1 | Render dashboard → Service settings → Suspend | 30 sec |
| 2 | Confirm laptop engines still running: `./scripts/launch-market.sh --status` | 30 sec |
| 3 | If laptop is also down: `./scripts/launch-market.sh` | 1 min |
| 4 | Send Telegram: "Cloud rolled back, laptop primary" | 30 sec |
| 5 | Investigate cloud issue without time pressure | Async |

**Total rollback: <10 minutes** to back to laptop-only operation.

---

## Skills to learn before Saturday (~2 hrs Friday evening)

1. **Docker basics** — `docker build`, `docker run`, `docker ps`, `docker logs <name>`
2. **Reading Render logs** — Dashboard → Service → Logs tab · understand startup vs runtime logs
3. **HTTPS basics** — what's the lock icon, what does "TLS handshake failed" mean
4. **Common deploy errors** — port already in use, missing env var, wrong Python version

---

## What changes after Phase 1 succeeds

| Before | After |
|:--|:--|
| Dashboard only on `localhost:5050` (laptop) | Dashboard on `tradepilot.onrender.com` (anywhere) |
| Can't view dashboard while traveling | Phone-accessible from any network |
| Cache poisoning risk: high (overnight Flask restarts) | Cache poisoning risk: medium (Render scheduled deploys still hit endpoints) |
| Engine truth: laptop only | Engine truth: still laptop only (engines stay there until Phase 2) |
| Monthly cost | ₹0 (Render free tier) |

## What does NOT change after Phase 1

- Engines still run on laptop
- yfinance still polled from laptop IP
- All trades still placed by laptop processes
- Real money still not in scope (paper trading only)
- SEBI compliance still pending (Phase 3)

---

## Phase 2 preview (next weekend, 2026-05-17/18)

**Trigger:** Phase 1 succeeded · all 6 gates passed · ready to graduate from PaaS to a real VM.

**Goal:** Move 7 engines + Rust to AWS Lightsail Mumbai 3GB. Static IP attached. Laptop becomes failover backup.

**Cost:** ₹1,650/month (₹825 for half-month May).

**Effort:** 8-12 hours over Saturday + Sunday.

Don't think about Phase 2 details until Phase 1 is signed off Sunday afternoon. Focus discipline.

---

## Phase 3 preview (week of 2026-05-25)

**Trigger:** Phase 2 succeeded · Lightsail running 7 engines for a full week · static IP whitelist requested.

**Goal:** Apply for Kite Connect production app · add JWT auth + Doppler secrets + Cloudflare · 5-day shadow trading · flip to real money 2026-06-08.

**Cost:** +₹2,000/mo Kite + ~₹500/mo Cloudflare/Doppler.

This is the only phase with real-money risk. All gates from Phases 1-2 must hold before any real capital deploys.

---

## References

- Master PDF (decision-ready): `docs/research/2026-05-08_cloud_migration_master.pdf`
- Master HTML (editable source): `docs/research/2026-05-08_cloud_migration_master.html`
- Provider research: `docs/research/2026-05-08_cloud_providers.md`
- Architecture research: `docs/research/2026-05-08_cloud_architecture.md`
- Security research: `docs/research/2026-05-08_cloud_security.md`
- Detailed migration plan: `docs/research/2026-05-08_cloud_migration_plan.md`
- Memory note: `~/.claude/projects/-Users-soumyaswain/memory/project_tradepilot_cache_poisoning.md`

---

**Owner:** Soumya Swain
**Created:** 2026-05-08
**Last updated:** 2026-05-08
**Status:** Active · awaiting Friday pre-flight
