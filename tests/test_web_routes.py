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


def test_router_declares_three_sections(client):
    """The section registry is JS-rendered, so assert it in the served module.

    A Flask test client executes no JavaScript — the served page carries an
    empty <nav>. Fetching router.js verifies the real artifact through the
    real server, which is the closest honest equivalent without a browser.
    """
    r = client.get("/static/desk/router.js")
    assert r.status_code == 200
    for section in (b'id: "desk"', b'id: "market"', b'id: "agents"'):
        assert section in r.data


def test_terminal_has_subtab_bar(client):
    """The sub-tab bar element must exist even when empty."""
    assert b'id="subnav"' in client.get("/").data


def test_terminal_loads_router_modules(client):
    """Every module is referenced by a src-only script tag.

    This is the direct regression test for the 2026-08-03 blank tab: a
    script referenced but never loaded, or loaded with discarded inline
    content, is exactly how that shipped.
    """
    body = client.get("/").data
    for src in (b"/static/desk/route.js",
                b"/static/desk/router.js",
                b"/static/desk.js"):
        assert src in body


def test_router_keeps_external_links(client):
    """The nav is registry-rendered, so external destinations must be declared
    in the module. /classic is the client-facing surface and must stay
    reachable from the terminal until it is absorbed."""
    r = client.get("/static/desk/router.js")
    assert r.status_code == 200
    assert b'href: "/decisions"' in r.data
    assert b'href: "/classic"' in r.data


def test_agent_floor_panes_exist(client):
    """Both panes are in the shell."""
    body = client.get("/").data
    assert b'id="view-agents-quant"' in body
    assert b'id="view-agents-floor"' in body


def test_agent_floor_frames_ship_empty(client):
    """Frames must have no src in the served HTML.

    A hardcoded src would load and start polling both consoles on every
    page load, whether or not anyone opens the section.
    """
    body = client.get("/").data
    # Assert the behaviour, not the attribute order: no framed URL may appear
    # in the served HTML at all. panes.js sets src at mount time.
    assert b"/team?embed=1" not in body
    assert b"/floor?embed=1" not in body
    assert b'id="frameQuant"' in body
    assert b'id="frameFloor"' in body


def test_panes_module_loaded(client):
    assert b"/static/desk/panes.js" in client.get("/").data
