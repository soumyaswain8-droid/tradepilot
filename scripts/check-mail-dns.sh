#!/usr/bin/env bash
# Check that a sending domain can actually deliver mail.
#
#   ./scripts/check-mail-dns.sh sidewall.in
#
# DMARC passes only when SPF or DKIM passes AND aligns with the From domain.
# A DMARC policy published WITHOUT them is worse than no policy at all: it
# tells receivers to quarantine unauthenticated mail, and then every message
# you send is unauthenticated. That is the state this script exists to catch.
set -u

DOMAIN="${1:-sidewall.in}"
SELECTOR="${2:-google}"
RESOLVER="@8.8.8.8"
fail=0

q() { dig +short +time=3 +tries=2 $RESOLVER "$@" 2>/dev/null; }

echo "Checking mail DNS for ${DOMAIN}"
echo

mx=$(q MX "$DOMAIN" | head -3)
if [ -n "$mx" ]; then
  echo "  MX        OK        $(echo "$mx" | tr '\n' ' ')"
else
  echo "  MX        MISSING   cannot receive mail, so bounces and replies go nowhere"
  fail=1
fi

spf=$(q TXT "$DOMAIN" | grep -i 'v=spf1' | head -1)
if [ -z "$spf" ]; then
  echo "  SPF       MISSING   add a TXT record at the apex:"
  echo "                      v=spf1 include:_spf.google.com ~all"
  fail=1
elif echo "$spf" | grep -q '_spf.google.com'; then
  echo "  SPF       OK        $spf"
else
  echo "  SPF       PRESENT   but does not include _spf.google.com -- Workspace mail will fail SPF"
  echo "                      $spf"
  fail=1
fi

# Only one SPF record is legal. Two is a permerror, which fails SPF outright.
spf_count=$(q TXT "$DOMAIN" | grep -ci 'v=spf1')
if [ "$spf_count" -gt 1 ]; then
  echo "  SPF       BROKEN    ${spf_count} SPF records found. RFC 7208 allows exactly one;"
  echo "                      more than one is a permanent error. Merge them into a single record."
  fail=1
fi

dkim=$(q TXT "${SELECTOR}._domainkey.${DOMAIN}" | head -1)
if [ -n "$dkim" ]; then
  echo "  DKIM      OK        selector '${SELECTOR}' published"
else
  echo "  DKIM      MISSING   no key at ${SELECTOR}._domainkey.${DOMAIN}"
  echo "                      Workspace admin -> Apps -> Google Workspace -> Gmail"
  echo "                      -> Authenticate email -> Generate new record, publish it,"
  echo "                      then click Start authentication."
  echo "                      (selectors are arbitrary -- pass yours as argument 2)"
  fail=1
fi

dmarc=$(q TXT "_dmarc.${DOMAIN}" | head -1)
if [ -z "$dmarc" ]; then
  echo "  DMARC     ABSENT    no policy; mail is not rejected on alignment"
else
  policy=$(echo "$dmarc" | grep -o 'p=[a-z]*' | head -1)
  echo "  DMARC     PRESENT   ${policy}"
  if [ "$fail" -ne 0 ] && [ "$policy" != "p=none" ]; then
    echo
    echo "  WARNING   ${policy} is in force while SPF or DKIM is missing above."
    echo "            Receivers are being told to quarantine or reject mail that"
    echo "            cannot authenticate -- which right now is all of it."
  fi
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "Ready to send. Verify once in practice before trusting it: send to a"
  echo "Gmail address, open Show original, and confirm SPF, DKIM and DMARC all PASS."
  exit 0
fi
echo "Not ready to send. Fix the items above, then re-run."
echo "DNS changes take up to an hour to propagate; a failure straight after"
echo "editing may just be cache."
exit 1
