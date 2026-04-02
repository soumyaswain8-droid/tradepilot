# TradePilot Strategy Survey

*Saved for future reference -- all options preserved for revisiting decisions*

Created: 2026-04-02

---

## Round 1: Business & Market

### Q1. Who is your Day-1 user?

| Option | Who | Size | Why |
|--------|-----|------|-----|
| A | F&O traders losing money | 10.5M | Biggest pain, willing to pay to stop bleeding |
| **B (SELECTED)** | **Beginner traders (Gen Z, first-timers)** | **5-10M/year** | **Massive volume, need education + guardrails** |
| C | Profitable traders cobbling 5 tools | 500K-1M | High willingness to pay, power users |
| D | Algo-curious retail traders | 2-3M | Want automation but can't code |

### Q2. Revenue model priority?

| Option | Model | When money comes |
|--------|-------|-----------------|
| **A (SELECTED)** | **Freemium + Pro subscription (Rs 499-999/month)** | **Users pay for AI scoring, backtesting, automation** |
| B | Brokerage-first (partner with broker, earn per trade) | Volume-based, like Zerodha but smarter |
| C | Education-first (courses + certification, Rs 2K-5K) | Monetize learning, platform is free |
| D | Hybrid (free platform + premium features + brokerage cut) | Multiple streams from day one |

### Q3. Regulatory path?

| Option | Path | Time | Cost | Risk |
|--------|------|------|------|------|
| A | SEBI Research Analyst (RA) -- advisory/signals only | 1-2 months | Rs 5-10L | Low |
| **B (SELECTED)** | **Authorized Person (AP) -- white-label under broker** | **1-2 months** | **Rs 2-5L** | **Low-Med** |
| C | Technology partner (like Smallcase/Sensibull model) | 3-6 months | Rs 10-30L | Low |
| D | Full broker license from the start | 6-18 months | Rs 50L+ | High |

### Q4. What's the #1 thing that makes a trader switch to TradePilot?

| Option | Hook | Why it works |
|--------|------|-------------|
| **A (SELECTED)** | **"See your profit probability before every trade"** | **No one does this. Instant differentiation** |
| B | "Never lose more than you set" (risk guardrails) | Loss prevention = emotional relief |
| C | "Replace 5 apps with 1" (unified platform) | Convenience + cost saving |
| D | "Backtest any strategy on 10 years of Indian data" | Validation before real money |

### Q5. What does success look like in 6 months?

| Option | Goal | Metric |
|--------|------|--------|
| A | 10,000 active users, Rs 5L MRR | Growth-focused |
| **B (SELECTED)** | **1,000 paying users, product-market fit proven** | **Quality-focused** |
| C | Platform live with backtesting + AI scoring, 5,000 signups | Product-focused |
| D | Revenue-positive (even if small), 2,000 users | Sustainability-focused |

---

## Round 1 Summary

**Profile:** TradePilot targets beginner traders (Gen Z) with a freemium subscription model, launching as an Authorized Person under an existing broker. The killer hook is AI-powered profit probability scoring. Success = 1,000 paying users with proven product-market fit in 6 months.

---

## Round 2: Product & Technology

### Q6. What should the MVP include?

| Option | Feature | Build Time | Impact |
|--------|---------|:----------:|--------|
| **A (SELECTED)** | **AI Trade Scorer (profit probability before every trade)** | **6-8 weeks** | **Killer hook** |
| B | Paper trading / simulator (learn without real money) | 4-6 weeks | Perfect for beginners |
| C | Interactive charting with TradingView integration | 3-4 weeks | Table stakes |
| D | Options strategy builder with Greeks | 6-8 weeks | Power users love it |
| E | Educational content (bite-sized lessons + quizzes) | 4-6 weeks | Retention for beginners |
| F | Portfolio analytics dashboard (P&L, drawdown) | 4-6 weeks | Makes people stay |
| G | Backtesting engine (validate strategies on history) | 8-10 weeks | Competitive moat |

### Q7. Platform -- where do users access TradePilot?

| Option | Platform | Why |
|--------|----------|-----|
| A | Mobile-first (iOS + Android app) | 80%+ of Indian traders use mobile |
| B | Web-first (responsive web app) | Faster to build, easier to iterate |
| **C (SELECTED)** | **Both from day 1 (React Native + Web)** | **Maximum reach** |
| D | Web app + Progressive Web App (PWA) for mobile | Best of both, single codebase |

### Q8. Tech stack preference?

