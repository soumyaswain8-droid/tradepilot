"""
prototype.v10 — frozen April-2026 signal path for engine v10.

Contains ONLY the two modules that drifted between April (git 9d7db34) and today:
  signal_engine.py  259 lines  (+51 since April)  — what to buy
  risk_manager.py   595 lines  (+194 since April) — how much

The other six modules on the April signal path are byte-identical to today
(regime_detector, premarket_intel, pool_manager, comparator, alpha_hunter,
telegram_bot's alert surface), so v10 imports those from prototype.v5 rather
than duplicating them. Verified by sha1 on 2026-07-29.

DO NOT EDIT. These files are a frozen experimental control. If they change,
v10 stops being a test of the April recipe.
"""
