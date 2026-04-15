# Indian Market Alpha Edges -- TradePilot v5 Research

*Multi-horizon strategies: Intraday | Swing | Positional | Investment*
*Research date: 2026-04-08*

---

## 1. FII/DII Flow Prediction

**Edge**: FII flows lead Indian market by 1-3 days. FII selling > 2000cr/day = bearish next 2-3 sessions. FII buying reversal after prolonged selling = strong rally signal.

| Signal | Interpretation | Horizon |
|--------|---------------|---------|
| FII net sell > 3000cr + DII net buy > 2000cr | Tug-of-war, market choppy | Swing (2-5d) |
| FII net buy flip after 10+ sell days | Reversal rally incoming | Positional (1-4w) |
| FII heavy in financials | Sector rotation into banks/NBFC | Swing |
| DXY rising + US yields up | FII outflow from India likely | Positional |
| GIFT Nifty premium > 50pts over prev close | Strong FII overnight buying | Intraday |

**Correlation chain**: US 10Y yield up -> DXY strengthens -> EM outflows -> FII sells India -> Nifty drops (1-3 day lag)

**2025 evidence**: FIIs pulled out >1 lakh crore by mid-Feb 2025 (strong dollar + high US rates). Reversed in April 2025 with 22,910cr into financials in 2 weeks -- Nifty rallied 8%.

**Data sources**:
- NSE FII/DII daily: `https://www.nseindia.com/reports/fii-dii` (free, EOD)
- NSDL FPI monthly trends: `https://www.fpi.nsdl.co.in/Reports/Monthly.aspx` (free)
- Participant-wise OI (FII/DII/Pro/Client): NSE archives CSV, published 5-6 PM daily
- Python: `nsefin` package -- `fii_dii_data()` returns pandas DataFrame

---

## 2. F&O Expiry Effects

**CRITICAL UPDATE (Sep 2025)**: NSE moved weekly expiry from Thursday to Tuesday. BSE gets Thursday. Monthly/quarterly expiry moved to Monday. All strategies must be recalibrated.

| Pattern | Evidence | Strategy |
|---------|----------|----------|
| Max Pain convergence | Price gravitates to max pain strike in last 2hrs of expiry | Sell OTM options targeting max pain |
| OI unwinding T-1 | Heavy OI at strikes unwinds day before expiry | Trade in direction of unwinding |
| Expiry week volatility | Option writers defend high OI strikes aggressively | Iron condor/butterfly around max pain |
| Pin risk at round strikes | 22000, 22500 etc act as magnets on expiry | Avoid naked positions near round strikes |
| Post-expiry drift | New series starts with momentum, not mean-reversion | Trend-follow first 2 days of new series |

**SEBI finding**: 90%+ of retail F&O traders lost money (1.81 lakh crore over 3 years). Edge exists for option sellers, not buyers.

**Data sources**:
- NSE Option Chain: `https://www.nseindia.com/option-chain` (live, free)
- Python: `nsepython` -- `nse_optionchain_scrapper("NIFTY")` returns full chain
- Max Pain calculators: Sensibull (free tier), Opstra

---

## 3. Sector Rotation in India

**Regime-based rotation map**:

| Market Regime | Leading Sectors | Lagging Sectors | Signal |
|---------------|----------------|-----------------|--------|
| Weak rupee (INR depreciation) | IT, Pharma (dollar earners) | Auto, Oil importers | USD/INR > 84, DXY > 105 |
| RBI rate cuts | Real estate, Auto, NBFCs | Banks (NIM compression) | Repo rate cut announcement |
| RBI rate hikes | Banks (NIM expansion), PSU banks | Real estate, leveraged cos | Repo rate hike |
| Risk-off / global fear | Pharma, FMCG, Gold | Metals, IT, small-caps | India VIX > 20 |
| Risk-on / FII inflow | Banks, Auto, Capital goods | Defensives (Pharma, FMCG) | FII net buy + VIX < 14 |
| Election / policy uncertainty | Defense, Infra, PSU | Private banks, consumer | Pre-budget/election period |
| Commodity supercycle | Metals, Oil & Gas, Mining | IT, FMCG | CRB index rising |

