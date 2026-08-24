# Preflight — 2026-08-24

_Generated 2026-08-24 08:50:16_  ·  exit=1

```
[36m═══════════════════════════════════════════════════════[0m
[36m  Monday Self-Test — 2026-08-24 08:50:02[0m
[36m═══════════════════════════════════════════════════════[0m

[36m— 1. macOS power schedule —[0m
  [32m✓[0m pmset wake schedule for weekdays             


[36m— 1b. Disk headroom —[0m
  [31m✗[0m free disk >= 5 GB (session needs ~2 GB, engines write continuously) [31mFAIL[0m
      
  [33m~[0m free disk >= 15 GB (comfortable margin)       [33mWARN[0m
      
[36m— 2. launchd jobs (10 expected) —[0m
  [32m✓[0m launchd: com.tradepilot.v2.preflight loaded  
  [32m✓[0m launchd: com.tradepilot.v2.dqo-premarket loaded
  [31m✗[0m launchd: com.tradepilot.v2.engines-on loaded  [31mFAIL[0m
      
  [32m✓[0m launchd: com.tradepilot.v2.dqo-mid loaded    
  [32m✓[0m launchd: com.tradepilot.v2.exec-eod loaded   
  [32m✓[0m launchd: com.tradepilot.v2.standup loaded    
  [32m✓[0m launchd: com.tradepilot.v2.due-alpha-hunter loaded
  [32m✓[0m launchd: com.tradepilot.v2.due-competitive-intel loaded
  [32m✓[0m launchd: com.tradepilot.v2.due-architect loaded
  [32m✓[0m launchd: com.tradepilot.v2.bk-daily loaded   

[36m— 3. Sarathi rule catalog —[0m
  [32m✓[0m rule file SARATHI-LRN.md exists              
  [32m✓[0m rule file SARATHI-SPR.md exists              
  [32m✓[0m rule file SARATHI-ML.md exists               
  [32m✓[0m rule file SARATHI-CDE.md exists              
  [32m✓[0m rule file SARATHI-DAT.md exists              

[36m— 4. Engine scripts + entry points —[0m
  [32m✓[0m v4 paper-trade script + clean import         
  [32m✓[0m v5 paper-trade script + clean import         
  [32m✓[0m v5_classic paper-trade script + clean import 

[36m— 5. ML model + Sarathi gate —[0m
  [32m✓[0m live model file exists                       
  [32m✓[0m verification_report.json next to live model  
  [31m✗[0m MLOps IC gate allows current model (CEO override active) [31mFAIL[0m
      [mlops-gate] lgbm_intraday.txt: BLOCKED — Model BLOCKED. Blocking rules: ['ML-001']
  [31m✗[0m CEO override has not expired                  [31mFAIL[0m
      FAIL: override expired on 2026-07-25 (today=2026-08-24)

[36m— 6. Team infrastructure —[0m
  [32m✓[0m scripts/team/log.py imports + smoke          
  [32m✓[0m scripts/sarathi/verify.py imports            
  [32m✓[0m team Flask routes (5 routes) registered      

[36m— 7. Data feed pre-warm —[0m
  [33m~[0m nifty50_quotes_batch.json present (warms up post-09:00) [33mWARN[0m
      

[36m— 8. cron is CLEAN (we use launchd now) —[0m
  [32m✓[0m no TRADEPILOT cron block                     

[36m— 9. Pending LLM-agent tasks —[0m
    3 pending LLM-agent task(s):
      - alpha-hunter         marked 2026-08-21T16:00:05+05:30: Weekly IC + feature drift audit
      - architect            marked 2026-08-23T19:05:02+05:30: Sprint review + next week planning
      - competitive-intel    marked 2026-08-23T19:00:01+05:30: Weekly Qlib/FinRL/arxiv scan

[36m═══════════════════════════════════════════════════════[0m
  [32mPASS: 24[0m   [33mWARN: 2[0m   [31mFAIL: 4[0m   (total: 30)

[31mFailing checks:[0m
  - free disk >= 5 GB (session needs ~2 GB, engines write continuously)
  - launchd: com.tradepilot.v2.engines-on loaded
  - MLOps IC gate allows current model (CEO override active)
  - CEO override has not expired

[31mMonday morning launch is at RISK. Fix above before 08:55 IST.[0m

```
