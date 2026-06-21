# Preflight — 2026-05-19

_Generated 2026-05-19 08:50:15_  ·  exit=0

```
[36m═══════════════════════════════════════════════════════[0m
[36m  Monday Self-Test — 2026-05-19 08:50:05[0m
[36m═══════════════════════════════════════════════════════[0m

[36m— 1. macOS power schedule —[0m
  [32m✓[0m pmset wake schedule for weekdays             

[36m— 2. launchd jobs (10 expected) —[0m
  [32m✓[0m launchd: com.tradepilot.v2.preflight loaded  
  [32m✓[0m launchd: com.tradepilot.v2.dqo-premarket loaded
  [32m✓[0m launchd: com.tradepilot.v2.engines-on loaded 
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
  [32m✓[0m MLOps IC gate allows current model (CEO override active)
  [32m✓[0m CEO override has not expired                 

[36m— 6. Team infrastructure —[0m
  [32m✓[0m scripts/team/log.py imports + smoke          
  [32m✓[0m scripts/sarathi/verify.py imports            
  [32m✓[0m team Flask routes (5 routes) registered      

[36m— 7. Data feed pre-warm —[0m
  [33m~[0m nifty50_quotes_batch.json present (warms up post-09:00) [33mWARN[0m
      

[36m— 8. cron is CLEAN (we use launchd now) —[0m
  [32m✓[0m no TRADEPILOT cron block                     

[36m— 9. Pending LLM-agent tasks —[0m
    1 pending LLM-agent task(s):
      - architect            marked 2026-05-17T19:05:05+05:30: Sprint review + next week planning

[36m═══════════════════════════════════════════════════════[0m
  [32mPASS: 27[0m   [33mWARN: 1[0m   [31mFAIL: 0[0m   (total: 28)
[33mAll checks passed (with 1 warnings).[0m Safe to leave unattended.
[36m═══════════════════════════════════════════════════════[0m

```
