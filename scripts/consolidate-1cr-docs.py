#!/usr/bin/env python3
"""
consolidate-1cr-docs — gather the Rs 1 crore thread into 1cr-roadmap/ and repoint
every reference to it.

WHY A SCRIPT AND NOT `git mv`
These documents are cited from code docstrings, other docs and scripts (1-4 inbound
references each, measured). Moving them by hand leaves dead pointers that nothing
checks and nobody notices until someone follows one. This moves the file AND rewrites
every reference in the same pass, so the two can never drift.

WHAT IS DELIBERATELY LEFT ALONE
  - Daily machine artifacts (standup/, audit/, work-log/, reports/missed-trades,
    learning/*-eod-summary, research/regime-switching-daily). ~100 files written by
    the daily pipeline, which would recreate them in docs/ anyway.
  - Docs unrelated to the trading P&L or the revenue goal: the Agentic Summit writeup,
    the GitHub support ticket, the sci-fi landing design.

Run:
    python3 scripts/consolidate-1cr-docs.py            # dry run, prints the plan
    python3 scripts/consolidate-1cr-docs.py --apply
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = "1cr-roadmap"

# source -> destination subfolder
MOVES = {
    # the plan itself
    "docs/research/2026-08-05_signal-rebuild-plan.md": "plan",
    # strategy / edge research
    "docs/research/2026-07-29_v10-april-replica-feasibility-DRAFT.md": "research",
    "docs/research/2026-07-28_rrg-directional-design-REVIEW.md": "research",
    "docs/research/2026-07-24_rrg-directional-bias-design-DRAFT.md": "research",
    "docs/research/2026-07-24_short-confirm-backtest.md": "research",
    "docs/research/2026-07-21_sell-tier-scorer-gap.md": "research",
    "docs/research/2026-07-20_gate1-rrg-sensor-backtest.md": "research",
    "docs/research/2026-07-20_risk_gate_three_state_verdict.md": "research",
    # designs / specs
    "docs/superpowers/specs/2026-08-05-options-data-and-health-guard-design.md": "design",
    "docs/superpowers/specs/2026-07-30-v10-april-replica-design.md": "design",
    "docs/superpowers/specs/2026-07-20-rrg-regime-sensor-design.md": "design",
    # US expansion — the revenue half of the target
    "docs/research/us-market/01-brokers-and-apis.md": "us-market",
    "docs/research/us-market/02-data-sources.md": "us-market",
    "docs/research/us-market/03-anvitra-and-what-actually-works.md": "us-market",
    "docs/research/us-market/04-regulatory-lrs-tax.md": "us-market",
}

# Only scan directories that can plausibly cite a doc. Scanning the whole repo pulls
# in paper-trade JSON and node_modules and takes minutes.
SCAN_DIRS = ["prototype", "scripts", "docs", "app", "engine", "quant", "tests",
             "learnings", DEST]
SCAN_EXT = {".py", ".sh", ".md", ".json", ".js", ".html", ".css", ".txt", ".yaml", ".yml"}


def scan_files():
    for d in SCAN_DIRS:
        p = ROOT / d
        if not p.is_dir():
            continue
        for f in p.rglob("*"):
            if (f.is_file() and f.suffix in SCAN_EXT
                    and ".git" not in f.parts
                    and "node_modules" not in f.parts
                    and "paper-trades" not in f.parts
                    # Never rewrite this file: its own MOVES table contains every
                    # source path, so a rewrite would turn the mapping into
                    # destination->destination and silently break a re-run.
                    and f.resolve() != Path(__file__).resolve()):
                yield f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    plan = []
    for src, sub in MOVES.items():
        s = ROOT / src
        if not s.exists():
            print(f"  SKIP (missing): {src}")
            continue
        plan.append((src, f"{DEST}/{sub}/{s.name}"))

    print(f"\n  {len(plan)} documents -> {DEST}/\n")
    for src, dst in plan:
        print(f"    {src}\n      -> {dst}")

    # Build the rewrite table. Match the full path and the bare 'dir/name.md' form,
    # longest first so a longer path is never partly rewritten by a shorter rule.
    rewrites = sorted(plan, key=lambda x: -len(x[0]))

    print("\n  reference rewrites:")
    touched = 0
    for f in scan_files():
        try:
            t = f.read_text()
        except Exception:
            continue
        orig = t
        for src, dst in rewrites:
            if src in t:
                t = t.replace(src, dst)
        if t != orig:
            touched += 1
            rel = f.relative_to(ROOT)
            n = sum(orig.count(s) for s, _ in rewrites)
            print(f"    {rel}  ({n} reference{'s' if n != 1 else ''})")
            if a.apply:
                f.write_text(t)
    if not touched:
        print("    none found")

    if not a.apply:
        print("\n  DRY RUN — nothing changed. Re-run with --apply\n")
        return 0

    for src, dst in plan:
        d = ROOT / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["mv", str(ROOT / src), str(d)], check=True)
    print(f"\n  moved {len(plan)} files, rewrote references in {touched}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
