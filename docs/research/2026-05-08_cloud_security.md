# TradePilot Cloud Security & Compliance Research
**Date:** May 8, 2026 | **Status:** Ready for Implementation  
**Scope:** Algorithmic intraday trading system (paper → real-money via Zerodha Kite Connect)

---

## 1. SEBI Compliance Framework (2025-26)

### Regulatory Status
- **Effective Date:** April 1, 2026 (SEBI Circular HO/MIRSD/P/2025/0000013)
- **Individual Trader Threshold:** ≤10 Orders Per Second (OPS) = NO exchange registration required
- **TradePilot Status:** Paper trading → real-money (currently under threshold)

### Current Requirements
| Item | Requirement | TradePilot Status |
|------|-------------|------------------|
| **Algo-ID (Exchange)** | All orders must carry algo identifier | Required on Day 1 (real-money) |
| **Registration** | Not required if <10 OPS | Compliant (targeting ~2-4 OPS) |
| **Static IP** | Mandatory (from April 1, 2026) | Action Item: Register public IP with Zerodha |
| **2FA Authentication** | Required daily login | Action Item: Implement auth at startup |
| **Strategy Submission** | Not required for <10 OPS retail traders | Not applicable |
| **Audit Logs** | Retain for 5 years minimum | Action Item: Enable persistent logging |

### Deadline Checklist
- [x] Understand <10 OPS threshold (2-4 OPS target = safe)
- [ ] Register static public IP with Zerodha by March 31, 2026
- [ ] Implement 2FA startup auth flow
- [ ] Configure 5-year audit trail retention

---

## 2. Zerodha Kite Connect Security Requirements

### Production API Access Constraints
1. **Static IP Whitelisting**
   - Required for order placement (from April 1, 2025)
   - Non-order endpoints (positions, orders, holdings) open to any IP
   - Max 1 IP whitelist update per week
   - Supports IPv4 and IPv6

2. **Token Management**
   - AccessToken: short-lived (day-of-session)
   - RefreshToken: persistent (store in encrypted DB)
   - Automatic renewal on session expiry
   - Never store AppSecret in client code or git

3. **Session Lifecycle**
   - Login → AccessToken issued
   - Daily refresh via RefreshToken
   - Pre-market session start (09:00 IST)
   - Force logout post-market (15:30 IST)

### Implementation for TradePilot
```python
# Pseudo-code: Kite token management
AccessToken = encrypted_store.get("kite_access_token")
if expired or None:
    RefreshToken = encrypted_store.get("kite_refresh_token")
    AccessToken = kite.refresh(RefreshToken)
    encrypted_store.set("kite_access_token", AccessToken)
    encrypted_store.set("token_expires_at", expiry_time)
```

---

## 3. Threat Model: TradePilot Cloud Deployment

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| **API Key Exposure** (Kite secret in logs/git) | Medium | Critical | Secrets Manager (AWS/Doppler), env vars, git pre-commit hooks |
| **Unauthorized Order Placement** (auth bypass) | Medium | Critical | JWT + 2FA, rate limits per endpoint, IP whitelisting |
| **Session Hijacking** (token theft) | Medium | High | HTTPS only, HttpOnly cookies, daily token rotation |
| **DDoS on /api/scores** | Low | Medium | Cloudflare rate limiting, 429 responses, WAF rules |
| **Malicious Commits** (bad code to prod) | Low | Critical | Git pre-commit hooks, CI/CD gates, canary deploys |
| **Stale Session Post-Market** | High | Medium | Force logout at 15:35 IST, validate timestamps |
| **Data Exfiltration** (trades, PII) | Low | High | Encryption at rest (AES-256), in-transit (TLS 1.3), audit logs |
| **Regime Flip During Trade** | Medium | High | Real-time market regime check, kill-switch circuit breaker |
| **Cloud Provider Outage** (Render/Railway) | Low | Critical | Failover to laptop, manual trading, DBaaS replication |
| **Insider Threat** (developer commits malicious engine changes) | Low | Critical | Code review + approval gate before market hours, canary deploy |