| Option | Stack | Tradeoff |
|--------|-------|----------|
| A | Next.js + Python (AI) + PostgreSQL | Fast to build, huge talent pool |
| B | Next.js + Go (backend) + QuestDB | Performance-first, harder to hire |
| C | React Native + Node.js + TimescaleDB | Mobile-native, JS everywhere |
| **D (SELECTED)** | **Flutter (mobile) + Rust (backend) + QuestDB** | **Blazing fast, hardest to hire** |

**NOTE:** Tension with Q11 (Rs 5-10L budget). This stack works only if founders can code Rust/Flutter. Otherwise consider Option A (Next.js + Python) for MVP, migrate to Rust later.

### Q9. Broker API integration -- who do you partner with first?

| Option | Broker | Why |
|--------|--------|-----|
| A | Zerodha (Kite Connect) | Largest user base, free personal APIs |
| B | Angel One (SmartAPI) | Best algo support, commodity access |
| C | Dhan (DhanHQ) | Fastest execution (<50ms), options focus |
| **D (SELECTED)** | **Multiple (Zerodha + Angel One)** | **More coverage, more complexity** |

---

## Round 2 Summary

**Profile:** MVP = AI Trade Scorer as the core feature. Flutter + Rust + QuestDB stack (performance-first). Both mobile + web from day 1. Multi-broker integration (Zerodha + Angel One).

---

## Round 3: Go-to-Market & Execution

### Q10. How do you acquire your first 1,000 users?

| Option | Channel | Cost | Speed |
|--------|---------|:----:|:-----:|
| **A (SELECTED)** | **YouTube/Instagram content (trading education + platform demos)** | **Low** | **Slow (3-6 months)** |
| B | Reddit/Twitter community (r/IndianStreetBets, FinTwit) | Free | Medium (2-4 months) |
| C | Referral program (invite friends, get Pro free for a month) | Medium | Fast (1-2 months) |
| D | College campus ambassadors (target Gen Z directly) | Medium | Medium (2-3 months) |
| **E (SELECTED)** | **Paid ads (Google/Meta targeting "stock trading for beginners")** | **High** | **Fast (1 month)** |
| **F (SELECTED)** | **Influencer partnerships (finfluencers with 100K+ followers)** | **High** | **Fast (1-2 months)** |

### Q11. What's your initial investment budget?

| Option | Budget | What it covers |
|--------|-------:|:---------------|
| **A (SELECTED)** | **Rs 5-10L** | **Solo/co-founder build, minimal infra, AP license** |
| B | Rs 15-25L | Small team (2-3 devs), infra, AP + marketing |
| C | Rs 50L-1Cr | Full team, proper infra, multiple broker integrations |
| D | Rs 1Cr+ | Aggressive launch, full team, marketing blitz |

### Q12. What's your biggest fear / what could kill this?

| Option | Risk | Mitigation needed |
|--------|------|:-------------------|
| **A (SELECTED)** | **SEBI regulations change / algo trading gets restricted further** | **Regulatory monitoring + pivot plan** |
| **B (SELECTED)** | **AI predictions aren't accurate enough, users lose trust** | **Transparency about probability vs certainty** |
| **C (SELECTED)** | **Can't compete with Zerodha's brand and network effects** | **Niche down harder, don't compete on price** |
| D | Can't find Rust/Flutter developers | Hire remote, or pivot to simpler stack |
| E | Broker APIs are unreliable / partner pulls the plug | Multi-broker from day 1 (already chosen) |

---

## Round 3 Summary

**Profile:** Acquire users via content marketing (YouTube/Instagram) + paid ads + finfluencer partnerships. Budget: Rs 5-10L (lean founder-led build). Top risks: regulatory change, AI trust gap, and competing with Zerodha's brand.

---

## Full Strategy Profile

| Decision | Choice |
|----------|--------|
| Day-1 user | Beginner traders (Gen Z, first-timers) |
| Revenue | Freemium + Pro subscription (Rs 499-999/month) |
| Regulatory | Authorized Person (AP) under broker |
| Hook | "See your profit probability before every trade" |
| 6-month goal | 1,000 paying users, PMF proven |
| MVP feature | AI Trade Scorer |
| Platform | Mobile + Web (Flutter) |
| Tech stack | Flutter + Rust + QuestDB |
| Broker API | Zerodha + Angel One |
| Acquisition | Content + Paid ads + Finfluencers |
| Budget | Rs 5-10L |
| Top risks | Regulatory, AI trust, brand competition |

### Tensions Resolved (2026-04-02)
1. **Stack vs Budget:** RESOLVED -- DevPilot codes the Rust/Flutter. Co-founder helps. No hiring needed for MVP.
2. **Marketing vs Build:** RESOLVED -- Build first, marketing later. Focus 100% on product.
3. **Multi-broker vs MVP speed:** RESOLVED -- Zerodha only for v0.1. Angel One added later.
