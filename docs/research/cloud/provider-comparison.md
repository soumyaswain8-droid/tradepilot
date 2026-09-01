# Cloud Provider Comparison — TradePilot off the Mac

**PRIMARY: Oracle Cloud Infrastructure, Mumbai (ap-mumbai-1), Always Free Ampere A1 — ₹0/month.**
**FALLBACK: AWS Lightsail, Mumbai (ap-south-1), $10/month bundle (2 GB / 2 vCPU / 60 GB).**
**Reason: this workload needs ~1 GB RAM and near-zero CPU, so the only variable that actually matters is monthly cost against a ₹24,000 book — and Oracle gives 2 ARM cores and 12 GB in the same city as Zerodha's servers for nothing, with Lightsail Mumbai as the boring paid escape hatch if Oracle's ARM capacity or idle-reclaim policy bites.**

---

## 1. What the workload actually needs

Measured, from the brief:

| Dimension | Measured | Sized for |
|:--|:--|:--|
| Memory | 0.3 GB RSS across 7 processes at peak | 2 GB floor, 4 GB comfortable (2.5M-row parquet in pandas) |
| Disk | 2.4 GB total | 40–60 GB (room for parquet growth, logs, OS, swap) |
| CPU | Idle most of the day, bursty nightly | 2 vCPU (burstable is fine) |
| Network in | ~180k ticks / 6.25 h session ≈ **8 ticks/sec**, 20 symbols | trivial — any plan |
| Network out | 14 HTTP fetches × 96/day + dashboard | < 5 GB/month. Every plan below includes 1 TB+ |
| Scheduling | 41 launchd jobs | systemd timers or cron; no managed scheduler needed |

**The honest sizing conclusion: this is a 2 vCPU / 2–4 GB / 50 GB box.** Anything larger is over-provisioning. A 2.5M-row parquet is roughly 200–400 MB in memory as a pandas DataFrame — 4 GB is generous, 2 GB works if the nightly job chunks or uses pyarrow filters.

---

## 2. Latency and location — the honest answer

**Verdict: region barely matters for latency on this workload. Pick Mumbai anyway, because it is free/cheap there and it removes a variable you would otherwise have to keep explaining away.**

The evidence, not the folklore:

| Fact | Source | Implication |
|:--|:--|:--|
| Zerodha's Kite infrastructure runs in **AWS Mumbai**; they explicitly say "if you choose cloud hosting, make sure the region is set to Mumbai" | [Kite Connect forum](https://kite.trade/forum/discussion/4293/where-are-your-servers-located-which-region-should-i-host-my-code-for-least-latency) | Mumbai is the free-of-charge default choice |
| **Kite WebSocket market data latency is 700 ms – 1 s end to end**, on average | [Kite Connect forum](https://kite.trade/forum/discussion/13587/fast-market-data) | This dominates everything. Your network hop is noise next to it |
| Mumbai ↔ Singapore inter-region RTT ≈ **63 ms** | [economize.cloud, AWS ap-south-1 vs ap-southeast-1](https://www.economize.cloud/resources/aws/latency/ap-south-1-vs-ap-southeast-1/) | Singapore adds ~6–9% to an 800 ms pipeline |
| Kite REST is **behind Cloudflare**; Zerodha state the delay is "negligible wherever you host in India" | [Kite Connect forum](https://kite.trade/forum/discussion/13049/higher-bandwidth-connection-improve-performance) | The order REST path terminates at a Cloudflare edge PoP first, not at a Mumbai origin socket |
| Zerodha themselves: "Kite Connect is **not meant for HFT or latency-based strategies**" | [Kite Connect FAQ](https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/kite-connect-api-faqs) | Co-location logic does not apply here |

Worked arithmetic for a decision loop measured in seconds:

- Mumbai VM: ~800 ms (Kite pipeline) + ~2 ms (network) = **~802 ms** tick-to-your-code.
- Singapore VM: ~800 ms + ~63 ms = **~863 ms**. A 7.6% increase on a loop that already takes seconds to decide.
- Frankfurt/Helsinki VM: ~800 ms + ~120–140 ms RTT (typical India↔Central Europe; *not independently verified in this pass*) = **~930 ms**. Still under a second.

None of those three numbers changes a fill for a system whose fastest decision is seconds. If a strategy's P&L moves on 130 ms, that strategy is broken for a different reason.

**Where region *does* matter, and it is not speed:**

1. **Jitter and reconnect behaviour at 09:15.** A long-haul TCP/TLS path has more packet loss and more reconnect churn across a 6-hour WebSocket session. In-region means fewer mid-session reconnects to write recovery code for. This is a reliability argument, not a latency one.
2. **Blame elimination.** When a fill looks wrong, "the VM is in Frankfurt" becomes a permanent open question in every post-mortem. In Mumbai it never comes up.
3. **Egress and jurisdiction.** Trivial at this volume, but Indian-region hosting keeps market data inside India, which is one fewer thing to argue about if this ever stops being a paper book.

**What would change this verdict:** an options market-making or scalping strategy where the loop is sub-100 ms, or any strategy reacting to the full-mode depth (bid/ask ladder) rather than LTP. Neither describes this system.

---

## 3. Cost comparison — sized instance, all-in monthly

All figures **verified in September 2026** via the sources linked in §7. Prices are Linux, on-demand, ex-tax. INR conversions use an **assumed ₹88/USD — verify the live rate**, it is not a researched figure.

| Provider / region | Instance | vCPU / RAM / disk | Compute | Storage | Public IPv4 | **Total /mo** | **≈ ₹/mo** |
|:--|:--|:--|--:|--:|--:|--:|--:|
| **Oracle Cloud, Mumbai** (`ap-mumbai-1`) | VM.Standard.A1.Flex (ARM) | 2 OCPU / 12 GB / 200 GB | $0 | $0 | $0 | **$0** | **₹0** |
| **AWS Lightsail, Mumbai** | 2 GB bundle | 2 / 2 GB / 60 GB | $10.00 | incl. | incl. | **$10.00** | **₹880** |
| **AWS Lightsail, Mumbai** | 4 GB bundle | 2 / 4 GB / 80 GB | $20.00 | incl. | incl. | **$20.00** | **₹1,760** |
| **DigitalOcean, Bangalore** (BLR1) | Basic 2 GB | 1 / 2 GB / 50 GB | $12.00 | incl. | incl. | **$12.00** | **₹1,056** |
| **DigitalOcean, Bangalore** | Basic 2 GB / 2 vCPU | 2 / 2 GB / 60 GB | $18.00 | incl. | incl. | **$18.00** | **₹1,584** |
| **AWS EC2, ap-south-1** | t4g.small (ARM) | 2 / 2 GB / 50 GB gp3 | $8.18 | $4.56 | $3.60 | **$16.34** | **₹1,438** |
| **AWS EC2, ap-south-1** | t4g.medium (ARM) | 2 / 4 GB / 50 GB gp3 | $16.35 | $4.56 | $3.60 | **$24.51** | **₹2,157** |
| **GCP, asia-south1 (Mumbai)** | e2-small | 2 shared / 2 GB / 50 GB | $14.67 list (≈$10.3 w/ SUD) | ~$5.00 | ~$3.65 | **≈$19–23** | **₹1,672–2,024** |
| **Azure, Central India** | B2pts_v2 (ARM) | 2 / **1 GB** / 64 GB | $4.09 | ~$3–5 | ~$3.65 | **≈$11–13** | **₹968–1,144** |
| **Hetzner, Falkenstein/Helsinki** | CAX11 (ARM) | 2 / 4 GB / 40 GB | €5.99 | incl. | ~€0.60 | **≈€6.59 / $7.70** | **₹678** |
| **E2E Networks, India** | C3.8GB | 4 / 8 GB / 100 GB NVMe | $35.64 | incl. | — | **$35.64** | **₹3,136** |
| **E2E Networks, India** | E1LC-2.6GB | 2 / 6 GB | $32.32 | — | — | **$32.32** | **₹2,844** |

Notes on the numbers:

- **Lightsail Mumbai halves the transfer allowance** — the $10 bundle gets 1.5 TB, not 3 TB. Irrelevant here (you will use single-digit GB), but it is real. Overage is $0.13/GB in Mumbai.
- **EC2 is the most expensive way to buy the same box**, because IPv4 ($0.005/hr = $3.60/mo) and EBS gp3 (Mumbai: $0.0912/GB-mo) are unbundled. Lightsail is the same hardware with the fees folded in.
- **Azure B2pts_v2 at $4.09 is the cheapest in-India compute line item, but it ships 1 GB of RAM.** That is under this workload's comfortable floor once matplotlib and a 2.5M-row parquet are in play. The 4 GB ARM equivalent was not price-verified in this pass.
- **GCP asia-south1 has no viable free tier** — the always-free e2-micro is us-west1/us-central1/us-east1 only. Sustained-use discount applies automatically on GCE but not to the IP or disk.
- **E2E Networks is 3–4× the price of the Mumbai hyperscalers for this size.** Their pricing page starts at 2 vCPU / 6 GB for $32.32/mo — there is no ₹400 "nano" tier in the current published pricing, contrary to what several third-party blogs claim. E2E is priced for GPU and enterprise workloads; a personal trading bot is not their customer.
- **Hetzner is the cheapest paid box on the list** and its 4 GB of ARM RAM beats every in-India option at that price. It is in Germany or Finland. See §2 for whether that matters (it barely does) and §6 for why it is still not the pick.

**The cost frame that decides this.** A ₹24,000 paper book at an optimistic 3%/month gross returns ~₹720/month. A ₹1,584/month DigitalOcean droplet is a **79% annual drag** on the notional. Even ₹880/month Lightsail is 44%/year. **Any paid VM is arithmetically larger than what this account can earn.** That is not an argument against moving off the Mac — the Mac is failing for reliability reasons and infrastructure is a fixed cost you pay to learn — but it is a decisive argument for exhausting the free tier first.

---

## 4. Reliability — replacing a laptop that sleeps

The Mac's actual failure modes: lid closed, WiFi dropped, sleep, no unattended restart. Every option below beats it. The differences that matter:

| Provider | Host-failure auto-restart | Maintenance reboots | Notice given | Notes |
|:--|:--|:--|:--|:--|
| Oracle OCI | Yes — instance restarts on new host | Scheduled infrastructure maintenance; you can reboot-migrate early | Email + console notification, typically ~2 weeks | **Idle reclaim is the real risk, not uptime — see §5** |
| AWS EC2 / Lightsail | Yes | Scheduled events, retirement notices | Email + console, days to weeks | Best-in-class notification. Lightsail hides most of it |
| GCP | Yes, plus **live migration** (no reboot for most maintenance) | Live-migrated, not rebooted | Usually none needed | Technically the strongest maintenance story |
| Azure | Yes | Planned maintenance windows, some reboot-required | Yes, via Scheduled Events API | |
| DigitalOcean | Yes | Occasional live-migration or scheduled reboot | Email notice | |
| Hetzner | Yes | Rare | Email notice | Fine, but EU business hours for support |
| E2E Networks | Yes | Less documented publicly | Less predictable | Smallest operator on the list |

**None of these providers reboot a VM without warning under normal operation.** All of them will restart your instance on a new host after a hardware failure. The practical reliability work is not provider selection — it is:

1. `systemd` units with `Restart=always` for the 7 long-running processes (this is what launchd was doing badly).
2. `systemd` timers, not cron, for the 41 jobs — so a missed run while the host was down is visible in `journalctl` and can be `Persistent=true`.
3. A watchdog that alerts when the Kite WebSocket has not delivered a tick in N seconds during market hours. You already have this pattern.
4. Automatic instance restart is not automatic *process* restart. Test a hard `reboot` and confirm all 7 come back before you trust it.

---

## 5. Free tiers that are actually viable

### Oracle Cloud Always Free — the only genuinely viable one, with two real catches

**Current terms (verified against [Oracle's Always Free docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), September 2026):**

| Resource | Allowance |
|:--|:--|
| Ampere A1 (ARM) compute | **1,500 OCPU-hours + 9,000 GB-hours/month = 2 OCPU / 12 GB running 24×7** |
| AMD micro instances | 2 × VM.Standard.E2.1.Micro (1/8 OCPU, 1 GB) |
| Block storage | **200 GB total** (boot + block), 5 backups |
| Object storage | 20 GB, 50,000 API requests/month |
| Outbound transfer | **10 TB/month** |
| Load balancer | 1 flexible LB, 10 Mbps |
| Duration | **No expiry.** Always Free means always free |

Against the measured workload — 0.3 GB RSS, 2.4 GB disk — this is **40× the memory and 80× the disk you need**, for free, in Mumbai, forever. Nothing else on this list is close.

**Catch 1 — Oracle halved the allowance in July 2026.** It was 4 OCPU / 24 GB; it is now 2 OCPU / 12 GB, announced with minimal notice, and existing over-limit instances were shut down until manually resized, with termination of non-compliant instances after 18 August 2026 ([InfoQ](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/), [Linuxiac](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)). The precedent matters more than the number: **Oracle changes Always Free terms unilaterally and quietly.** 2 OCPU / 12 GB is still enormous for this workload — you would be fine even if they halved it again to 1 OCPU / 6 GB — but plan on the assumption that it can shrink without warning.

**Catch 2 — idle reclaim, and this workload is squarely in scope.** Oracle reclaims Always Free compute if, over a **7-day window**, *all three* of: CPU 95th-percentile < 20%, network < 20%, and memory < 20% (A1 shapes only). A system using 0.3 GB of 12 GB (2.5%), idle CPU, and 8 ticks/sec of network **meets all three tests**. Mitigations, in order of preference:

1. **Provision the smaller shape you actually need — 1 OCPU / 6 GB, or even 1 OCPU / 4 GB.** This raises your utilisation ratios toward the 20% thresholds and leaves headroom under the (shrinkable) cap. Do not take 2/12 just because it is offered.
2. **Upgrade the tenancy to Pay As You Go with a card on file.** The Always Free resources remain free, and idle-reclaim is documented as applying to Always Free *accounts*. This is the standard community workaround. *Verify this against Oracle's current terms before relying on it — it is widely reported but I did not confirm it in a primary Oracle source in this pass.*
3. Schedule the nightly research jobs so the 95th-percentile CPU clears 20% for part of the week. This happens naturally if the CPU-bursty parquet jobs run nightly.

**Catch 3 — capacity.** "Out of host capacity" on A1 shapes is the well-known failure mode; some regions provision in minutes, others take days of retries. **Mumbai-specific A1 capacity in 2026 was not verifiable in this pass** — the reports are regional and anecdotal. Practical approach: try to provision. If Mumbai refuses, Hyderabad (`ap-hyderabad-1`) is the other Indian OCI region and is a 500 km move that costs a few ms. If both refuse for a week, go to the fallback. **Always Free is limited to your home region, and home region cannot be changed after signup — so choose Mumbai or Hyderabad at account creation.**

### The others — all expire, none are viable long-term

| Provider | Free tier, 2026 | Viable for always-on? |
|:--|:--|:--|
| **AWS** | Restructured 15 July 2025. New accounts get **$100 credit + up to $100 earned, expiring at 6 months** (credits themselves at 12). The old 12-month 750h t2/t3.micro is **gone for accounts created after that date**. Account auto-closes when the Free plan ends unless upgraded. | **No.** Six months, then it stops |
| **GCP** | Always-free e2-micro exists but is **us-west1/us-central1/us-east1 only** — not asia-south1. Plus a $300/90-day trial. | **No** for a Mumbai deployment |
| **Azure** | 12-month free tier includes **750 h/month of B1s, B2pts_v2 (ARM) or B2ats_v2**, plus $200 credit for 30 days. Renews monthly *within the first 12 months*, then expires. | **No.** Twelve months, then it stops |
| **DigitalOcean / Hetzner / E2E** | Signup credits only ($200/60 days for DO, promo codes for Hetzner). No always-free compute. | **No** |

Azure's 12 free months of B2pts_v2 is worth noting as a *free bridge* if Oracle refuses capacity — but 1 GB RAM and a hard 12-month cliff make it a stopgap, not a home.

---

## 6. ARM vs x86 for this Python stack

**ARM is a non-issue. You already run this stack on ARM.**

The installed versions on the Mac, checked directly:

```
platform.machine() -> arm64          # Apple Silicon
numpy 2.4.4     pandas 2.3.3    scipy 1.17.1     sklearn 1.8.0
xgboost 3.2.0   lightgbm 4.6.0  statsmodels 0.14.0
pyarrow 23.0.1  matplotlib 3.10.8   flask 2.2.2
```

Every one of those is running natively on arm64 today. Moving to Linux/aarch64 changes the OS ABI, not the architecture.

**Wheel availability on PyPI for linux aarch64 (`manylinux_2_28_aarch64` / `manylinux2014_aarch64`):**

| Package | aarch64 wheel | Note |
|:--|:--|:--|
| numpy, pandas, scipy, scikit-learn | Yes | Long-standing, well-tested |
| **xgboost** | **Yes** — manylinux aarch64 wheels published; `pip install xgboost` needs no compiler ([PyPI](https://pypi.org/project/xgboost/)) | Was the historical gap ([dmlc/xgboost#6180](https://github.com/dmlc/xgboost/issues/6180)); resolved. 3.2.0 is well past it |
| **lightgbm** | **Yes** — manylinux aarch64 wheels published ([PyPI](https://pypi.org/project/lightgbm/)) | Historical gap ([microsoft/LightGBM#3517](https://github.com/microsoft/LightGBM/issues/3517)); resolved. 4.6.0 is well past it |
| statsmodels, pyarrow, matplotlib | Yes | |
| flask, kiteconnect | Pure Python | Architecture-irrelevant |

**Where ARM would actually hurt, and none of it applies here:**

- **Pinned old versions.** If a `requirements.txt` pins xgboost < 1.7 or lightgbm < 4.0, you land in the era before aarch64 wheels and pip will try to compile — which needs CMake, a compiler toolchain, and patience. Your versions are current; check the pin file before migrating.
- **C libraries outside PyPI.** TA-Lib, some brokers' native SDKs, anything needing a system `.so`. Compiles on ARM, but it is an afternoon rather than a `pip install`.
- **Conda.** The Mac is running Anaconda (`~/anaconda3`). If you rebuild the environment with conda on aarch64, `defaults` channel coverage is thinner than `conda-forge`. **Recommendation: rebuild with `pip` + `venv` on the server, or use conda-forge explicitly.** Do not try to copy the Anaconda tree across.
- **Numerical reproducibility.** Different BLAS (OpenBLAS on aarch64 Linux vs Accelerate on macOS) can change the last bits of a float. Backtest results will differ in the ~1e-12 range. Irrelevant for P&L, occasionally alarming in a diff. Note it before it surprises you.

Cheapest way to eliminate all residual doubt in 20 minutes: `docker run --platform linux/arm64 -it python:3.11-slim` on the Mac (native, no emulation on Apple Silicon) and `pip install` the requirements file. If it resolves, ARM is settled.

---

## 7. What would make this the wrong choice

Be explicit about the conditions under which the recommendation inverts.

**Oracle Always Free is the wrong primary if:**

1. **A1 capacity is unavailable in Mumbai and Hyderabad for more than about a week of retries.** This is the single most likely failure. Spending days scripting retry loops against Oracle's capacity API costs more than the ₹880/month the fallback costs. Set a hard limit: one week, then pay.
2. **Idle reclaim actually fires.** If the mitigations in §5 fail and Oracle terminates the instance mid-session, you have lost a trading day *and* the box. Given the workload sits inside all three idle thresholds by default, treat this as a live risk, not a theoretical one. If reclaim happens once, move to the fallback and do not fight it.
3. **Oracle changes the terms again.** They halved the allowance in July 2026 with essentially no notice. If they halve it again or attach conditions, the whole recommendation is void. Keep the migration reproducible (Ansible/shell script, not hand-tuned) so switching providers is an afternoon.
4. **The account gets flagged.** Oracle free-tier accounts get suspended for signup-fraud heuristics — duplicate cards, VPN signups, unusual regions — with slow, low-priority support. There is no SLA and no paying-customer leverage. If this system ever holds real money, "no SLA" stops being acceptable.
5. **This stops being a paper book.** At real capital above roughly ₹5 lakh, ₹880/month is 0.2%/year and the free-tier risks (reclaim, capacity, no SLA, unilateral term changes) become obviously bad economics. **The moment real money is at risk, move to the paid fallback and stop optimising for zero.**

**AWS Lightsail Mumbai is the wrong fallback if:**

6. **You need more than the bundle.** Lightsail is deliberately inflexible — fixed CPU/RAM/disk ratios, awkward to attach extra block storage, and migrating out to EC2 later is a snapshot-and-rebuild, not a resize.
7. **CPU burst credits run out.** Lightsail instances are burstable and throttle when the credit balance is exhausted. A nightly pandas job over 2.5M rows on a 2 GB / 2 vCPU bundle can plausibly do this if it runs for hours. **Monitor the burst-capacity metric during the first month.** If nightly research pins the CPU, step up to the $20 bundle or move the research jobs to a spot instance that runs and terminates.
8. **You want a single bill in INR.** Both Oracle and AWS bill in USD with FX and GST layered on. DigitalOcean Bangalore at $12 is not cheaper, but it is simpler; E2E Networks bills natively in INR but costs 3–4×.

**Hetzner is the wrong choice, despite being the cheapest paid box, because:** the €5.99 CAX11 gives you 4 GB of ARM for less than any Indian option, but it puts the process ~120–140 ms and a long-haul TCP path away from the exchange for no benefit, and it adds a permanent "was it the network?" question to every anomalous fill investigation. **It becomes the right choice if in-India options are unavailable and cost is binding** — the latency genuinely does not matter (§2), it is just not worth the explanatory overhead when Mumbai is free.

**A note on what would make *any* of this wrong:** if the real problem is that 41 launchd jobs and 7 processes are fragile rather than that the Mac sleeps, a VM inherits the fragility at a new address. The migration is worth doing for the unattended-restart and always-on properties, but budget the systemd conversion and the reboot test as the actual work. The provider decision is the easy part.

---

## 8. Recommended path

1. Create an OCI account with **home region = Mumbai (`ap-mumbai-1`)**. Home region is permanent — get this right at signup.
2. Provision **VM.Standard.A1.Flex, 1 OCPU / 6 GB, 50 GB boot volume**, Ubuntu 24.04 LTS (aarch64). Deliberately smaller than the free cap: better idle-reclaim ratios, leaves headroom if Oracle shrinks the tier again.
3. If "out of host capacity": retry, then try `ap-hyderabad-1`. **One week hard limit**, then go to Lightsail.
4. Rebuild the Python environment with `venv` + `pip` (not a copied Anaconda tree). Verify xgboost/lightgbm import and a backtest runs.
5. Convert the 41 launchd jobs to systemd timers with `Persistent=true`; the 7 processes to units with `Restart=always`.
6. Bind Flask to `127.0.0.1:5050` and reach it over an SSH tunnel or Tailscale. Do not open 5050 to the internet — this is consistent with the existing network-hardening posture.
7. **Test a hard reboot before market hours.** Confirm all 7 processes and the next 3 scheduled jobs come back unattended.
8. Consider upgrading the tenancy to Pay As You Go once a card is available — the Always Free resources stay free and it is the cleanest documented protection against idle reclaim (verify current terms first).

---

## 9. Sources

Pricing and terms verified September 2026. Where a figure could not be confirmed from a primary source, it is marked as unverified in the text above.

- [Oracle Cloud Always Free Resources — official docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle Cloud Infrastructure Free Tier — official docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- [InfoQ — Oracle quietly halves free tier Ampere A1 limits (July 2026)](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
- [Linuxiac — Oracle cuts free tier Ampere A1 resources in half](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)
- [terminalbytes — Oracle Cloud free tier 2026: 4 OCPU/24GB cut to 2 OCPU/12GB](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/)
- [Amazon Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)
- [AWS Free Tier — official billing docs](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html)
- [infratally — AWS Free Tier in 2026: what changed](https://infratally.com/articles/aws-free-tier-2026/)
- [Amazon VPC pricing — public IPv4 charges](https://aws.amazon.com/vpc/pricing/)
- [t4g.small pricing and specs — Vantage](https://instances.vantage.sh/aws/ec2/t4g.small)
- [aws-pricing.com — ap-south-1 region](https://aws-pricing.com/ap-south-1.html)
- [DigitalOcean Droplet pricing](https://www.digitalocean.com/pricing/droplets)
- [e2-small pricing and specs — Vantage](https://instances.vantage.sh/gcp/e2-small)
- [Google Cloud — free features and trial offer](https://docs.cloud.google.com/free/docs/free-cloud-features)
- [Standard_B2pts_v2 specs and pricing — cloudprice.net](https://cloudprice.net/vm/Standard_B2pts_v2)
- [Microsoft — create free services with an Azure free account](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/create-free-services)
- [Hetzner — price adjustment 15 June 2026 (official docs)](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
- [E2E Networks pricing](https://www.e2enetworks.com/pricing)
- [Kite Connect forum — where are your servers located](https://kite.trade/forum/discussion/4293/where-are-your-servers-located-which-region-should-i-host-my-code-for-least-latency)
- [Kite Connect forum — fast market data](https://kite.trade/forum/discussion/13587/fast-market-data)
- [Kite Connect forum — higher bandwidth and performance](https://kite.trade/forum/discussion/13049/higher-bandwidth-connection-improve-performance)
- [Zerodha support — Kite Connect API FAQs](https://support.zerodha.com/category/trading-and-markets/general-kite/kite-api/articles/kite-connect-api-faqs)
- [economize.cloud — AWS latency ap-south-1 vs ap-southeast-1](https://www.economize.cloud/resources/aws/latency/ap-south-1-vs-ap-southeast-1/)
- [xgboost on PyPI](https://pypi.org/project/xgboost/) · [dmlc/xgboost#6180 — aarch64 wheels](https://github.com/dmlc/xgboost/issues/6180)
- [lightgbm on PyPI](https://pypi.org/project/lightgbm/) · [microsoft/LightGBM#3517 — aarch64 wheels](https://github.com/microsoft/LightGBM/issues/3517)

---

*Author: Soumya Swain · soumya@suryaai.co.in · 2026-09-01*