---

## 4. OWASP Top 10 Mitigations for Flask App

### Current API Endpoints & Risks
- **Read-only:** `/api/scores`, `/api/compare-v4`, `/api/engine-status`, `/api/system-health`
- **Write (Paper):** `/api/paper/buy`, `/api/paper/sell`
- **Future:** `/api/kite/order`, `/api/kite/cancel` (real-money)

### Top 10 Vulnerabilities & Fixes

| OWASP Risk | Current Status | Mitigation |
|-----------|----------------|-----------|
| **A01: Broken Access Control** | ⚠️ No auth on /api/scores | Add JWT bearer token + role-based access (RBAC) |
| **A02: Cryptographic Failure** | ⚠️ Kite secret in ENV only | Use AWS Secrets Manager + KMS encryption |
| **A03: Injection** | ✓ No SQL (JSON responses only) | Validate all query params (Flask-WTF validators) |
| **A04: Insecure Design** | ⚠️ No rate limiting | Implement Flask-Limiter (10 req/sec per IP) |
| **A05: Broken Authentication** | ⚠️ Stateless (no 2FA yet) | Add Kite 2FA + JWT expiry (15 min) |
| **A06: Vulnerable Components** | ⚠️ Pin dependencies | Weekly dependabot scans, no unpatched flask/requests |
| **A07: Auth/Session Mgmt** | ⚠️ No explicit logout | Implement /api/logout → blacklist JWT + kill Kite session |
| **A08: Data Integrity Failure** | ⚠️ Orders not cryptographically signed | Append HMAC-SHA256(order_data, secret) to each trade record |
| **A09: Logging/Monitoring** | ⚠️ Minimal logs | Centralize to CloudWatch + set alerts on failed orders |
| **A10: SSRF** | ✓ No external requests | Keep internal (Kite is partner, not SSRF risk) |

### Priority Authentication Model
```python
# Flask-JWT-Extended setup
@app.before_request
def validate_token():
    if request.endpoint.startswith('api_') and not request.endpoint.startswith('api_health'):
        token = request.headers.get('Authorization', '').split()[-1]
        if not token or not verify_jwt(token):
            return jsonify({"error": "Unauthorized"}), 401
        g.user_id = decode_jwt(token)['sub']
```

---

## 5. Secrets Management: Recommendation

### Comparison (Effort vs. Security)
| Tool | Cost | Setup Time | Rotation | Best For |
|------|------|-----------|----------|----------|
| **Env Vars Only** | Free | 5 min | Manual | Dev-only, NOT production |
| **Doppler** | Free tier / $10/mo | 15 min | Automatic | Cloud-first, easy CI/CD |
| **AWS Secrets Manager** | $0.40/secret/mo | 30 min | Automatic | AWS-native, Render integration |
| **HashiCorp Vault** | Self-hosted / Cloud | 2-4 hrs | Full control | Enterprise, multi-cloud |

### Recommended: **Doppler** (sweet spot for one-person ops)
- Free tier: 5 secrets per project
- Auto-rotation of Kite AccessToken
- GitHub/Render integration via webhooks
- Audit trail of all secret access
- No infrastructure to manage

**Setup:** `doppler run -- python app.py` (injects secrets at runtime)

---

## 6. Network Security Architecture

### Current: Public Flask (Risky for Real-Money)
```
User Browser → https://tradepilot.onrender.com → Flask → Kite API
```
**Problem:** Every authenticated user can reach /api/paper/buy.

### Recommended: VPN + IP Whitelisting
```
User (via VPN/IP whitelist) → https://tradepilot.onrender.com → Flask (Kite-only orders)
                                         ↓
                              Kite API (static IP whitelisted)
```

