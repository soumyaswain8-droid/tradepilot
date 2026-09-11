"""Phase 1 cheap wins: pure functions against tmp_path fixtures, routes via client."""
import json
from datetime import date
from pathlib import Path

import pytest


def test_operator_blueprint_is_registered(client):
    r = client.get("/api/operator/ping")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
