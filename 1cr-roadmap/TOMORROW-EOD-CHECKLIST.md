# Tomorrow after EOD — what to check

**For 2026-08-11, after 15:30.** Replaces the open decision items. Every line has a
command and a pass condition, so "we checked" means something.

---

## 1. Did the guards actually fire? (highest priority)

Three guards shipped today and **none of them has ever run in a live session** — the
engines were already running with the old code loaded. Tomorrow is their first real
test. A guard that silently fails is worse than no guard.

::: {.checklist}

| | Check | Pass condition |
|:---:|:--|:--|
| ☐ | **SESSION-GUARD** — no engine entered before 09:15 | `grep -h "entry_time" docs/paper-trades/*/2026-08-11.json` shows nothing before 09:15. v10 and v5_classic especially — they had no guard at all today and v10 bought 19 positions at 08:53. |
| ☐ | **Disk headroom gate** — preflight ran it | `grep "free disk" docs/team/standup/2026-08-11_preflight.md` shows the check present and PASS. If the disk was under 5 GB the fleet should NOT have launched. |
| ☐ | **No `Errno 28` anywhere** | `grep -l "No space left" logs/*2026-08-11.log` returns nothing. 11 engines hit it today. |
| ☐ | **Telegram per-trade alerts stayed off** | No `🟢 v5 BUY <symbol>` messages. `alert_entries`/`alert_exits` are false in `prototype/v5/telegram_config.json`. |

:::

**If SESSION-GUARD did not fire:** the change didn't take effect. Check the engines
reloaded the file (they only pick up edits on relaunch).

---

## 2. v5_size — day 2 of the position-size experiment

The one experiment actually running. Day 1: median ₹108,623, 10 closed trades,
net +₹3,430, but **t=0.76 — not significant**. Needs ~300 trades, roughly 6 weeks.

::: {.checklist}

| | Check | Pass condition |
|:---:|:--|:--|
| ☐ | Median position still **above ₹66,667** | If it drops below, the experiment stopped happening and the day's data is void. |
| ☐ | Fee rate ≈ **0.079%** vs v5's 0.106% | This is the structural part and it must hold every day. |
| ☐ | Cumulative trade count | Track toward 300. At ~10/day that is day 2 of ~30. |
| ☐ | Net per trade **as a percentage**, not rupees | Rupee P&L is 15× larger by construction. Only the % comparison means anything. |
| ☐ | Any single trade >50% of the day's P&L? | Day 1 was 69% one trade (BSE +₹2,383). Flag it — it is noise, not edge. |

:::

**Do not conclude anything from 2 days.** The fee saving is proven; the profit
difference is not, and will not be for weeks.

---

## 3. Mean reversion — CLOSED 2026-08-10, no action needed

Ran the same evening on 6,600 setups across 201 symbols. The pre-registered gate
failed and **L3 has been deleted from the spec**. Nothing to check tomorrow; recorded
here so it is not re-opened from memory.

| Variant | n | net after cost | t |
|:--|--:|--:|--:|
| with daily bias | 6,600 | -0.0964% | -11.66 |
| against daily bias | 6,600 | -0.0277% | **-3.22** |
| fade >= 2% move | 3,861 | +0.0153% | 1.32 |
| RISK_OFF only | 2,649 | -0.0170% | -1.19 |

**True but not tradeable:** fading beats following (+0.0510% vs -0.0177% gross,
+0.0701% vs random). The market mean-reverts intraday; the reversion is smaller than
the fee. Fourth family to land in the same place.

**The lesson worth carrying:** a 30-symbol smoke run showed edge rising monotonically
with fade depth (+0.0119% -> +0.0510% -> +0.0783%) and was reported as promising. At
full sample the curve is flat and insignificant — the gradient was noise off samples
as small as 116. **Never act on, or report, a smoke run.**

## 4. Data integrity — today's numbers were partly compromised

::: {.checklist}

| | Check | Pass condition |
|:---:|:--|:--|
| ☐ | All 200 symbols priced | `grep "Batch quotes" logs/v5-2026-08-11.log` shows 200/200. Today degraded to 160/200. |
| ☐ | `positions_active.json` written through to 15:30 | Today v5_size stopped at 14:36 because the disk was full, which made open positions look closed. |
| ☐ | Closed + open reconciles against `summary.trades` | Today CHOLAFIN was open with +₹1,091 unrealised and appeared in neither of my first two checks. |
| ☐ | No engine wrote a `.tmp` it could not rename | `ls docs/paper-trades/*/.*tmp*` returns nothing. |

:::

---

## 5. v10 — decide its status

v10 entered 19 positions at 08:53 on Friday's closing prices, lost **−₹1,920**, and
tripped the SWING circuit breaker (5 consecutive losses), which then blocked **57**
further signals.

::: {.checklist}

| | Check | Action |
|:---:|:--|:--|
| ☐ | Did the new session guard stop it repeating? | See §1. |
| ☐ | Is the SWING breaker still latched from today? | If it carries over, v10 starts tomorrow already blocked and its day is meaningless again. |
| ☐ | Exclude today's v10 from any comparison | Its fills are fictional. Report it separately or not at all. |

:::

---

## 6. Standing numbers to update

| Metric | 2026-08-10 | Tomorrow |
|:--|--:|:--|
| Fleet net (modelled fees) | +₹12,102 | |
| Closed trades | 765 | |
| Best engine | v5_size +₹3,430 | |
| Worst engine | v10 −₹1,096 | |
| v5_size median position | ₹108,623 | |
| v5 median position | ₹7,989 | |
| v5_size cumulative trades | 10 | (target 300) |

---

## What NOT to do tomorrow

- **Do not read 2 days of v5_size as proof.** t=0.76 today.
- **Do not conclude from the gainers list.** Selecting stocks that went up and then
  judging exits is hindsight; it produced a wrong "SIGNAL_FLIP is the culprit" call
  today that the full 332-exit sample overturned.
- **Do not build the 50-agent fleet.** The week-1 gate killed that thesis; the spec
  stands as a design, not a plan.
- **Do not touch v5.** It is the control. Its value is that nothing changes in it.
