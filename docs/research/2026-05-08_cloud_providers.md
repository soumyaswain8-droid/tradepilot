# Cloud Hosting Research for TradePilot — 2026

**Date:** 2026-05-08  
**Project:** TradePilot (Algorithmic Intraday Paper Trading)  
**Workload:** 7 Python engines + Flask app + Rust service, 24/5 operation

---

## Workload Requirements Summary

- **Compute:** 7 Python processes (150-300 MB each) + Flask (5050) + Rust binary
- **Total RAM needed:** ~2–2.5 GB (engines) + 512 MB (Flask) + 100 MB (Rust) = **3–3.5 GB minimum**
- **CPU:** Moderate (polling every 10 min, eventual WebSocket tick stream)
- **Storage:** ~50 MB state JSON + 200 MB ML models + ~50 MB/day logs = **~1.5 GB/month growth**
- **Network:** 200 NSE symbols × yfinance polling (currently), future Kite Connect WebSocket
- **Uptime:** 24/5 (market hours 09:15–15:30 IST, EOD reports, overnight maintenance)
- **Geography:** Owner in Mumbai (travels), low-latency to NSE preferred
- **Deployment:** Long-running daemons (not serverless)

---

## Provider Comparison Table

| Provider | Minimum Viable Plan | Monthly Cost | Mumbai/India Region | Free Trial | Deployment | Setup Difficulty | SLA |
|----------|-------------------|--------------|-------------------|-----------|-----------|-----------------|-----|
| **AWS Lightsail** | $20/mo (2 GB RAM, 2 vCPU) | ₹1,650 / $20 USD | ap-south-1 ✓ | Free tier (limited) | VMs (managed) | 2/5 | 99.99% |
| **AWS EC2** | t3.medium in ap-south-1 (4 GB, 2 vCPU) | ₹2,780 / $33.50 USD | ap-south-1 ✓ | None | VMs (full control) | 4/5 | 99.99% |
| **Railway** | Hobby $5 + usage (~$30 compute/mo) | ₹290 + ₹2,500 / $5 + $30 USD | No (global only) | $5 one-time credit | Containers/Docker | 1/5 | 99.9% |
| **Render** | Web service $7/mo + needs DB | ₹580 / $7 USD | No (US/EU only) | Free tier (sleeps) | Containers/Docker | 1/5 | 99.9% |
| **Fly.io** | ~$3.15/mo (256 MB RAM) | ₹260 / $3.15 USD base | Singapore only | None (card required) | Containers (Firecracker VMs) | 2/5 | 99.99% |
| **DigitalOcean** | Basic Droplet (512 MB, 1 vCPU) Bangalore | ₹180 / $2.15 USD | Bangalore ✓ | $200 free credits (60d) | VMs / Droplets | 2/5 | 99.99% |
| **Hetzner Cloud** | CX22 (4 GB, 2 vCPU) | ₹460 / €5.5 (~$6) | No (EU only; Singapore 40-50ms) | $20 free credits | VMs | 2/5 | 99.9% |
| **Vultr** | 1 GB RAM, Mumbai | ₹590 / $7 USD | Mumbai ✓ | $2.50 free credits | VMs | 2/5 | 99.95% |
| **GCP Compute Engine** | e2-medium (2 vCPU, 4 GB) asia-south1 | ₹2,500 / $30 USD | asia-south1 (Delhi) ✓ | $300 free credits (90d) | VMs | 3/5 | 99.95% |
| **Azure App Service** | B1 plan (1 vCPU, 1.75 GB) | ₹2,000 / $24 USD | Southeast Asia (no Delhi) | $200 free credits (1yr) | PaaS | 3/5 | 99.95% |

---

## Top 3 Recommendations

### 🥇 **#1: AWS Lightsail (ap-south-1 Mumbai)**

**Why:** Purpose-built for persistent workloads like TradePilot.
- Managed VMs with fixed pricing ($20/mo for 2 GB / 2 vCPU)
- **Direct access to ap-south-1 Mumbai region** — <10 ms latency to NSE
- All-in pricing (no hidden egress charges)
- Reliable uptime (99.99% SLA)

**Cost:** ₹1,650/mo ($20 USD)  
**Scaling:** Upgrade to $40/mo (4 GB) or $80/mo (8 GB) as needed  
**Downside:** 15% regional premium over US pricing; slightly inflexible (no granular vCPU scaling)

**12-month projection:** ₹19,800 ($240 USD) at $20/mo base tier

---

### 🥈 **#2: Railway (Global, no India region)**

**Why:** Lowest cost for flexible, containerized workload.
- Hobby plan $5/mo + usage-based compute ($20/vCPU, $10/GB RAM)
- Estimated total: ~$30–35/mo for 3 GB RAM + Flask + logs
- Simplest deployment (git push, auto-containerize)
- No server management overhead

**Cost:** ₹2,500–2,900/mo ($30–35 USD)  
**Downside:** No Mumbai/India region; ~150 ms latency from Singapore/Tokyo  
**Good for:** Development/staging; production only if latency acceptable

