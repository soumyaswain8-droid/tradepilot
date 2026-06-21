"""
TradePilot v4 — Labels subpackage
==================================
Supervised-learning label generators for intraday setups.

Modules:
    triple_barrier  - López de Prado triple-barrier labels {+1, -1, 0}

The triple-barrier method (López de Prado, *Advances in Financial Machine
Learning*, Ch.3) replaces fixed-horizon return labels — which destroy
information content (IC) on retail intraday setups — with categorical
path-dependent labels:

    +1  take-profit barrier hit first
    -1  stop-loss barrier hit first
     0  vertical (time) barrier hit first  (timed out)

Reported to roughly halve drawdown on intraday equity vs fixed-horizon
labels (arXiv:2504.02249).
"""

from .triple_barrier import (
    Barriers,
    triple_barrier_label,
    triple_barrier_labels,
    DEFAULT_TAKE_PROFIT_PCT,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_VERTICAL_BARS,
)

__all__ = [
    "Barriers",
    "triple_barrier_label",
    "triple_barrier_labels",
    "DEFAULT_TAKE_PROFIT_PCT",
    "DEFAULT_STOP_LOSS_PCT",
    "DEFAULT_VERTICAL_BARS",
]
