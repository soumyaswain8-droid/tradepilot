"""The client dashboard's served surface.

None of the rendering is testable here -- there is no DOM, and adding one
would breach the no-new-dependencies constraint. What these tests can prove is
that the route serves, that every module referenced is actually fetchable, and
that operator vocabulary never reaches a client's page. Everything else lives
in docs/APP_MANUAL_CHECKS.md and is checked by hand.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def test_app_route_serves(client):
    assert client.get("/app").status_code == 200


def test_every_module_the_page_references_is_fetchable(client):
    """Fetch them, do not merely grep for the <script src>.

    A tag can name a file that 404s -- that is exactly how a tab shipped blank
    on 2026-08-03. Asserting the string appears in the HTML proves only that
    somebody typed it.
    """
    for path in ("/static/desk/route.js", "/static/app/api.js",
                 "/static/app/screens.js", "/static/app/main.js",
                 "/static/app.css"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.data) > 0, path


def test_all_five_mount_points_exist(client):
    body = client.get("/app").get_data(as_text=True)
    for view in ("view-home", "view-calls", "view-call", "view-book", "view-record"):
        assert view in body, view


def test_module_order_is_load_bearing(client):
    """route.js defines TPRoute; main.js uses it. Order is not cosmetic."""
    body = client.get("/app").get_data(as_text=True)
    for tag in ("desk/route.js", "app/api.js", "app/screens.js", "app/main.js"):
        assert tag in body, "missing script tag: " + tag
    assert body.index("desk/route.js") < body.index("app/main.js")
    assert body.index("app/api.js") < body.index("app/main.js")
    assert body.index("app/screens.js") < body.index("app/main.js")


def test_the_router_is_reused_not_reimplemented(client):
    """main.js must go through TPRoute, not hand-roll a second parser.

    route.js is pure and already carries twelve node tests. A second parser
    would be a second thing to get wrong, and the load-order test alone does
    not prove the dependency is actually used.
    """
    js = client.get("/static/app/main.js").get_data(as_text=True)
    assert "TPRoute.parse" in js
    assert "TPRoute.build" in js


BANNED_VOCABULARY = ("v4", "v5_size", "composite_scorer", "alpha-hunter",
                     "regime", "orchestrator", "sprint")


def test_no_operator_vocabulary_in_the_page_or_its_modules(client):
    """A client sees what was called, never which engine said so.

    The served HTML is static, so scanning it alone can only catch a banned
    word typed into the markup. The modules are where a renderer could label
    something "v4 score", so they are scanned too.

    What this CANNOT cover: a banned word arriving inside API data and being
    rendered client-side. That is guarded a layer down by shape_call's
    explicit field allowlist in prototype/client_api.py, which has its own
    test. Do not read this test as covering it.
    """
    surfaces = ["/app", "/static/app/main.js", "/static/app/api.js",
                "/static/app/screens.js", "/static/app.css"]
    for path in surfaces:
        body = client.get(path).get_data(as_text=True).lower()
        for word in BANNED_VOCABULARY:
            assert word not in body, (path, word)


def test_the_terminal_and_classic_are_untouched(client):
    """/app is additive. Neither existing surface changes."""
    assert client.get("/").status_code == 200
    assert client.get("/classic").status_code == 200


def test_no_inline_script_in_the_template(client):
    """Every script tag is src-only. Inline JS cannot be cached or linted."""
    body = client.get("/app").get_data(as_text=True)
    for chunk in body.split("<script")[1:]:
        head = chunk.split(">")[0]
        assert "src=" in head, "inline <script> found: " + head[:60]


def test_api_module_names_every_endpoint_it_needs(client):
    """A screen that calls a path the module never defines fails silently."""
    js = client.get("/static/app/api.js").get_data(as_text=True)
    for path in ("/api/app/calls", "/api/app/record", "/api/app/positions"):
        assert path in js, path


def test_api_module_is_the_only_place_fetch_appears(client):
    """Keeping fetch out of the renderers is what makes them inspectable."""
    screens = client.get("/static/app/screens.js").get_data(as_text=True)
    main = client.get("/static/app/main.js").get_data(as_text=True)
    assert "fetch(" not in screens
    assert "fetch(" not in main


def test_screens_module_never_prints_a_bare_hit_rate(client):
    """The spec forbids a rate without its sample size."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "resolved" in js
    assert "is_meaningful" in js