**Steps:**
1. Register owner's public IP (or corporate VPN exit) with Zerodha
2. Implement IP whitelist in Flask middleware: `if request.remote_addr not in ALLOWED_IPS: abort(403)`
3. For travel: use personal VPN, update Zerodha IP once/week
4. Disable CORS except for whitelisted domain (remove `https://tradepilot.onrender.com` from wildcard)

---

## 7. Encryption Strategy

### At Rest
- **State Files** (pickle, json trade records): AES-256-GCM via cryptography lib
- **Logs** (daily EOD reports): Encrypted at write time, plaintext in-memory only
- **ML Models** (pickle, .pkl): Encrypt if sensitive; degrades inference speed <1%

### In Transit
- **Flask ↔ Browser:** TLS 1.3 (Render auto-provisions SSL cert)
- **Flask ↔ Kite:** Zerodha enforces TLS; always use https://api.kite.trade
- **Flask ↔ DB:** If RDS/Postgres: enforce SSL mode=require
- **Yahoo/NSE data:** HTTPS only, no raw socket fallbacks

### Implementation (Python)
```python
from cryptography.fernet import Fernet
key = os.environ['ENCRYPTION_KEY']  # store in Doppler
cipher = Fernet(key)
encrypted_order = cipher.encrypt(json.dumps(order_dict).encode())
# Store encrypted_order in DB
```

---

## 8. Audit Logging & Compliance

### SEBI Requirement: 5-Year Retention, Tamper-Proof

| Event | Format | Retention | Storage |
|-------|--------|-----------|---------|
| **Trade Orders** | `{timestamp, symbol, qty, price, side, status, exec_price}` | 5 years | CloudWatch Logs + S3 (Glacier after 6 months) |
| **API Calls** | `{user, endpoint, method, status, ip, user_agent}` | 2 years | CloudWatch Logs |
| **Secrets Access** | `{timestamp, secret_name, accessed_by, result}` (Doppler audit) | 1 year | Doppler dashboard |
| **Failed Auth** | `{timestamp, ip, endpoint, error_code}` | 1 year | CloudWatch Logs + alerts |

### Setup
```bash
# CloudWatch Logs retention policy
aws logs put-retention-policy --log-group-name tradepilot-app \
  --retention-in-days 1825  # 5 years
# S3 Archive (after 90 days)
aws logs create-export-task --log-group-name tradepilot-app \
  --from $(date -d '90 days ago' +%s)000 --to $(date +%s)000 \
  --destination tradepilot-archive-bucket --destination-prefix logs/
```

---

## 9. Backup & Disaster Recovery

### Scenario: Render Outage During Market Hours

| Phase | Action | RTO | RPO |
|-------|--------|-----|-----|
| **Detection** (Render down) | CloudWatch alert → SMS | <2 min | N/A |
| **Failover** | Manual: Pull latest state from S3, run on laptop | 5 min | 1 min (last backup) |
| **Resume** | Redeploy to Render once recovered OR continue on laptop | Variable | 0 (in-memory state syncs) |

**Implementation:**
```bash
# Pre-market (09:00 IST): Backup latest state
aws s3 cp tradepilot/state/ s3://tradepilot-backup/state-$(date +%s)/ --recursive

# Emergency (laptop):
aws s3 sync s3://tradepilot-backup/state-LATEST . && python app.py --local-mode
```

**Caveat:** Real-money orders CANNOT be placed from non-whitelisted IP. Failover to laptop = paper trading only until IP whitelist is updated (1 week max).

---

## 10. Penetration Testing & Vulnerability Scans

### Free Tools: OWASP ZAP (Recommended)
```bash
# Baseline scan (automated, 10 min)
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://tradepilot.onrender.com \
  -r baseline-report.html

# Full scan with OpenAPI spec (if available)
zap-cli scan --openapi openapi.json https://tradepilot.onrender.com
```

### CI/CD Integration (Before Prod Deploy)
Add to GitHub Actions:
```yaml
- name: OWASP ZAP Scan
  run: |
    docker run -v $(pwd):/zap -t owasp/zap2docker-stable \
      zap-baseline.py -t https://staging.tradepilot.onrender.com
```

