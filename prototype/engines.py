"""Engine roster discovery — the roster lives on disk, not in code.

M0 Truth First, spec §4 (docs/superpowers/specs/2026-09-10-m0-truth-first-design.md):
reporters and the watchdog must not hard-code engine lists. An engine exists for a
date when ``docs/paper-trades/<engine>/<date>.json`` exists; it is excluded when its
name is listed in ``scripts/retired/RETIRED.txt`` or ends in ``_dryrun``.

Pure functions, no side effects. Import from scripts with::

    sys.path.insert(0, str(ROOT))          # repo root
    from prototype.engines import discover_engines, active_engines, engine_colour
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRYRUN_SUFFIX = "_dryrun"

# Deterministic fallback palette for engines the caller has no colour for.
_FALLBACK_PALETTE = [
    "#2563eb", "#16a34a", "#dc2626", "#7c3aed", "#f59e0b", "#0ea5e9",
    "#ec4899", "#a855f7", "#64748b", "#0d9488", "#ea580c", "#4f46e5",
]


def _root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else ROOT


def _paper_dir(root: Path) -> Path:
    return root / "docs" / "paper-trades"


def _retired_file(root: Path) -> Path:
    return root / "scripts" / "retired" / "RETIRED.txt"


def retired_engines(root: str | Path | None = None) -> set[str]:
    """Names listed in scripts/retired/RETIRED.txt (one per line, ``#`` comments)."""
    path = _retired_file(_root(root))
    if not path.exists():
        return set()
    names: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            names.add(line)
    return names


def discover_engines(date: str, root: str | Path | None = None) -> list[str]:
    """Sorted engine names with a ``<date>.json`` state file, minus retired and dryrun."""
    base = _root(root)
    paper = _paper_dir(base)
    if not paper.is_dir():
        return []
    retired = retired_engines(base)
    found = []
    for d in paper.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        if name in retired or name.endswith(DRYRUN_SUFFIX):
            continue
        if (d / f"{date}.json").is_file():
            found.append(name)
    return sorted(found)


def _load_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _open_positions(d: dict) -> int:
    """Count open positions in a day file — v5 family (pools) or v4 flat shape."""
    n = 0
    pools = d.get("pools")
    if isinstance(pools, dict):
        for pool in pools.values():
            if isinstance(pool, dict):
                n += len(pool.get("positions") or [])
    positions = d.get("positions")
    if isinstance(positions, list):
        n += sum(1 for p in positions if isinstance(p, dict) and p.get("status") == "open")
    elif isinstance(positions, dict):
        for plist in positions.values():
            if isinstance(plist, list):
                n += len(plist)
    return n


def _trade_count(d: dict) -> int:
    summary = d.get("summary")
    if isinstance(summary, dict):
        try:
            return int(summary.get("trades") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def active_engines(date: str, root: str | Path | None = None) -> list[str]:
    """Discovered engines whose ``<date>.json`` shows trades > 0 or open positions."""
    base = _root(root)
    out = []
    for name in discover_engines(date, base):
        d = _load_json(_paper_dir(base) / name / f"{date}.json")
        if d is None:
            continue
        # A multi-day lane (v5_swing) keeps its open book in positions_active.json, not in
        # the day file — a live position there makes the engine active even on a 0-trade day.
        try:
            pa = json.loads((_paper_dir(base) / name / "positions_active.json").read_text())
            active_book = sum(len(v) for v in (pa.get("positions") or {}).values()) if isinstance(pa.get("positions"), dict) else len(pa.get("positions") or [])
        except Exception:
            active_book = 0
        if _trade_count(d) > 0 or _open_positions(d) > 0 or active_book > 0:
            out.append(name)
    return out


def engine_colour(name: str) -> str:
    """Deterministic hex colour for an engine name (stable across runs and machines)."""
    digest = hashlib.md5(name.encode("utf-8")).digest()
    return _FALLBACK_PALETTE[digest[0] % len(_FALLBACK_PALETTE)]


engine_color = engine_colour
