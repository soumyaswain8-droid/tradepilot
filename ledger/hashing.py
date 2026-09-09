"""Deterministic hashing for ledger rows.

- canonical_json: sorted keys, no whitespace, floats as Python repr (json.dumps default),
  -0.0 normalised to 0.0 so the text is identical before and after a jsonb round trip.
- row_hash: sha256 hex of the canonical JSON of a payload.
- merkle_root: pairwise sha256 over hex leaves; odd leaf duplicated; empty -> sha256("").
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable


def sanitize(obj: Any) -> Any:
    """Return a copy with NaN/Inf floats replaced by None (jsonb cannot hold them)."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    return obj


def _jsonb_stable(obj: Any) -> Any:
    """Normalise values jsonb cannot round-trip: numeric has no negative zero, so -0.0 comes back
    as 0.0. Hashing the normalised form keeps row_hash equal before and after storage."""
    if isinstance(obj, float):
        return 0.0 if obj == 0.0 else obj
    if isinstance(obj, dict):
        return {k: _jsonb_stable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonb_stable(v) for v in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(_jsonb_stable(obj), sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row_hash(payload: Any) -> str:
    return sha256_hex(canonical_json(payload))


def merkle_root(hashes: Iterable[str]) -> str:
    level = list(hashes)
    if not level:
        return sha256_hex("")
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [sha256_hex(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]
