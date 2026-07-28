# GitHub Support ticket #4609220 — contribution graph not backfilled

**Submitted:** 2026-07-28 ~16:56 IST · **Status:** open · **Account:** soumyaswain8-droid
**Track at:** https://support.github.com/tickets
**Subject:** Contribution graph missing 52 commits despite correct API attribution (Repositories)
**Route used:** Repositories → Repository features → Insights → Type of Issue: "Errors, problems…"

Expect a reply in 1–3 business days. **If the canned "verify your commit email is linked"
reply arrives, do NOT redo the checks** — `author.login` resolving at all proves the link
exists. Send the Evidence 4 block at the bottom of this file instead.

---

## Ticket body as submitted

**Repository:** `soumyaswain8-droid/tradepilot` — private, **not a fork**, default branch `main`, created 2026-04-03
**Issue:** commits in this repository are correctly attributed to my account via the REST API, but are not credited on my contribution calendar.

Hello,

Commits that the REST API attributes correctly to my account are not appearing on my contribution calendar. Attribution is provably correct; only the calendar rollup is missing. There is a clean cutoff date, which suggests a partial re-index rather than a configuration problem on my side.

**Account:** `soumyaswain8-droid` (user id `257114414`)
**Commit email:** `soumya@sidewall.in` — added, verified and set primary on 2026-07-27 (~16:15 IST)
**Profile settings:** "Private contributions" and "Activity overview" are both enabled

### What happened

Before 2026-07-27 the email `soumya@sidewall.in` was not linked to my account, so commits were unattributed. I added and verified it on 2026-07-27. Since then the graph has been **partially** backfilled:

- Commits authored **2026-07-24 and later are credited exactly**.
- Commits authored **before 2026-07-24 are still credited as zero** — 52 commits across 10 days, going back to at least 2026-06-21.

### Evidence 1 — the API attributes the missing commits to my account

These are on days the calendar shows **0**. Note `author.login` and `author.id` are populated and correct on every one:

```
GET /repos/soumyaswain8-droid/tradepilot/commits/<sha>

sha=8dd9e54d3209  author.login=soumyaswain8-droid  author.id=257114414  email=soumya@sidewall.in  authored=2026-07-20T11:30:00Z
sha=32011648b00b  author.login=soumyaswain8-droid  author.id=257114414  email=soumya@sidewall.in  authored=2026-07-22T11:30:00Z
sha=adad335273af  author.login=soumyaswain8-droid  author.id=257114414  email=soumya@sidewall.in  authored=2026-07-23T11:30:00Z
sha=e79ff84e7699  author.login=soumyaswain8-droid  author.id=257114414  email=soumya@sidewall.in  authored=2026-06-21T16:39:40Z
```

### Evidence 2 — commits that ARE credited look identical

Same repository, same email, same author, same branch. The only difference is the date:

```
sha=7ac00579b9da  author.login=soumyaswain8-droid  email=soumya@sidewall.in  authored=2026-07-24T12:00:02Z   <- credited
sha=cb4d0b2561a1  author.login=soumyaswain8-droid  email=soumya@sidewall.in  authored=2026-07-25T12:00:00Z   <- credited
sha=9db48cac3529  author.login=soumyaswain8-droid  email=soumya@sidewall.in  authored=2026-07-28T02:40:52Z   <- credited
```

### Evidence 3 — day-by-day comparison

Commit counts are from `git log origin/main`; calendar counts are from the GraphQL `contributionsCollection.contributionCalendar` for the same window, queried while authenticated as myself.

| Author date (UTC) | Commits in `main` | Calendar count | Status |
|---|---:|---:|---|
| 2026-07-06 | 16 | 0 | **NOT CREDITED** |
| 2026-07-13 | 4 | 0 | **NOT CREDITED** |
| 2026-07-14 | 1 | 0 | **NOT CREDITED** |
| 2026-07-15 | 1 | 0 | **NOT CREDITED** |
| 2026-07-16 | 1 | 0 | **NOT CREDITED** |
| 2026-07-17 | 3 | 0 | **NOT CREDITED** |
| 2026-07-18 | 8 | 0 | **NOT CREDITED** |
| 2026-07-20 | 11 | 0 | **NOT CREDITED** |
| 2026-07-21 | 4 | 2 | partial |
| 2026-07-22 | 1 | 0 | **NOT CREDITED** |
| 2026-07-23 | 6 | 0 | **NOT CREDITED** |
| 2026-07-24 | 10 | 10 | credited OK |
| 2026-07-25 | 1 | 1 | credited OK |
| 2026-07-28 | 4 | 4 | credited OK |

**10 days with commits but zero credit; 52 commits not credited.**

`restrictedContributionsCount` for this window is 16, so private contributions are being counted in principle — just not for the affected dates.

### What I have already ruled out

- **Wrong or mixed commit email** — all 71 commits authored in July 2026 use `soumya@sidewall.in`; there is no second identity in the history.
- **Email not linked/verified** — added, verified and primary since 2026-07-27, and the API resolves `author.login` for the affected commits, which only happens when the email is linked.
- **Commits not on the default branch** — every affected SHA is an ancestor of `origin/main`, which is the repository's default branch.
- **Fork** — `fork=false`.
- **Private contributions hidden** — the toggle is on, and private commits from 2026-07-24 onward are being counted.
- **Waiting out the cache** — more than 24 hours have passed since verification (2026-07-27 ~16:15 IST → checked 2026-07-28 16:17 IST) and the older range has not filled in.

### What I am asking for

Please trigger a full re-index / backfill of my contribution calendar for `soumyaswain8-droid` covering at least 2026-06-01 to 2026-07-28, so the commits above are credited on their author dates.

If it helps, I am happy to grant temporary Support access to the private repository, or to supply any further SHAs or API output.

Thank you,
Soumya Swain

---

## Evidence 4 — held in reserve for the first-line reply

All four of GitHub's own documented criteria were verified and pass:

```
1. .patch From: line —
   GET /repos/soumyaswain8-droid/tradepilot/commits/<sha>  (Accept: application/vnd.github.patch)
   8dd9e54 -> From: Soumya Swain <soumya@sidewall.in>
   3201164 -> From: Soumya Swain <soumya@sidewall.in>
   adad335 -> From: Soumya Swain <soumya@sidewall.in>

2. Default branch    — every affected SHA is an ancestor of origin/main
3. 24h rebuild window— elapsed (verified 2026-07-27 16:15 IST, checked 2026-07-28 16:17 IST)
4. Repo relationship — repository owner, admin:true, fork=false
```

GitHub's own pre-submit AI triage agreed: *"more like an incomplete graph rebuild than a
repository configuration issue… you can submit this ticket as-is."*

## Fallback, only if Support declines

Remove + re-add `soumya@sidewall.in` at https://github.com/settings/emails to force a
re-index. Requires promoting another address to primary first (GitHub will not delete a
primary email) — which recreates the exact unlinked state that caused this, with no
guarantee of a deeper backfill. Prefer Support.
