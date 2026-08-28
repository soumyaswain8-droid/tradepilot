#!/usr/bin/env python3
"""
diskguard — refuse to start a job that could fill the volume.

WHY THIS EXISTS. On 2026-08-28 an overnight research run wrote a 183 MB panel and a
subagent wrote a multi-hundred-MB intermediate, and together they took the root volume
to zero bytes. Every write path on macOS needs to create a temp file first, so at zero
bytes NOTHING could run — not the analysis, not the editor, not even the `rm` that
would have cleared it. Six hours of scheduled jobs failed silently and the machine had
to be rescued through a tool that happened to use a different code path.

The cost of that outage was hours. The cost of preventing it is one call at the top of
main(). A job that stops with "need 2.0 GB, have 0.4 GB" is a message; a job that runs
the volume to zero is an outage that takes the whole machine with it.

    from quant.diskguard import require_free
    require_free(2.0, "winners panel is ~200MB and pandas needs headroom")

Design notes:
  - the check is at START, not per-write. A job that dies halfway leaves a partial file
    and a confused operator; better to refuse before anything is created.
  - `headroom` defaults deliberately high. Free space is not the same as usable space:
    macOS reports purgeable space as free, and other processes are writing too.
  - it raises rather than exits, so a caller that genuinely wants to continue can catch
    it and say so explicitly in its own logs.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DiskTooFull(RuntimeError):
    pass


def free_gb(path: Path | str = ROOT) -> float:
    """Free space in GB on the volume holding `path`."""
    return shutil.disk_usage(str(path)).free / 1e9


def require_free(gb: float = 2.0, why: str = "", path: Path | str = ROOT) -> float:
    """Raise unless at least `gb` gigabytes are free. Returns the free space."""
    have = free_gb(path)
    if have < gb:
        raise DiskTooFull(
            f"refusing to start: need {gb:.1f} GB free, have {have:.2f} GB"
            + (f" ({why})" if why else "")
            + "\n  Free space first — a job that fills this volume takes the whole"
              "\n  machine down with it, including the commands needed to recover."
        )
    return have


def report(gb: float = 2.0, why: str = "", path: Path | str = ROOT) -> float:
    """Same check, but prints the margin instead of staying silent on success.

    Printing on success matters: a guard that is invisible when it passes is a guard
    nobody trusts is running.
    """
    have = require_free(gb, why, path)
    print(f"  disk: {have:.1f} GB free (need {gb:.1f})")
    return have


if __name__ == "__main__":
    import sys
    need = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    try:
        report(need)
    except DiskTooFull as e:
        print(f"  {e}")
        sys.exit(1)
