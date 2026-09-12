"""The swept-level reclaim detector: the one definition shared by the EOD shadow
script and the live risk gate."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from prototype.v5.reclaim import swept_level_reclaimed, tag_from_bars


def _bars(rows):
    """rows: list of (o,h,l,c). Returns four lists."""
    return [list(x) for x in zip(*rows)]


def test_short_reclaim_detected():
    # session low before the window is 100 (bar 1). Bar 3 sweeps to 98 and closes 101.
    o, h, l, c = _bars([(102, 103, 100, 101), (101, 102, 100, 100.5), (100.5, 101, 100.2, 100.4),
                        (100.4, 101.5, 98.0, 101.0), (101, 102, 100.8, 101.5)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is True


def test_short_no_reclaim_when_close_stays_below():
    o, h, l, c = _bars([(102, 103, 100, 101), (101, 102, 100, 100.5), (100.5, 101, 100.2, 100.4),
                        (100.4, 100.6, 98.0, 99.0), (99, 99.5, 98.5, 99.2)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is False


def test_short_no_reclaim_when_low_not_swept():
    o, h, l, c = _bars([(102, 103, 100, 101), (101, 102, 100.5, 101), (101, 101.5, 100.7, 101.2),
                        (101.2, 101.6, 100.9, 101.4), (101.4, 102, 101, 101.8)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is False


def test_long_mirror_rejected_high():
    # session high before the window is 105 (bar 0). Bar 3 spikes to 107 and closes 104.
    o, h, l, c = _bars([(103, 105, 102, 104), (104, 104.8, 103, 104.2), (104.2, 104.9, 103.8, 104.5),
                        (104.5, 107.0, 104, 104.0), (104, 104.5, 103, 103.5)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="LONG") is True
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is False


def test_too_early_returns_false():
    o, h, l, c = _bars([(100, 101, 99, 100), (100, 101, 98, 100.5)])
    assert swept_level_reclaimed(o, h, l, c, i=2, side="SHORT") is False


def test_window_uses_last_completed_bars_only():
    # the sweep is at bar 0 (outside a 3-bar window ending before i=5) -> not detected
    o, h, l, c = _bars([(100, 101, 95, 100.5), (100.5, 101, 100, 100.2), (100.2, 100.8, 100, 100.4),
                        (100.4, 100.9, 100.1, 100.6), (100.6, 101, 100.2, 100.7), (100.7, 101, 100.3, 100.8)])
    assert swept_level_reclaimed(o, h, l, c, i=6, side="SHORT") is False


def test_tag_from_bars_replay_shape():
    bars = [{"t": "09:15:00", "o": 102, "h": 103, "l": 100, "c": 101},
            {"t": "09:20:00", "o": 101, "h": 102, "l": 100, "c": 100.5},
            {"t": "09:25:00", "o": 100.5, "h": 101, "l": 100.2, "c": 100.4},
            {"t": "09:30:00", "o": 100.4, "h": 101.5, "l": 98.0, "c": 101.0},
            {"t": "09:35:00", "o": 101, "h": 102, "l": 100.8, "c": 101.5}]
    assert tag_from_bars(bars, "09:36:10", "SHORT") == "reclaim"     # entry inside the 09:35 bar; window 09:20-09:30 holds the sweep
    assert tag_from_bars(bars, "09:31:00", "SHORT") is None          # entry inside the 09:30 bar: only 3 bars before it, need lookback+1
    assert tag_from_bars(bars, "09:22:00", "SHORT") is None          # too few bars before entry
    assert tag_from_bars(bars, "09:36:10", "LONG") == "clean"