**2024-2025 rotation evidence**:
- PSU Bank index surged 27.67% (leader)
- IT index dropped 9.71% (weak global tech spend)
- Pharma declined 2.14%, FMCG fell 2.81% (defensive rotation out)
- Of 69 BSE 200 stocks up 30%+ in 2024, 39 posted negative returns in 2025

**Data sources**:
- Nifty sectoral indices: NSE website (free, daily)
- Relative strength calculation: Nifty IT / Nifty 50 ratio (plot on TradingView)
- Trendlyne sector heatmap: `https://trendlyne.com/` (free tier available)

---

## 4. Event-Driven Strategies

| Event | Typical Impact | Pre-Event | Post-Event | Horizon |
|-------|---------------|-----------|------------|---------|
| **RBI Policy** (bi-monthly) | VIX spike before, crush after | Buy straddle T-3 | Sell straddle on announcement day | Intraday |
| **Union Budget** (Feb 1) | Sectoral moves 3-8%, tax changes drive specific stocks | VIX rises 2 weeks before | Budget beneficiary sectors rally 1-2 weeks | Swing |
| **MSCI Rebalancing** (Feb/May/Aug/Nov) | Forced FII flows ~$200-500M per rebalancing | Buy additions 2 weeks before effective date | Sell on effective date (front-running fades) | Positional |
| **Quarterly Results** (Jan/Apr/Jul/Oct) | Individual stock moves 5-15% | Buy vol before results for high-beta stocks | Fade extreme gaps post-results | Swing |
| **US Fed Decision** | INR/FII flow impact | Indian market cautious T-1 | Direction set by FII response next day | Intraday |
| **Global Crisis** (war, pandemic) | VIX spike > 25-30, gap downs | Wait for VIX > 25 | Buy Nifty when VIX crosses back below 20 | Positional |

**MSCI Feb 2026 example**: $260M withdrawn from India. Aditya Birla Capital and L&T Finance added (attracted $257M and $241M respectively). IRCTC excluded ($142M outflow).

**Data sources**:
- RBI calendar: `https://www.rbi.org.in` (published annually)
- MSCI rebalancing: `https://www.msci.com/index-reviews` (quarterly announcements)
- Results calendar: MoneyControl, Trendlyne (free)

---

## 5. Small/Mid-Cap Momentum

**Edge**: BSE SmallCap outperforms Nifty 50 in bull markets by 2-3x, then crashes 40-60% in corrections. Rotation timing is the alpha.

| Signal | Action | Evidence |
|--------|--------|----------|
| SmallCap/Nifty50 ratio rising + FII buying | Overweight small-caps | 2023-2024 rally phase |
| SmallCap/Nifty50 ratio falling + VIX > 18 | Rotate to large-caps | Feb 2025 correction |
| MF SIP flows hitting record highs | Floor under mid/small (structural bid) | SIP at 29,361cr/month (Sep 2025) |
| Thematic fund NFO launches accelerating | Top signal -- excess retail enthusiasm | Late 2024 peak |
| SEBI tightening MF small-cap exposure rules | Forced selling ahead | SEBI stress test circular 2024 |

**MF flow data (2025)**:
- Small-cap fund inflows: record 6,484cr/month (Jul 2025)
- Mid-cap fund inflows: record 5,331cr/month (Aug 2025)
- Total MF AUM: 65.74 lakh crore (Mar 2025), up 23% YoY
- SIP accounts: 9.45 crore (Oct 2025)

**Data sources**:
- AMFI monthly data: `https://www.amfiindia.com/research-information/amfi-monthly` (free, PDF/Excel)
- BSE SmallCap index: BSE website
- MF category flows: Value Research, Morningstar India (free)

---

## 6. Delivery Percentage (NSE-Specific)

**Edge**: High delivery % (>50% for large-caps, >40% for mid-caps) with rising price = institutional accumulation. Low delivery (<20%) with rising price = intraday speculation (unsustainable).

