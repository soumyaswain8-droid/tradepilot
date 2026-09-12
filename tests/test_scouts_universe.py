"""
test_scouts_universe — the Floor's scouts must watch the same universe the engines
trade (quant/universe_engine.txt), with an env override and a safe fallback.

See quant/build_universe_engine.py for how the file is generated, and
prototype/agents/scouts.py (UNIVERSE_F) for the resolution logic under test.

NOTE on the sys.path setup below: prototype/data_engine.py does a bare
`from stock_universe import (...)`, which only resolves if prototype/ itself
(not just the repo root) is on sys.path -- the same reason prototype/app.py
inserts its own directory at import time (see tests/conftest.py's docstring).
Repo root alone is not enough here, so both are inserted.
"""
import sys, os, importlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "prototype"))


def test_engine_universe_file_matches_data_engine():
    from prototype.data_engine import NIFTY_STOCKS
    want = sorted({s.replace(".NS", "") for s in NIFTY_STOCKS if s.endswith(".NS")})
    got = [l.strip() for l in open(os.path.join(ROOT, "quant", "universe_engine.txt")) if l.strip() and not l.startswith("#")]
    assert got == want
    assert len(got) > 350


def test_scouts_universe_env_override(tmp_path, monkeypatch):
    f = tmp_path / "u.txt"; f.write_text("RELIANCE\nINFY\n")
    monkeypatch.setenv("FLOOR_UNIVERSE", str(f))
    import prototype.agents.scouts as sc
    importlib.reload(sc)
    assert sc.UNIVERSE_F == f


def test_scouts_universe_default_is_engine_file(monkeypatch):
    monkeypatch.delenv("FLOOR_UNIVERSE", raising=False)
    import prototype.agents.scouts as sc
    importlib.reload(sc)
    assert sc.UNIVERSE_F.name == "universe_engine.txt"