### Burp Suite Community (Manual)
- Free version: sufficient for one-person audit
- Passive scanning only (no active payload injection)
- Good for API endpoint discovery

**Recommendation:** Run ZAP baseline before each production deploy (takes <15 min).

---

## 11. Insider Threat / Bad Commits Mitigation

### Risk: Developer commits malicious engine code (e.g., hidden short orders)

### Gates (Prevent Deploy to Prod)
1. **Pre-commit Hook** (git): Block secrets in code
   ```bash
   # .git/hooks/pre-commit
   git-secrets --scan || exit 1
   ```

2. **Code Review** (GitHub): Require 1 approval + green CI before merge
   ```yaml
   # Branch protection rule
   Require code review before merge
   Require status checks to pass before merge (ZAP scan + tests)
   ```

3. **Canary Deploy** (Render): Deploy to /staging first, manual smoke test
   ```bash
   # Render deployment pipeline
   Deploy to staging → manual test /api/engine-status → Deploy to prod
   ```

4. **Circuit Breaker** (Market hours): No deploys 09:15–15:30 IST
   ```python
   # At startup
   if 09:15 < now < 15:30:
       raise RuntimeError("Cannot deploy during market hours")
   ```

---

## 12. DDoS & Rate Limiting

### Public Endpoints Risk
- `/api/scores` could attract scrapers (1000s req/sec)
- No auth = anyone can hammer the endpoint

### Mitigation
1. **Rate Limiting** (Flask-Limiter)
   ```python
   limiter = Limiter(app, key_func=lambda: request.remote_addr)
   @app.route('/api/scores')
   @limiter.limit("10 per minute")  # 10 req/min per IP
   def get_scores():
       ...
   ```

2. **Cloudflare** ($20/mo for DDoS + WAF)
   - Block requests from non-India IPs (optional)
   - Cache /api/scores for 60s (reduce origin hits)
   - Rate limit by IP globally

3. **Response on Limit Exceeded**
   ```python
   @app.errorhandler(429)
   def ratelimit_handler(e):
       return jsonify({"error": "Rate limit exceeded"}), 429
   ```

---

## 13. Personal Data / DPDP Act 2023 Compliance

### Current Status
- **No user accounts yet** (paper trading is single-owner)
- If extended to family/friends → DPDP compliance triggered

### DPDP Act Key Points (Enforcement: May 13, 2027)
| Requirement | Compliance Action |
|-------------|------------------|
| **Privacy Notice** | Publish "We collect trading data for analytics" |
| **Consent** | Explicit opt-in for paper trading data collection |
| **Data Breach Notification** | Report within 72 hours if secrets/tokens exposed |
| **Data Retention** | Delete old trades after 5 years (or as specified) |
| **User Rights** | Allow users to request/delete their data |
| **DPO Appointment** | Not required for <9 employees (startup exempt) |
| **Penalties** | Up to ₹250 Cr for gross violations |

**Action:** If adding users, create `/privacy` page + consent flow (simple checkbox).

---

## Critical Security Tasks (Priority Order)

| Task | Effort | Impact | Timeline |
|------|--------|--------|----------|
| 1. **Register static IP with Zerodha + 2FA startup** | 30 min | Critical | Before real-money |
| 2. **Implement JWT auth on all /api endpoints** | 2 hrs | Critical | Week 1 |
| 3. **Setup Doppler secrets manager** | 1 hr | High | Week 1 |
| 4. **Enable HTTPS + disable CORS wildcards** | 30 min | High | Week 1 |
| 5. **Configure CloudWatch logging + 5-year retention** | 1 hr | High | Week 1 |
| 6. **Add Flask-Limiter (rate limits)** | 1 hr | High | Week 2 |
| 7. **Implement JWT logout + blacklist** | 1 hr | Medium | Week 2 |
| 8. **Add HMAC signing to trade records** | 1.5 hrs | Medium | Week 2 |
| 9. **Run OWASP ZAP baseline scan** | 30 min | Medium | Week 2 |
| 10. **Setup GitHub branch protection + code review gate** | 30 min | High | Week 1 |
| 11. **Implement market-hours deploy block** | 30 min | High | Week 2 |
| 12. **Create S3 backup + restore playbook** | 1 hr | Medium | Week 3 |

