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


def test_floor_embed_hides_brand(client):
    """?embed=1 drops the brand span; the stats strip must survive."""
    r = client.get("/floor?embed=1")
    assert r.status_code == 200
    assert b"AGENT FLOOR</span>" not in r.data
    assert b'id="sTicks"' in r.data          # stats strip kept


def test_floor_without_embed_keeps_brand(client):
    """The standalone page is unchanged."""
    r = client.get("/floor")
    assert b"AGENT FLOOR</span>" in r.data


def test_team_embed_hides_header_and_pageswitch(client):
    """?embed=1 drops the header and must not load the operator nav."""
    r = client.get("/team?embed=1")
    assert r.status_code == 200
    # Match the <h1>, not the bare string: team.html:5 also carries
    # "TradePilot Quant Desk" in its <title>, which embed mode keeps.
    assert b"<h1>TradePilot Quant Desk</h1>" not in r.data
    assert b"pageswitch.js" not in r.data


def test_team_without_embed_keeps_header(client):
    """The standalone page is unchanged."""
    r = client.get("/team")
    assert b"<h1>TradePilot Quant Desk</h1>" in r.data
    assert b"pageswitch.js" in r.data
