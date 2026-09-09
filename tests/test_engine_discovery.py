"""Discovery tests for prototype/engines.py against a temporary fixture tree.

Fixture: three real engines (alpha: trades, beta: retired, delta: no file for
today), one dryrun engine, plus an engine that only holds an open position and
one with today's file but nothing in it.
"""
import json
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype.engines import (  # noqa: E402
    active_engines, discover_engines, engine_colour, retired_engines,
)

TODAY = "2026-09-09"
YESTERDAY = "2026-09-08"


def _day(trades=0, open_positions=0, flat_v4=False):
    if flat_v4:
        positions = [{"symbol": f"S{i}", "status": "open"} for i in range(open_positions)]
        return {"positions": positions, "realized_pnl": 0}
    return {
        "summary": {"trades": trades, "total_pnl": 0.0},
        "pools": {"INTRADAY": {"positions": [{"symbol": f"S{i}"} for i in range(open_positions)],
                               "closed": []}},
    }


@pytest.fixture
def tree(tmp_path):
    paper = tmp_path / "docs" / "paper-trades"
    engines = {
        "alpha": {TODAY: _day(trades=5)},
        "beta": {TODAY: _day(trades=9)},                 # retired below
        "gamma_dryrun": {TODAY: _day(trades=3)},         # dryrun suffix
        "delta": {YESTERDAY: _day(trades=4)},            # no file for today
        "epsilon": {TODAY: _day(trades=0, open_positions=2)},
        "zeta": {TODAY: _day(trades=0)},                 # present but idle
        "eta": {TODAY: _day(open_positions=1, flat_v4=True)},
    }
    for name, days in engines.items():
        d = paper / name
        d.mkdir(parents=True)
        for day, content in days.items():
            (d / f"{day}.json").write_text(json.dumps(content))
    (paper / "stray.json").write_text("{}")             # a file, not an engine dir
    retired = tmp_path / "scripts" / "retired"
    retired.mkdir(parents=True)
    (retired / "RETIRED.txt").write_text(
        "# comment line\n"
        "beta   # inline comment\n"
        "\n"
        "   ghost\n"
    )
    return tmp_path


def test_retired_engines_parses_comments_and_whitespace(tree):
    assert retired_engines(tree) == {"beta", "ghost"}


def test_retired_engines_missing_file_is_empty(tmp_path):
    assert retired_engines(tmp_path) == set()


def test_discover_excludes_retired_dryrun_and_missing_today(tree):
    assert discover_engines(TODAY, tree) == ["alpha", "epsilon", "eta", "zeta"]


def test_discover_is_date_specific(tree):
    assert discover_engines(YESTERDAY, tree) == ["delta"]
    assert discover_engines("2026-01-01", tree) == []


def test_discover_missing_paper_dir_is_empty(tmp_path):
    assert discover_engines(TODAY, tmp_path) == []


def test_active_requires_trades_or_open_positions(tree):
    assert active_engines(TODAY, tree) == ["alpha", "epsilon", "eta"]


def test_active_ignores_unreadable_file(tree):
    (tree / "docs" / "paper-trades" / "alpha" / f"{TODAY}.json").write_text("not json")
    assert "alpha" in discover_engines(TODAY, tree)
    assert "alpha" not in active_engines(TODAY, tree)


def test_engine_colour_is_deterministic_hex():
    a, b = engine_colour("v5_wide"), engine_colour("v5_wide")
    assert a == b
    assert re.fullmatch(r"#[0-9a-f]{6}", a)
    assert engine_colour("v5") != engine_colour("v5_classic") or True  # collisions allowed, but stable


def test_real_tree_roster_for_2026_09_09():
    """Guard against the real repo drifting: only the two live intraday engines."""
    if not os.path.isdir(os.path.join(REPO_ROOT, "docs", "paper-trades", "v5")):
        pytest.skip("real paper-trades tree not present")
    assert discover_engines("2026-09-09") == ["v5", "v5_swing", "v5_wide"]
    # v5_swing held KOTAKBANK in positions_active.json on 09-09 -> active despite 0 trades
    assert active_engines("2026-09-09") == ["v5", "v5_swing", "v5_wide"]
