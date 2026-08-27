"""Web-layer coverage.

Before this file the entire Flask surface -- roughly 70 routes -- was
untested. The terminal already shipped one blank tab on 2026-08-03 because a
script was silently discarded; these tests exist so that class of bug fails
in CI rather than in the browser.
"""


def test_terminal_renders(client):
    """GET / returns the terminal shell."""
    r = client.get("/")
    assert r.status_code == 200
    assert b"TRADEPILOT" in r.data


def test_floor_renders(client):
    """GET /floor returns the Agent Floor console."""
    r = client.get("/floor")
    assert r.status_code == 200
    assert b"Market Scan" in r.data


def test_team_renders(client):
    """GET /team returns the Quant Desk."""
    r = client.get("/team")
    assert r.status_code == 200
    assert b"<h1>TradePilot Quant Desk</h1>" in r.data