**12-month projection:** ₹30,000–35,000 ($360–420 USD)

---

### 🥉 **#3: DigitalOcean Bangalore + Vultr Mumbai (Hybrid)**

**Why:** Best India-local alternative if cost is secondary.
- DigitalOcean: Basic Droplet (512 MB) Bangalore = ₹180/mo; scale to ₹840/mo for 2 GB
- Vultr Mumbai: 1 GB = ₹590/mo; 2 GB likely ₹1,180/mo
- Both have sub-15 ms latency to NSE / Indian exchanges

**Cost:** ₹540–1,680/mo depending on size  
**Best:** Vultr for single-region simplicity; DigitalOcean for ecosystem features

**12-month projection (DigitalOcean 2GB Bangalore):** ₹10,080 ($120 USD)

---

## India-Specific Considerations

### **Regulatory & Compliance**
- AWS ap-south-1, GCP asia-south1 (Delhi), Azure Southeast Asia, DigitalOcean Bangalore, Vultr Mumbai = **compliant with data localization rules** if NSE data must stay in India
- Railway, Render, Fly.io (no India region) = cross-border data transfer; acceptable only for non-regulated workloads

### **Latency to NSE**
| Region | Latency to NSE (Mumbai) |
|--------|----------------------|
| AWS ap-south-1 (Mumbai) | <10 ms |
| Vultr Mumbai | <10 ms |
| DigitalOcean Bangalore | 12–15 ms |
| GCP asia-south1 (Delhi) | 25–35 ms |
| Railway (Singapore) | 150–180 ms |
| Hetzner (Singapore) | 150–180 ms |

**Recommendation:** For tick-perfect Kite Connect WebSocket, use Mumbai-based providers (AWS Lightsail / Vultr).

### **Payment Methods in India**
- **AWS:** International credit card, GST invoice
- **GCP:** International credit card, GST invoice
- **DigitalOcean:** International credit card, GST invoice (₹ billing available via Bengaluru office)
- **Vultr:** International credit card; GST not always auto-calculated
- **Railway:** International credit card only
- **Render, Fly.io:** International credit card only

---

## Final Recommendation: **AWS Lightsail ap-south-1**

**Chosen for TradePilot because:**

1. **Latency:** Direct Mumbai region <10 ms to NSE
2. **Persistent workloads:** Designed for long-running daemons (not sleep/spin-down)
3. **Simplicity:** Fixed ₹1,650/mo; no surprise egress charges
4. **Reliability:** 99.99% SLA, daily automated backups
5. **Scaling:** Easy upgrade path ($20 → $40 → $80)
6. **Integration:** Seamless with AWS Secrets Manager, CloudWatch logs, S3 backups

### Cost Breakdown (12 months on $20/mo Lightsail)

| Item | Monthly | Annual |
|------|---------|--------|
| **Lightsail $20/mo** | $20 | $240 |
| **Storage overage** (~₹200/mo) | $2.40 | $28.80 |
| **Data transfer out** (logs/reports) | $1–2 | $12–24 |
| **Snapshot backups** | $1 | $12 |
| **Total estimated** | **~$24–25** | **~₹20,400–₹21,000** |

**Note:** As yfinance polling scales to Kite Connect WebSocket (higher tick volume), consider upgrading to Lightsail $40/mo (4 GB) to handle bursty tick processing without CPU throttle.

---

## Alternative: Scaling Beyond Year 1

If TradePilot grows to multi-user SaaS:
- **Year 1–2:** Lightsail $40/mo (4 GB) — ₹2,640/mo
- **Year 2+:** AWS ECS Fargate (containerized, auto-scaling) — ₹3,000–8,000/mo depending on traffic
- **Year 3+:** Dedicated EC2 instances (m5.xlarge) — ₹10,000–15,000/mo for HA setup

---

## Sources

- [Railway vs Render 2026 – Encore](https://encore.dev/articles/render-vs-railway)
- [Fly.io Pricing 2026](https://fly.io/pricing/)
- [AWS Lightsail Pricing & Total Cost Guide 2026](https://cloudburn.io/blog/amazon-lightsail-pricing)
- [AWS ap-south-1 Pricing – AWS Regions](https://aws-pricing.com/ap-south-1.html)
- [Cloud Migration Cost India 2026: AWS vs Azure vs GCP](https://rajeshrnair.com/blog/business/business-strategy/cloud-migration-cost-india-aws-azure-guide)
- [Cheapest VPS in India 2026](https://www.techplained.com/cheapest-vps-india)
- [Railway vs Render vs Fly.io for Solo Developers 2026](https://devtoolpicks.com/blog/railway-vs-render-vs-fly-io-solo-developers-2026)
- [DigitalOcean vs Hetzner 2026 Comparison](https://betterstack.com/community/guides/web-servers/digitalocean-vs-hetzner/)

---

**Decision Date:** 2026-05-08  
**Recommendation:** AWS Lightsail ap-south-1, $20/mo ≈ ₹1,650/mo  
**Annual Budget:** ₹20,400–₹21,000 ($240–250 USD)
