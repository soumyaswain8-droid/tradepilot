# EOD 2026-08-17 — the left-on-the-table autopsy

Fleet **−₹14,995 net** on 675 trades (gross −₹7,603, fees ₹7,392). Red Monday: only
3 engines green, control v5 worst (−₹2,499). v5_size −₹1,732, median ₹80,614
(above cliff ✓, day 6, 86/300).

## Money left, decomposed — three buckets that must not be summed

| Bucket | ₹ | What it is |
|:--|--:|:--|
| A. In-trade MFE ceiling | 38,178 | Best price ever held vs realized. **Hindsight ceiling** — nobody exits at the peak. |
| B. Post-exit drift | **−4,061** | What the move did after we left. NEGATIVE = exits *saved* money today. |
| C. Cap-blocked entries (v5_size) | +34,233 | 110 refused signals held to EOD on ₹110k slots — **uncapitalized counterfactual**, not a loss. |

## A. The real giveback: winners that round-tripped to stops

Of the ₹38k ceiling, **₹23,629 sits inside the 168 STOPLOSS trades** — positions that
were in profit at their peak and rode all the way down through their stop.
Why: stops are fixed-% and the trailing stop arms only at +1.0%; on a whipsaw day
price tags +0.6–0.9%, never arms the trail, then reverses through the full stop.
The band between "profitable" and "trail armed" is where ₹23.6k evaporated.

## B. Exits were NOT the leak today

Post-exit drift is net −₹4,061: after we exited, prices moved *against* our old
direction. STOPLOSS exits alone dodged a further ₹4,278 of decline — on a falling
tape the stop machinery did its job. Best save: NMDC short stopped at 10:09, dodged
₹1,668. The 08-10 finding (SIGNAL_FLIP mildly early, +0.12% median drift) did not
repeat on a red day — flips were +₹496 net drift, noise.

## C. The cap counterfactual — optionality, not loss

v5_size refused 110 signals on "Max 5 positions". Held to EOD on a ₹110k slot each,
they net +₹34,233 (NMDC +5.0%, SUZLON +3.4%). Caveats that keep this honest: no
stops, no slippage, and **108 slots of capital we do not have** — the cap *is* the
capital. The actionable piece is not "raise the cap": it is that **slots fill
first-come at 09:35–09:36**, so NMDC (blocked 09:36, best candidate of the day) lost
to whatever fired one scan earlier. Slot selection is by arrival, not by score.

## D. Coverage

The scorer's own artifact: 62 BUY signals at open, **52 entered by no engine** (16%
coverage). Fleet breadth remains a fraction of its own signal list.

## What is actionable (for research, not for shipping tomorrow)

1. **Trail-arm band**: measure across history what a lower arm threshold (e.g. 0.5%)
   or ATR-scaled trail does to the ₹23.6k-class giveback vs added whipsaw stops.
   Harness exists; falsification gate applies.
2. **Score-ordered slot fill**: one line of sort before deploy — but test first
   whether early arrivals actually underperform later high scores.
3. Coverage (D) is the old universe/caps question — parked behind the size
   experiment; one experiment at a time.