**Total Effort:** ~13 hours (phased over 3 weeks)  
**Cost:** Doppler free tier + Cloudflare $20/mo + CloudWatch ~$5/mo

---

## Cost Estimate (Annual)

| Component | Cost | Notes |
|-----------|------|-------|
| **Doppler (Free tier)** | $0 | 5 secrets max; upgrade $10/mo if needed |
| **Cloudflare Pro** | $240/yr | DDoS + WAF + caching |
| **AWS CloudWatch Logs** | $60/yr | ~1GB/month ingest + 5-year S3 archive |
| **AWS Secrets Manager** | $5/yr | 1 secret ($0.40/mo), only if not using Doppler |
| **GitHub Enterprise** (optional) | $231/yr | For org-level branch protection |
| **OWASP ZAP** | Free | Open-source, run locally |
| **Burp Suite Community** | Free | Manual testing only |
| **Total** | ~$300–600/yr | Lightweight for one-person team |

---

## Compliance Checklist

- [ ] SEBI: <10 OPS target confirmed (2-4 OPS safe)
- [ ] SEBI: Static IP registered with Zerodha (deadline: April 1, 2026)
- [ ] SEBI: Daily 2FA authentication at startup
- [ ] SEBI: 5-year audit trail in CloudWatch + S3
- [ ] Zerodha: AccessToken stored in Doppler (no plaintext)
- [ ] Zerodha: RefreshToken auto-renewal implemented
- [ ] Kite API: All secrets encrypted at rest
- [ ] OWASP: JWT auth on all write endpoints
- [ ] OWASP: Rate limiting (10 req/min per IP)
- [ ] OWASP: HTTPS + no CORS wildcards
- [ ] OWASP: Input validation (Flask-WTF)
- [ ] OWASP: No secrets in git (pre-commit hooks)
- [ ] OWASP: ZAP baseline scan passing
- [ ] DPDP Act: Privacy notice (if users added)
- [ ] DPDP Act: 72-hour breach notification process
- [ ] GitHub: Branch protection + code review gate
- [ ] Deploy: Canary deploy pipeline (staging first)
- [ ] Deploy: No market-hours deployments (09:15–15:30 IST)
- [ ] Backup: S3 state backup + restore playbook tested
- [ ] Logging: CloudWatch retention = 5 years for trades

---

## References

1. [SEBI Algo Trading Circular 2025](https://www.sebi.gov.in/)
2. [Zerodha Kite Connect API Docs](https://kite.trade/docs/connect/v3/)
3. [NSE Retail Algo Framework Circular](https://www.nseindia.com/)
4. [OWASP Top 10 2025](https://owasp.org/Top10/2025/)
5. [India DPDP Act 2023](https://www.meity.gov.in/)
6. [Flask Security Best Practices](https://flask-security-too.readthedocs.io/)
7. [OWASP ZAP Documentation](https://www.zaproxy.org/)
8. [AWS Secrets Manager Guide](https://docs.aws.amazon.com/secretsmanager/)
9. [Doppler Secrets Manager](https://www.doppler.com/)
10. [Cloudflare DDoS Protection](https://www.cloudflare.com/ddos/)

---

**Next Steps:**
1. Review this with legal counsel (if SEBI compliance is required)
2. Prioritize Tasks 1–5 before trading real money
3. Implement Tasks 6–12 over 3 weeks
4. Run ZAP scan before first production deploy
5. Store this document in version control (docs/research/)

