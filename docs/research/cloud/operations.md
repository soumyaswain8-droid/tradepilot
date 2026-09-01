# Cloud Operations — TradePilot on an always-on Linux VM

**BIGGEST BLOCKER: the Kite `access_token` dies at 06:00 IST daily, the login is interactive by exchange mandate, and there is no refresh-token path for a retail app. On a laptop you just click a bookmark; on a headless VM nobody can.**

**RECOMMENDED ANSWER: put the VM on a private Tailscale tailnet, re-register the Kite `redirect_url` to the VM's MagicDNS name, and do the 60-second login from the phone at ~08:45. Flask stays bound to 127.0.0.1 and is reached only over the tailnet. Nothing new is exposed to the public internet, and the TOTP seed stays off the VM.**

**THE THING THAT MAKES IT WORK: `prototype/envcfg.py` reads `.env` uncached on every call, so a token written at 08:45 reaches already-running engines with no restart. Do not "optimise" that with a cache — the whole design rests on it.**

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — laptop to always-on Linux VM |
| **Version** | `v1.0.0` |
| **Status** | Research — decision pending |
| **Book at risk** | Rs 24,000 paper today, real money intended this week |
| **Created** | 2026-09-01 |
| **Updated** | 2026-09-01 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 1. Problem 1 — the daily token

### 1.1 What Kite actually does (verified against current docs, not memory)

