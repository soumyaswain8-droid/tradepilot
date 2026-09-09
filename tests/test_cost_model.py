"""M0 WP-1 -- pool-aware cost model in scripts/v5-paper-trade.py.

INTRADAY must stay byte-identical to the pre-2026-09-10 formula (12 bps of average
notional) so intraday history remains comparable; multi-day pools must charge the
Zerodha delivery round trip.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_SCRIPT = REPO_ROOT / "scripts" / "v5-paper-trade.py"


@pytest.fixture(scope="module")
def cost_for_trade():
    # The script has a __main__ guard, so exec'ing the module only defines things.
    # Its import-time side effect is mkdir(exist_ok=True) on docs/paper-trades/<ENGINE_NAME>
    # and logs/, so ENGINE_NAME is pinned to an existing ledger dir: nothing new is created.
    os.environ["ENGINE_NAME"] = "v5"
    # The script imports dp_creds as a sibling module (scripts/ is sys.path[0] when run directly).
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    os.environ.setdefault("COST_BPS_ROUND_TRIP", "12")
    spec = importlib.util.spec_from_file_location("v5_paper_trade_under_test", ENGINE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.cost_for_trade


# Fixed trade: 10 shares, bought at 1000, sold at 1010.
QTY, ENTRY, EXIT = 10, 1000.0, 1010.0


def old_intraday_formula(qty, entry, exit_):
    """The pre-change body of cost_for_trade, verbatim."""
    notional_avg = qty * (entry + exit_) / 2
    return notional_avg * (12 / 10000)


def test_intraday_cost_equals_old_formula(cost_for_trade):
    assert cost_for_trade(QTY, ENTRY, EXIT, pool="INTRADAY") == old_intraday_formula(QTY, ENTRY, EXIT)
    assert cost_for_trade(QTY, ENTRY, EXIT, pool="INTRADAY") == pytest.approx(12.06)


def test_pool_default_is_intraday(cost_for_trade):
    assert cost_for_trade(QTY, ENTRY, EXIT) == cost_for_trade(QTY, ENTRY, EXIT, pool="INTRADAY")


def test_unknown_pool_falls_back_to_intraday(cost_for_trade):
    assert cost_for_trade(QTY, ENTRY, EXIT, pool="WHATEVER") == old_intraday_formula(QTY, ENTRY, EXIT)


def test_swing_cost_matches_hand_computed_delivery_schedule(cost_for_trade):
    # Zerodha equity delivery, spec decision 2. Hand arithmetic:
    buy_value = QTY * ENTRY          # 10,000.00
    sell_value = QTY * EXIT          # 10,100.00
    turnover = buy_value + sell_value  # 20,100.00
    brokerage = 0.0                                   # delivery brokerage is zero
    stt = 0.001 * buy_value + 0.001 * sell_value      # 10.00 + 10.10      = 20.10
    exchange = 0.0000297 * turnover                   # 20,100 x 0.00297%  = 0.59697
    sebi = 0.000001 * turnover                        # 20,100 x 0.0001%   = 0.0201
    stamp = 0.00015 * buy_value                       # 10,000 x 0.015%    = 1.50
    gst = 0.18 * (brokerage + exchange + sebi)        # 18% of 0.61707     = 0.1110726
    dp_charge = 15.34 * 1.18                          # Rs 15.34 + 18% GST = 18.1012
    expected = round(brokerage + stt + exchange + sebi + stamp + gst + dp_charge, 2)
    assert expected == 40.43                          # 40.4293426 -> 40.43
    assert cost_for_trade(QTY, ENTRY, EXIT, pool="SWING") == expected


@pytest.mark.parametrize("pool", ["SWING", "POSITIONAL", "INVESTMENT"])
def test_all_multi_day_pools_use_delivery_schedule(cost_for_trade, pool):
    assert cost_for_trade(QTY, ENTRY, EXIT, pool=pool) == 40.43


def test_delivery_cost_is_rounded_to_two_dp(cost_for_trade):
    c = cost_for_trade(37, 3290.2, 3185.7, pool="SWING")
    assert c == round(c, 2)
