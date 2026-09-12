"""reclaim_flags in scripts/v5-paper-trade.py: per-candidate swept-level flag with an
injected bar fetcher, so no network is touched."""
import sys, os, time, datetime, importlib.util
from zoneinfo import ZoneInfo
import pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))  # dp_creds lives here (see test_chop_ladder.py)


def _mod():
    # importing scripts/v5-paper-trade.py is side-effect free: it defines and wires, and
    # only main() at the bottom trades, so loading it here starts nothing.
    spec = importlib.util.spec_from_file_location("v5pt", os.path.join(ROOT, "scripts", "v5-paper-trade.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _df(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


def test_reclaim_flags_with_injected_fetch():
    m = _mod()
    bars = {"AAA": _df([(102, 103, 100, 101), (101, 102, 100, 100.5), (100.5, 101, 100.2, 100.4),
                        (100.4, 101.5, 98.0, 101.0), (101, 102, 100.8, 101.5)]),
            "BBB": _df([(100, 101, 99, 100)]),
            "CCC": None}
    def fetch(sym):
        if sym == "DDD":
            raise RuntimeError("feed down")
        return bars.get(sym)
    out = m.reclaim_flags(["AAA", "BBB", "CCC", "DDD"], ["SHORT", "SHORT", "SHORT", "SHORT"], fetch=fetch)
    assert out == {"AAA": True, "BBB": None, "CCC": None, "DDD": None}
    out2 = m.reclaim_flags(["AAA"], ["LONG"], fetch=fetch)
    assert out2 == {"AAA": False}


def test_budget_stops_fetching_and_tails_are_none():
    """A slow feed must not stall the synchronous scan: once budget_s is spent, every
    remaining symbol is None and `fetch` is never called again."""
    m = _mod()
    calls = []

    def slow(sym):
        calls.append(sym)
        time.sleep(0.05)
        return None

    syms = [f"S{i}" for i in range(10)]
    out = m.reclaim_flags(syms, ["SHORT"] * 10, fetch=slow, budget_s=0.12)
    assert set(out) == set(syms)                  # every symbol still gets a verdict
    assert all(v is None for v in out.values())
    assert len(calls) < 10, f"budget ignored, fetched all {len(calls)}"
    assert calls == syms[:len(calls)]             # it stopped at the budget, never resumed


def _tz_df(rows):
    idx = pd.DatetimeIndex([r[0] for r in rows]).tz_localize("Asia/Kolkata")
    return pd.DataFrame([r[1] for r in rows], columns=["Open", "High", "Low", "Close"], index=idx)


def test_today_only_drops_the_previous_session():
    """get_candles(days=1) spans two sessions Tue-Fri; yesterday's bars would drag the
    reference session low back a day."""
    m = _mod()
    ohlc = (100, 101, 99, 100)
    rows = [(f"2026-09-10 1{i}:00:00", ohlc) for i in range(5)]          # yesterday, 5 bars
    rows += [(f"2026-09-11 09:{15 + 5 * i}:00", ohlc) for i in range(4)]  # today, 4 bars
    out = m._today_only(_tz_df(rows), today=datetime.date(2026, 9, 11))
    assert len(out) == 4
    assert all(ts.date() == datetime.date(2026, 9, 11) for ts in out.index)
    assert m._today_only(_tz_df(rows[:5]), today=datetime.date(2026, 9, 11)) is None


def test_completed_only_drops_a_still_forming_bar():
    """A 5m bar stamped at its start is complete only once start+5min has passed. Keeping
    it would put the live window one bar ahead of the EOD path."""
    m = _mod()
    ohlc = (100, 101, 99, 100)
    now = datetime.datetime(2026, 9, 11, 11, 32, tzinfo=ZoneInfo("Asia/Kolkata"))
    forming = _tz_df([("2026-09-11 11:25:00", ohlc), ("2026-09-11 11:30:00", ohlc)])
    assert len(m._completed_only(forming, now=now)) == 1      # 11:30 started 2 min ago
    settled = _tz_df([("2026-09-11 11:20:00", ohlc), ("2026-09-11 11:25:00", ohlc)])
    assert len(m._completed_only(settled, now=now)) == 2      # 11:25 started 7 min ago
