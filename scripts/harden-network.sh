#!/bin/bash
# harden-network.sh — always-on inbound shield for untrusted WiFi.
# Enables the macOS application firewall, blocks ALL incoming connections,
# and turns on stealth mode. These settings persist across reboots and apply
# on EVERY network you join — so protection is automatic, not per-network.
#
# Run:     sudo bash scripts/harden-network.sh          # raise the shield
#          sudo bash scripts/harden-network.sh --status # show current state
#          sudo bash scripts/harden-network.sh --relax  # allow inbound again (home use)
#
# Requires root (firewall config is a privileged operation).

set -euo pipefail
FW="/usr/libexec/ApplicationFirewall/socketfilterfw"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root. Use: sudo bash $0 ${1:-}" >&2
  exit 1
fi

status() {
  echo "=== Firewall status ==="
  "$FW" --getglobalstate
  "$FW" --getblockall
  "$FW" --getstealthmode
}

case "${1:-harden}" in
  --status)
    status
    ;;
  --relax)
    echo "Relaxing inbound shield (firewall stays ON, stops blocking all inbound)..."
    "$FW" --setblockall off >/dev/null
    "$FW" --setstealthmode off >/dev/null
    status
    ;;
  harden|"")
    echo "Raising always-on inbound shield..."
    "$FW" --setglobalstate on   >/dev/null   # firewall on
    "$FW" --setblockall on      >/dev/null   # block ALL unsolicited inbound
    "$FW" --setstealthmode on   >/dev/null   # don't answer probes/pings
    echo "Shield up. Outbound and your own localhost services are unaffected."
    status
    ;;
  *)
    echo "Usage: sudo bash $0 [--status|--relax]" >&2
    exit 2
    ;;
esac
