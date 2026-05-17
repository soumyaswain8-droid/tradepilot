"""Tiny helper: exits 0 if CEO override on the live model is still valid, 1 if expired/missing."""
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
report_path = PROJECT_ROOT / "prototype" / "v4" / "models" / "verification_report.json"

try:
    r = json.loads(report_path.read_text())
except Exception as e:
    print(f"FAIL: cannot read verification_report.json: {e}")
    sys.exit(1)

override = r.get("override")
if not override:
    print("FAIL: no override field set")
    sys.exit(1)

expires_str = override.get("expires")
if not expires_str:
    # permanent override
    print(f"PASS: override permanent (by={override.get('by')})")
    sys.exit(0)

try:
    expires = date.fromisoformat(expires_str)
except Exception as e:
    print(f"FAIL: cannot parse expires={expires_str!r}: {e}")
    sys.exit(1)

today = date.today()
if expires < today:
    print(f"FAIL: override expired on {expires_str} (today={today})")
    sys.exit(1)

days_left = (expires - today).days
print(f"PASS: override valid until {expires_str} ({days_left} days left)")
sys.exit(0)