| Pattern | Signal | Action |
|---------|--------|--------|
| Delivery % > 60% + price up 3%+ | Strong institutional buying | Buy for swing/positional |
| Delivery % > 60% + price down 3%+ | Institutional distribution | Avoid or short |
| Delivery % < 20% + price up sharply | Intraday speculation only | Do NOT buy for delivery |
| Delivery % rising over 5 days + price consolidating | Accumulation before breakout | Watch for volume breakout |
| Sudden spike in delivery (2x avg) + block/bulk deal | Insider/PE activity | Investigate corporate action |

**Data sources**:
- NSE Security-wise delivery: `https://www.nseindia.com/report-detail/eq_security` (free, daily CSV)
- Python: `NseIndiaApi` -- `deliveryBhavcopy(date)` returns full delivery data
- Bulk/Block deals: NSE website under Market Activity section

---

## 7. India VIX Patterns

**Edge**: India VIX is strongly mean-reverting. Normal range: 13-17. Extremes signal reversals.

| VIX Level | Market State | Strategy |
|-----------|-------------|----------|
| < 11 | Extreme complacency | Buy puts (cheap protection), reduce equity | 
| 11-14 | Low vol, trending market | Sell options (premium collection), momentum trades |
| 14-18 | Normal range | No vol edge, use other signals |
| 18-22 | Elevated fear | Start buying equities in tranches |
| > 25 | Panic / crisis | Aggressive buy on Nifty, sell puts |
| > 30 | Extreme panic (rare) | Back up the truck -- buy aggressively |

**Key patterns**:
- VIX spikes before RBI policy, Budget, elections -- then crushes post-event
- VIX and Nifty have strong negative correlation (statistically significant per academic studies)
- When VIX > 20, shift mid-cap allocation to large-cap
- When VIX < 14, shift large-cap to mid-cap (risk-on)
- VIX crush after events = sell straddles/strangles on event day

**Data sources**:
- India VIX historical: NSE website (free, daily)
- Live VIX: `https://www.nseindia.com/market-data/india-vix` (free)
- Python: `jugaad-data` or `nsefin` for historical VIX

---

## 8. Pre-Market & GIFT Nifty Gap Prediction

**Edge**: GIFT Nifty (formerly SGX Nifty) trades 21 hours/day. The gap between prev Nifty close and GIFT Nifty at 9:00 AM predicts opening direction with ~75% accuracy.

| Signal | Interpretation | Strategy |
|--------|---------------|----------|
| GIFT Nifty premium > 0.3% at 9:00 AM | Gap-up opening likely | Buy at open if trend-following |
| GIFT Nifty discount > 0.3% at 9:00 AM | Gap-down opening likely | Sell at open or buy puts |
| GIFT Nifty flat (within 0.1%) | No gap, range-bound likely | Wait for first 15-min candle |
| Pre-market (9:00-9:15) order book imbalance | Strong directional bias | Trade in direction of imbalance |
| GIFT Nifty diverges from US close direction | Domestic factor overriding | Watch for reversal intraday |

**Limitations**: Thin overnight volume can distort GIFT Nifty. Domestic news (RBI, govt policy) can override gap direction within first 30 minutes.

**Data sources**:
- GIFT Nifty live: `https://www.nseix.com` (official) or TradingView chart `NSEIX:NIFTY1!`
- NSE pre-market data: Available at 9:00 AM on NSE website
- Python: TradingView webhooks or websocket feeds

---

## 9. Mutual Fund Flow Data

**Edge**: MF flows are the structural floor under Indian markets. Monthly AMFI data reveals sector rotation by institutional India. SIP flows now > 26,000cr/month = consistent demand.

| Signal | Interpretation | Horizon |
|--------|---------------|---------|
| SIP flows declining MoM for 3+ months | Retail fatigue, market top signal | Positional |
| New thematic fund launches clustering | Sector is overhyped, likely top | Positional |
| Small-cap fund outflows | Smart money rotating out, follow | Swing |
| Large-cap fund inflows rising | Flight to safety, defensive mode | Investment |
| Total equity inflow negative (rare) | Capitulation, bottom signal | Investment |

