"""
Nightly backup — Python rewrite of nightly-backup.sh.

We rewrote in Python because macOS TCC was inconsistently blocking
launchd-spawned bash from exec'ing this specific script (EX_CONFIG with
no log output, even after Label / path / minimal-plist permutations).
Python invocations under launchd work reliably without those quirks.

Same behaviour as the bash original:
  - tar -czf the immutable artefacts to ~/tradepilot-backups/daily/
  - on Sunday: also copy to weekly/
  - on 1st of month: also copy to monthly/
  - retain last 30 daily / 12 weekly / 12 monthly

Audit-logs to docs/team/activity/.

CLI:
  python3 scripts/team/cadence/nightly_backup.py
  python3 scripts/team/cadence/nightly_backup.py --dry-run
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import tarfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKUP_ROOT = Path(os.environ.get("TRADEPILOT_BACKUP_DIR",
                                   str(Path.home() / "tradepilot-backups")))
IST = timezone(timedelta(hours=5, minutes=30))

INCLUDE_DIRS = [
    "docs/team",
    "docs/sarathi",
    "docs/exec",
    "docs/slippage",
    "prototype/v4/models",
]
EXCLUDE_NAMES = {"__pycache__", ".DS_Store"}


def _exclude_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    name = Path(tarinfo.name).name
    if name in EXCLUDE_NAMES:
        return None
    return tarinfo


def keep_last(directory: Path, keep: int) -> int:
    if not directory.exists():
        return 0
    files = sorted(directory.glob("*.tar.gz"),
                   key=lambda p: p.stat().st_mtime,
                   reverse=True)
    removed = 0
    for stale in files[keep:]:
        stale.unlink()
        removed += 1
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    now = datetime.now(IST)
    date_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()      # Monday=0 ... Sunday=6 (Python convention)
    day_of_month = now.day

    daily_dir = BACKUP_ROOT / "daily"
    weekly_dir = BACKUP_ROOT / "weekly"
    monthly_dir = BACKUP_ROOT / "monthly"
    for d in (daily_dir, weekly_dir, monthly_dir):
        d.mkdir(parents=True, exist_ok=True)

    tar_name = f"tradepilot-backup-{date_str}.tar.gz"
    daily_tar = daily_dir / tar_name

    if args.dry_run:
        print(f"[dry-run] would write {daily_tar}")
        return

    # Build tarball directly into the daily slot
    os.chdir(PROJECT_ROOT)
    with tarfile.open(daily_tar, "w:gz") as tf:
        for d in INCLUDE_DIRS:
            if Path(d).exists():
                tf.add(d, recursive=True, filter=_exclude_filter)

    size_kb = daily_tar.stat().st_size // 1024

    # Weekly slot on Sunday (Python weekday Sunday=6)
    if weekday == 6:
        shutil.copy2(daily_tar, weekly_dir / tar_name)

    # Monthly slot on 1st of month
    if day_of_month == 1:
        shutil.copy2(daily_tar, monthly_dir / tar_name)

    # Retention
    removed_daily = keep_last(daily_dir, 30)
    removed_weekly = keep_last(weekly_dir, 12)
    removed_monthly = keep_last(monthly_dir, 12)

    # Audit
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from scripts.team.log import log_activity
        log_activity("knowledge-archivist", "nightly-backup",
                     f"Backed up to {daily_tar} ({size_kb} KB); "
                     f"trimmed daily={removed_daily} weekly={removed_weekly} monthly={removed_monthly}",
                     links={"path": str(daily_tar)})
    except Exception as e:
        print(f"warn: activity log failed: {e}", file=sys.stderr)

    print(f"Backup OK: {daily_tar} ({size_kb} KB)")


if __name__ == "__main__":
    main()
