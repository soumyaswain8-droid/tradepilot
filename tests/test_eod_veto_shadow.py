import sys, os, json, importlib.util
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def _load():
    spec = importlib.util.spec_from_file_location("eod_veto_shadow", os.path.join(ROOT, "scripts", "eod-veto-shadow.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


BARS = [{"t": "09:15:00", "o": 102, "h": 103, "l": 100, "c": 101},
        {"t": "09:20:00", "o": 101, "h": 102, "l": 100, "c": 100.5},
        {"t": "09:25:00", "o": 100.5, "h": 101, "l": 100.2, "c": 100.4},
        {"t": "09:30:00", "o": 100.4, "h": 101.5, "l": 98.0, "c": 101.0},
        {"t": "09:35:00", "o": 101, "h": 102, "l": 100.8, "c": 101.5},
        {"t": "09:40:00", "o": 101.5, "h": 102, "l": 101, "c": 101.2}]
REPLAY = {"date": "2026-09-11", "candles": {"AAA": BARS, "BBB": BARS},
          "engines": {"v5": {"trades": [
              {"symbol": "AAA", "dir": "SHORT", "entry_time": "09:36:10", "pnl": -85.6, "reason": "STOPLOSS"},
              {"symbol": "BBB", "dir": "SHORT", "entry_time": "09:22:00", "pnl": 40.0, "reason": "TARGET"},
              {"symbol": "AAA", "dir": "LONG", "entry_time": "09:41:00", "pnl": 10.0, "reason": "TIME_EXIT"},
              {"symbol": "ZZZ", "dir": "SHORT", "entry_time": "10:00:00", "pnl": -5.0, "reason": "STOPLOSS"}]}}}


def test_score_replay_buckets():
    m = _load()
    out = m.score_replay(REPLAY, ["v5"])
    e = out["engines"]["v5"]
    tags = {(t["symbol"], t["entry_time"]): t["tag"] for t in e["trades"]}
    assert tags[("AAA", "09:36:10")] == "reclaim"
    assert tags[("BBB", "09:22:00")] == "untagged"      # too few bars before entry
    assert tags[("AAA", "09:41:00")] == "clean"          # LONG, no rejected high
    assert tags[("ZZZ", "10:00:00")] == "untagged"       # no candles
    assert e["buckets"]["reclaim"] == {"n": 1, "pnl": -85.6, "win": 0}
    assert e["buckets"]["clean"] == {"n": 1, "pnl": 10.0, "win": 100}
    assert e["buckets"]["untagged"]["n"] == 2
    assert out["fleet"]["reclaim"]["n"] == 1


def test_ledger_replaces_rows_for_same_date(tmp_path):
    m = _load()
    led = tmp_path / "veto-ledger.csv"
    out = m.score_replay(REPLAY, ["v5"])
    m.write_ledger(led, out)
    m.write_ledger(led, out)
    rows = led.read_text().strip().splitlines()
    assert rows[0] == "date,engine,tag,n,pnl,win_pct"
    assert len(rows) == 1 + 3            # header + 3 tags for one engine, no duplicates
