"""CORS must not cover the client's private endpoints.

/app and /api/app/* are served from one origin, and a same-origin request
never consults CORS. Leaving those paths outside the rule removes the
supports_credentials decision entirely, rather than requiring someone to
get it right later.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ORIGIN = {"Origin": "http://localhost:3000"}


def test_the_legacy_api_still_answers_cross_origin(client):
    r = client.get("/api/indices", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" in r.headers


def test_the_client_api_carries_no_cors_headers(client):
    r = client.get("/api/app/calls", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" not in r.headers


def test_the_gated_client_api_carries_no_cors_headers(client):
    r = client.get("/api/app/positions", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" not in r.headers