| Fact | Source |
|:--|:--|
| `access_token` expires at **06:00 the next day** — "regulatory requirement", Kite's own words | [Kite Connect v3 — User](https://kite.trade/docs/connect/v3/user/) |
| Tokens are flushed daily; new ones generatable from roughly **07:35** | [Kite forum — access token expiry](https://kite.trade/forum/discussion/3468/access-token-expiry-time-everyday) |
| `refresh_token` is returned in the session payload but is **"only available to certain approved platforms"** — and **v3 documents no `renew_access_token` endpoint** for it | [Kite Connect v3 — User](https://kite.trade/docs/connect/v3/user/) |
| Exchange mandate: the user must **log in manually at least once a day** to trade | [Kite forum — regenerate access token](https://kite.trade/forum/discussion/14337/regenerate-access-token) |
| `redirect_url` may be `127.0.0.1` / `localhost` for personal apps; it is a **single value** registered per `api_key` in the developer console | [Kite forum — redirect URL security model](https://kite.trade/forum/discussion/6402/security-model-for-redirect-urls) |

**Conclusion: Kite offers nothing better for unattended use.** The refresh token is a partner-platform feature (smallcase-class, exchange-approved for retail scale), not something a personal `api_key` can enable. There is no long-lived option to buy or apply for at this scale. Any design that claims full unattendedness is either storing the TOTP seed or lying.

So the real question is not "how do we automate this" — it is **"where does the human's 60 seconds happen, and what happens when it doesn't."**

### 1.2 Decision table

| Option | Setup cost | What is exposed | Failure mode at **08:30 IST on a trading morning** | Verdict |
|:--|:--|:--|:--|:--|
| **A. Public Flask login route** (`/kite/login` + `/kite/callback` on a public IP/domain) | ~1 hr (DNS, TLS, reverse proxy, auth layer) | The whole Flask app, unless separately firewalled. `/kite/callback` is a **GET with no auth that writes a credential into `.env`** | Works if you remembered to add auth. If not: anyone who learns the URL can hit `/kite/callback?request_token=…`. Worse, the token lands in **proxy access logs, browser history and Referer headers** — a request_token is single-use, but the app is now internet-reachable forever, for one minute of daily convenience | **No** |
| **B. Tailscale tailnet** (VM + phone + laptop on one tailnet, Flask still on 127.0.0.1, reached via MagicDNS) | ~20 min. Free Personal plan: **$0, 6 users, unlimited user devices, 50 tagged resources, MagicDNS included** ([Tailscale free plans](https://tailscale.com/docs/account/manage-plans/free-plans-discounts), [2026 free-tier summary](https://costbench.com/software/business-vpn/tailscale/free-plan/)) | Nothing publicly. Reachable only from devices you enrolled | **The realistic failure is not "the tunnel is down" — it is "you were asleep."** If Tailscale's control plane is unavailable, established peer links usually survive but a cold phone-to-VM connection may not come up. Break-glass: SSH to the VM over the public internet (key-only) and paste the token by hand. Budget 5 minutes | **YES — recommended** |
| **C. Cloudflare Tunnel + Zero Trust Access** | ~45 min (needs a domain on Cloudflare, tunnel + Access policy). Tunnel is **free and unmetered, unlimited tunnels**; Access is **free to 50 users**, 24h log retention, 100 `cloudflared` replicas/tunnel on free ([Cloudflare One account limits](https://developers.cloudflare.com/cloudflare-one/account-limits/), [Zero Trust free tier 2026](https://costbench.com/software/business-vpn/cloudflare-zero-trust/free-plan/)) | A public hostname, gated by an Access identity policy. Correctly configured, unauthenticated traffic never reaches Flask | Same 08:30 story as B, plus one extra dependency: Kite's redirect must survive the Access interstitial. If your Access session has expired, you get an email-OTP login **in front of** the Zerodha login — two auth hops before the market opens. More moving parts on the critical path | Good, but B is simpler |
| **D. Raw WireGuard** | ~45–90 min (key exchange, IP plan, NAT/keepalive, phone profile) | Nothing publicly, one UDP port on the VM | Same as B but **you** are the control plane. No MagicDNS, no ACL console, no easy re-key from a phone. If the phone profile breaks at 08:25 you are editing a config on a train | Only if you object to a third party in the path |
| **E. Store the TOTP seed on the VM, fully automate** | ~2 hrs (headless login automation is fragile and breaks whenever Zerodha changes the login page) | See below | **Nothing fails at 08:30 — this genuinely works.** That is exactly why it is tempting, and exactly why the trade-off has to be stated plainly rather than discovered later | **Owner has declined. Presented as a choice, not a recommendation** |

### 1.3 Option E — the honest security statement

This is not "less secure." It is a specific, nameable change in what a VM compromise costs you.

**Today**, an attacker with root on the VM gets: the `api_key`, the `api_secret`, and today's `access_token`. That is bad — they can read your positions and, if the live gates are on, trade your account **until 06:00 tomorrow**. Then it dies on its own. Your Zerodha password and 2FA are untouched, and you can revoke the API app from the developer console.

**With the TOTP seed on the VM**, the same attacker gets: your Zerodha **password and your second factor, in the same place**. That is not an API credential — that is your brokerage login. They can generate a fresh token every morning indefinitely, log in to Kite Web (not just the API), see full holdings and bank details, and the daily expiry stops being a natural circuit breaker. Two-factor authentication with both factors on one disk is one-factor authentication with extra steps.

The seed is also **not revocable the way a token is**: rotating it means re-enrolling 2FA on your actual brokerage account, under pressure, after you have already been breached.

The counter-argument is real and should be stated too: a VM you control, with key-only SSH and no public services, is not obviously easier to compromise than a laptop that goes to cafés. If you ever change your mind, the mitigations that would make it defensible are: seed in `root`-owned `0400` file outside the repo tree, `systemd` unit running as a dedicated user with `LoadCredential=`, no shell on that user, and alerting on every token generation so an unexpected 03:00 login pages you.

**The owner has declined this. Do not implement it, and do not quietly reintroduce it as "convenience."**

### 1.4 The concrete recommended flow

1. Install Tailscale on VM, phone, and laptop. Free Personal plan, one tailnet.
2. **Change the Kite `redirect_url` in the developer console** from `http://127.0.0.1:5050/kite/callback` to the VM's tailnet address — `http://tradepilot-vm.<tailnet>.ts.net:5050/kite/callback`. **Verify Kite accepts a non-localhost `http://` host before relying on this**; if it refuses, fall back to `tailscale serve` to terminate TLS and register the `https://` name instead.
   - Only one redirect URL exists per `api_key`. Changing it **breaks the laptop flow**. That is fine and actually desirable — one path, always exercised. The laptop reaches the same URL over the tailnet.
3. Keep `app.run(host="127.0.0.1", …)` exactly as it is (`prototype/app.py:4103`). Tailscale reaches it via `tailscale serve` proxying to loopback; the socket never binds a public interface.
4. Morning ritual, from the phone, ~08:45: open the bookmark → `/kite/login` → Zerodha login + TOTP **on the phone, where the seed already lives in your authenticator** → callback writes `.env` on the VM.
5. `scripts/kite-token-reminder.py` already escalates at 06:05 / 08:50 / 09:10 and is silent when the token is valid. Point it at Telegram on the VM. Do not change its silence-when-healthy behaviour.
6. `scripts/kite-token-check.py` already exits 1 when credentials exist but the token does not. **Make that exit code block live orders**, not just print.

**Why this over Cloudflare:** fewer hops on the critical path, no domain required, no second auth interstitial in front of Zerodha's own login, and the phone app is the thing you will actually have in your hand at 08:45.

---

## 2. Problem 2 — secrets

### 2.1 Is `.env` actually ignored? **Yes — verified.**

```
.gitignore:35:.env
$ git check-ignore -v .env   ->  .gitignore:35:.env   .env
$ git ls-files --error-unmatch .env  ->  not tracked
$ git log --all --diff-filter=A --name-only | grep '\.env'  ->  no hits
```

`.env` is ignored, has never been tracked, and **does not appear anywhere in git history**. Permissions are already `-rw-------` (0600). This is correct and needs no change.

### 2.2 What changes on a VM

The file itself is fine. Three things around it get worse:

1. **`/kite/callback` rewrites `.env` daily** (`prototype/app.py:3648-3653`) by read → filter → write. That is a non-atomic full-file rewrite of your only secrets file. A crash mid-write, or two callbacks racing, truncates it. On a laptop you notice; on a VM you find out when every engine loses its API key at once.
2. **Backups and snapshots.** VM provider snapshots contain `.env`. So does any `rsync` of the repo. On the laptop the disk was encrypted at rest by FileVault; a cloud volume snapshot is not yours to manage.
3. **More processes read it.** `envcfg`, `kite_data`, `kite_broker`, `floor_live`, `telegram_bot` all read `.env` directly, some with their own parsers.

### 2.3 Proportionate recommendation (single-owner, must survive neglect)

Do these four. Skip anything resembling Vault, KMS, or SOPS — an unmaintained secrets system is worse than a well-permissioned file.

| # | Action | Why |
|:--|:--|:--|
| 1 | **Move `.env` out of the repo tree** to `/etc/tradepilot/env`, owner `tradepilot:tradepilot`, mode `0600`. Point `envcfg.ROOT` at it via a `TRADEPILOT_ENV` override | Removes the entire class of "accidentally committed / rsynced / tarballed with the repo" |
| 2 | **Make the callback write atomic**: write `.env.tmp` in the same directory, `os.replace()` over the target | `os.replace` is atomic on POSIX. Turns a corrupting failure into a no-op failure |
| 3 | **Split the file in two**: `env.secrets` (API keys, tokens, bot token) and `env.risk` (`KITE_MAX_ORDER_VALUE`, `MAX_DAILY_LOSS`, `MAX_OPEN_POSITIONS`) | Risk limits are configuration you will want to read, diff, and version. Secrets are not. Today they are interleaved, so you cannot safely show anyone the risk config |
| 4 | **Rotate every key during the migration**, before real money. New `api_secret`, new Telegram bot token, new Alpaca and FMP keys | These have lived on a laptop that has been on untrusted WiFi. Migration is the free moment to rotate; after real money starts it costs a trading day |

Optional, cheap, high value: `systemd` `LoadCredential=` so the secrets file is mounted into the unit's private tmpfs rather than read from a world-traversable path. Ten minutes, no ongoing maintenance.

---

## 3. Problem 3 — exposure

### 3.1 Today

`prototype/app.py:4103` — `app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)`. Loopback only, debug off. Correct.

### 3.2 The route inventory that matters

**73 routes.** The overwhelming majority are read-only JSON. These are the ones that are not:

#### Tier 1 — must NEVER be reachable by anyone but the owner

| Route | Method | What it does |
|:--|:--|:--|
| **`/kite/callback`** (`app.py:3616`) | **GET**, no auth | **Exchanges a `request_token` and writes `KITE_ACCESS_TOKEN` into `.env`.** This is the single most dangerous route in the app: an unauthenticated GET that mutates your credential store. A leaked callback URL is not merely an information leak — it is a write primitive against your secrets file |
| **`/kite/login`** (`app.py:3661`) | GET, no auth | Leaks the `api_key` in the returned Zerodha URL. Low harm alone (the secret is what matters), but it advertises that a Kite-connected trading system lives here |

#### Tier 2 — mutate application state, no auth

| Route | Method | What it does |
|:--|:--|:--|
| `/api/paper/buy` (`app.py:2548`) | POST | Mutates in-process `paper_portfolio` |
| `/api/paper/sell` (`app.py:2563`) | POST | Mutates positions, cash, win/loss counts |
| `/api/paper/swipe` (`app.py:2648`) | POST | Buys at 5% of cash from a single field |
| **`/api/paper/reset`** (`app.py:2629`) | POST | **Wipes positions and history with no confirmation and no auth.** Destroys the evidence trail an experiment depends on |
| `/api/analytics/track` (`app.py:2684`) | POST | Unauthenticated write — a log-injection / disk-fill vector |
| `/api/ask` (`app.py:2943`) | POST | Free-text into an LLM path. Unauthenticated = someone else's inference bill, and a prompt-injection surface |

#### Tier 3 — informational but sensitive

`/admin` (2712), `/api/system-health` (1270), `/api/team/audit` (3259), `/portfolio` (3520), `/fleet` (3562), `/api/desk` (3769). These disclose positions, engine internals and infrastructure state.

### 3.3 The good news, stated precisely

**No Flask route can place a real order today.** Verified: `place_order` exists only in `prototype/us/broker.py`, `prototype/v5/kite_broker.py`, and `scripts/us-paper-trade.py` — never in `app.py`. Real submission in `kite_broker.place_order` requires the full triple gate (`prototype/v5/kite_broker.py:217-247`): credentials **and** `KITE_LIVE_ORDERS=1` **and** `KITE_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY`, with `KILL_SWITCH`, `MAX_ORDER_VALUE`, `MAX_DAILY_LOSS` and `MAX_OPEN_POSITIONS` checked before every order. That design is sound and should not be softened.

The exposure risk is therefore **not "the dashboard places a trade."** It is:
- the credential-writing GET at `/kite/callback`;
- destructive unauthenticated state mutation (`/api/paper/reset`) that can void an experiment;
- and the fact that **the gate is environment variables** — anyone who can write the environment or `.env` can flip `KITE_LIVE_ORDERS`, which is one more reason `/kite/callback` must never be public.

### 3.4 Recommendation

Keep the bind on `127.0.0.1`. The owner sees the dashboard by joining the tailnet — same URL, same port, from phone or laptop. If you ever do expose it, split the app: read-only routes on the exposed listener, every Tier 1 and Tier 2 route on a loopback-only listener. Do not rely on "nobody knows the URL."

---

## 4. Problem 4 — what breaks when nobody is watching

### 4.1 What exists

- `prototype/v5/telegram_bot.py` — `send_alert`, `alert_entry`, `alert_exit`, `alert_circuit_breaker`, `alert_daily_summary`, `alert_regime_change`. Rate-limited to 30 msgs/60s.
- `scripts/floor-watchdog.sh` — liveness via **log staleness** (210s), not `pgrep`. Correct instinct: a hung process is as dead as an absent one. Capped at 4 restarts/day, and it verifies each relaunch took.
- `scripts/kite-token-check.py` and `scripts/kite-token-reminder.py` — 06:05 / 08:50 / 09:10 escalation, silent when healthy.

**Two gaps found:**

1. **No disk monitoring exists anywhere in the repo.** A grep across `scripts/` and `prototype/` for `df`, `shutil.disk_usage`, and `statvfs` returns **nothing**. The volume that froze the machine for six hours on 2026-08-28 is still unmonitored, and the laptop is at **98% used, 5.4 GiB free** right now — `docs/` is 751 MB and `logs/` is 114 MB across 1,182 files. This will recur on the VM, where the disk is smaller and nobody is sitting in front of it.
2. **`telegram_bot.check_commands()` does not filter by `chat_id`.** It accepts any `/command` from any `getUpdates` sender. Anyone who discovers the bot handle can run `/status` and read your portfolio. Fix before the VM: drop updates whose `message.chat.id` is not the configured `chat_id`.

### 4.2 Minimum alerting before real money runs unattended

Six alerts. Each must be **actionable, deduplicated, and silent when healthy**.

| # | Alert | Trigger | The message must say |
|:--|:--|:--|:--|
| 1 | **Token expiry** | Escalate 06:05 / 08:50 / 09:10 IST while the token is invalid. **Hard-stop at 09:10** | `KITE TOKEN INVALID — 5 min to open. Engines will NOT trade live today. Login: http://tradepilot-vm…/kite/login` — must contain the tappable link. A reminder you cannot act on from the lock screen is not a reminder |
| 2 | **Process death** | Extend `floor-watchdog.sh` staleness logic to every engine. Alert on **every restart**, and page loudly when `MAX_RESTARTS` is exhausted | `FLOOR DEAD — log stale 4m12s. Restart 3/4 attempted, PID 4417 confirmed up.` And on exhaustion: `FLOOR DEAD — restart cap reached, NOT retrying. Positions open: 3. Manual intervention required.` A silent successful restart is fine to log and still worth one line; a failed one must be impossible to miss |
| 3 | **Daily-loss breaker** | `SafetyRailBreached` on `MAX_DAILY_LOSS` in `kite_broker._check_rails` | `DAILY LOSS BREAKER TRIPPED — realised Rs -1,250 vs cap Rs -1,250. Trading halted for the day. Open positions: 2 (RELIANCE 4, TCS 1) — these are NOT auto-closed.` **Stating what the breaker does not do is the load-bearing half.** Same shape for `MAX_ORDER_VALUE` and `MAX_OPEN_POSITIONS` |
| 4 | **Disk** | New. Check every 15 min. Warn <20% free, **page <10% free** | `DISK 8% FREE (3.1G of 40G). Largest: logs/ 4.2G, docs/ 1.9G. Rotate now or the box freezes.` Pair it with an actual fix — `logrotate` on `logs/*.log`, daily gzip, 30-day retention — because an alert about a disk you cannot clear from a phone is just anxiety |
| 5 | **VM reboot** | A `systemd` oneshot with `WantedBy=multi-user.target` that fires on every boot | `VM REBOOTED 03:14 IST. Uptime 0m. Engines: v5 UP, v5_gate UP, floor DOWN. Kite token: PRESENT/valid until 06:00.` The reboot itself is survivable; **silently starting with a different set of processes than you had is not.** This alert is the one that catches provider live-migrations and OOM kills |
| 6 | **Heartbeat** | One message at 09:14 IST: "system is up and armed" | `PREFLIGHT OK 09:14 — token valid, 4 engines up, disk 34% free, breakers armed, live orders OFF.` Alerts 1–5 tell you when something broke. This one tells you the **alerting itself** is alive. Without it, a dead Telegram token looks exactly like a quiet, healthy morning — and that is the failure that ends with real money and no observer |

**Two rules across all six.** Dedupe: `.pager_dedupe.json` already exists (`docs/team/audit/`) and `tests/test_pager_dedupe.py` covers it — reuse it, do not write a second one. And escalate at most once per condition per day; a channel that cries wolf is a channel you mute, and the existing preflight ML nag is already teaching that habit.

---

## 5. Pre-flight checklist — must pass BEFORE real money runs unattended

Every line must be verified on the VM, not assumed. This is a gate, not a to-do list.

::: {.checklist}

| | Area | Verification |
|:---:|:-----|:-------------|
| ☐ | **Token** | Kite `redirect_url` re-registered to the tailnet host and a **full login completed end-to-end from the phone**, not the laptop |
| ☐ | | `scripts/kite-token-check.py` exits 0 on the VM, and its **exit 1 hard-blocks live orders** rather than only printing |
| ☐ | | `envcfg` is still uncached — a token written at 08:45 is picked up by a process started at 08:00, verified by observation |
| ☐ | | Break-glass documented and **rehearsed once**: public-internet SSH (key-only) → paste token → confirm engines see it, inside 5 minutes |
| ☐ | | Documented answer to "no valid token at 09:10": system refuses to trade live. **It must not silently fall back to yfinance prices while live orders are armed** |
| ☐ | **Secrets** | `.env` moved to `/etc/tradepilot/env`, mode 0600, owned by the service user, outside the repo tree |
| ☐ | | `/kite/callback` writes atomically (`.tmp` + `os.replace`) — verified by killing the process mid-write |
| ☐ | | All keys rotated post-migration: `KITE_API_SECRET`, `TELEGRAM_BOT_TOKEN`, `ALPACA_API_KEY`, `FMP_API_KEY` |
| ☐ | | `git check-ignore -v .env` passes and `git log --all --diff-filter=A` shows no `.env` — re-confirm after the move |
| ☐ | **Exposure** | `ss -tlnp` on the VM shows Flask bound to `127.0.0.1:5050` only |
| ☐ | | `curl` to the VM's **public** IP on 5050 is refused, from off-tailnet |
| ☐ | | `/kite/callback`, `/kite/login`, `/api/paper/reset` unreachable except over the tailnet |
| ☐ | | `telegram_bot.check_commands()` filters on `chat_id`; a message from an unknown chat is ignored, verified by test |
| ☐ | **Alerting** | All six alerts fire on a deliberately induced failure — kill the floor, fill the disk with a ballast file, reboot the VM, revoke the token. **An alert that has never fired has never worked** |
| ☐ | | The 09:14 heartbeat arrives on the phone two mornings running |
| ☐ | | Dedupe reuses `.pager_dedupe.json`; a repeating condition sends once, not every cycle |
| ☐ | **Disk** | `logrotate` configured on `logs/*.log`, 30-day retention, gzip; free space >50% after rotation |
| ☐ | | Disk alert verified against a real ballast file, then the ballast removed |
| ☐ | **Resilience** | `systemd` units for every engine with `Restart=on-failure` and `RestartSec`; survives `reboot` with the same process set |
| ☐ | | Clock is NTP-synced and `Asia/Kolkata` — a wrong TZ silently shifts every 09:15 schedule |
| ☐ | | `KILL_SWITCH` tested **on the VM**: touch the file, confirm the next order attempt raises `KillSwitchActive` |
| ☐ | **Live gate** | `KITE_LIVE_ORDERS` and `KITE_LIVE_CONFIRM` are **absent** until every box above is ticked |
| ☐ | | `MAX_ORDER_VALUE` / `MAX_DAILY_LOSS` / `MAX_OPEN_POSITIONS` sized for the real book, and `kite-check` prints the **enforced** values — the 2026-08-31 bug was a cap reporting a number it was not enforcing |
| ☐ | | One full trading day observed on the VM in **paper** mode with all alerting live, before any live flag is set |

:::

---

## 6. Sources

- [Kite Connect v3 — User / session semantics](https://kite.trade/docs/connect/v3/user/)
- [Kite Connect v3 — Mobile and Desktop apps](https://kite.trade/docs/connect/v3/apps/)
- [Kite forum — access token expiry time](https://kite.trade/forum/discussion/3468/access-token-expiry-time-everyday)
- [Kite forum — regenerate access token](https://kite.trade/forum/discussion/14337/regenerate-access-token)
- [Kite forum — refresh token generation](https://kite.trade/forum/discussion/5394/refresh-token-generation)
- [Kite forum — security model for redirect URLs](https://kite.trade/forum/discussion/6402/security-model-for-redirect-urls)
- [Tailscale — free plans and discounts](https://tailscale.com/docs/account/manage-plans/free-plans-discounts)
- [Tailscale free tier limits, 2026](https://costbench.com/software/business-vpn/tailscale/free-plan/)
- [Tailscale serve vs funnel](https://www.ssdnodes.com/learn/tailscale-serve-vs-funnel)
- [Cloudflare One — account limits](https://developers.cloudflare.com/cloudflare-one/account-limits/)
- [Cloudflare Zero Trust free tier, 2026](https://costbench.com/software/business-vpn/cloudflare-zero-trust/free-plan/)
