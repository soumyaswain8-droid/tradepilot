"""TradePilot evidence ledger: schema, hashing, JSON migration and record-page queries.

Spec: docs/superpowers/specs/2026-09-10-m0-truth-first-design.md §5.
Lives in the DevPilot Postgres under schema `tradepilot`; every table is append-only.
"""
from .hashing import canonical_json, merkle_root, row_hash  # noqa: F401

TABLES = ("calls", "verdicts", "outcomes", "baselines", "panels", "disclosures", "ledger_roots")
