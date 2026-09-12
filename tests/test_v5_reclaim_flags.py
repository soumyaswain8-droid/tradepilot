"""reclaim_flags in scripts/v5-paper-trade.py: per-candidate swept-level flag with an
injected bar fetcher, so no network is touched."""
import sys, os, importlib.util
import pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))  # dp_creds lives here (see test_chop_ladder.py)


def _mod():
    # the engine script has module-level side effects; import it with the guard env the
    # script honours (read the top of scripts/v5-paper-trade.py: if it lacks a dry/import
    # guard, load only the function source via the helper below)
    spec = importlib.util.spec_from_file_location("v5pt", os.path.join(ROOT, "scripts", "v5-paper-trade.py"))
    m = importlib.util.module_from_spec(spec)
    os.environ["V5_IMPORT_ONLY"] = "1"
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