**Data sources**:
- AMFI monthly: `https://www.amfiindia.com/research-information/amfi-monthly` (free, 7-10 days post month-end)
- SIP data: AMFI monthly reports (Excel download)
- Category-wise flows: Value Research Online (free)

---

## Data Source Master Table

| Data Type | Source | Format | Frequency | Cost | Python Library |
|-----------|--------|--------|-----------|------|---------------|
| FII/DII cash activity | NSE | CSV/JSON | Daily (EOD) | Free | `nsefin` |
| FII/DII F&O activity | NSE | CSV | Daily (EOD) | Free | `nsefin` |
| Participant-wise OI | NSE archives | CSV | Daily (5-6 PM) | Free | `nsepython` |
| Option chain (live) | NSE | JSON | Real-time | Free | `nsepython` |
| Equity bhavcopy | NSE | CSV | Daily (EOD) | Free | `jugaad-data`, `NseIndiaApi` |
| Delivery bhavcopy | NSE | CSV | Daily (EOD) | Free | `NseIndiaApi` |
| F&O bhavcopy | NSE | CSV | Daily (EOD) | Free | `jugaad-data` |
| India VIX historical | NSE | CSV | Daily | Free | `jugaad-data` |
| GIFT Nifty | NSE IX / TradingView | Real-time | Continuous | Free | TradingView API |
| MF flows (AMFI) | AMFI website | PDF/Excel | Monthly | Free | Manual download |
| FPI sector-wise flows | NSDL | Excel | Monthly | Free | Manual download |
| MSCI rebalancing | MSCI website | PDF | Quarterly | Free | Manual parse |
| Bulk/block deals | NSE | CSV | Daily | Free | `NseIndiaApi` |
| Stock fundamentals | Screener.in | JSON | Quarterly | Free (basic) | Apify scraper |
| Technicals + screener | Trendlyne | Web | Real-time | Rs 119/mo | No official API |

### Key Python Packages

```
pip install nsefin jugaad-data nsepython bhavcopy
```

| Package | Best For | Maintained |
|---------|----------|-----------|
| `nsefin` | FII/DII data, option chain with Greeks, bhavcopy | Yes (2025) |
| `jugaad-data` | Historical stock/index data, F&O bhavcopy, caching | Yes |
| `nsepython` | Live option chain, OI data, NSE reports | Yes |
| `NseIndiaApi` | Delivery bhavcopy, equity data, corporate actions | Yes |
| `bhavcopy` | Simple bhavcopy downloader | Basic |

### NSE API Endpoints (Unofficial, may change)

```
Base: https://www.nseindia.com/api/

Option chain:    /option-chain-indices?symbol=NIFTY
Quote equity:    /quote-equity?symbol=RELIANCE
Quote derivative:/quote-derivative?symbol=BANKNIFTY
Market status:   /marketStatus
FII/DII:         /reports/fii-dii  (report page, not direct API)
```

**Note**: NSE blocks direct API access without proper cookies/session. Use the Python libraries above which handle session management.

---

## TradePilot v5 Implementation Priority

| Edge | Effort | Alpha Potential | Recommended Horizon | Priority |
|------|--------|----------------|---------------------|----------|
| GIFT Nifty gap prediction | Low | Medium | Intraday | P0 |
| India VIX regime detection | Low | High | All horizons | P0 |
| FII/DII flow tracking | Medium | High | Swing + Positional | P0 |
| Delivery % signals | Medium | Medium | Swing | P1 |
| F&O expiry patterns | Medium | Medium | Intraday + Swing | P1 |
| Sector rotation model | High | High | Positional + Investment | P1 |
| Event calendar (RBI/Budget/MSCI) | Low | Medium | Event-driven | P2 |
| MF flow analysis | Low | Low-Medium | Investment | P2 |
| Small/mid-cap momentum | Medium | High (but risky) | Positional | P2 |
