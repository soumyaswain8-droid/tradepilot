#!/usr/bin/env bash
# Render a TradePilot report onto the TradePilot letterhead.
#
#   scripts/render-weekly.sh 1cr-roadmap/weekly-report/tradepilot-weekly-2026-08-03.md
#
# THREE TRAPS THIS SCRIPT EXISTS TO AVOID, all of which exit 0 while failing:
#
# 1. IMAGE PATHS RESOLVE AGAINST THE TOOL, NOT THE MARKDOWN FILE.
#    `dp content render` resolves relative images against the shell CWD; pandoc
#    resolves them against --resource-path. The report refers to the mark as
#    ../../brand/letterhead/tradepilot-mark.svg, correct relative to the FILE. So we
#    cd into the file's own directory and put that directory first on the resource
#    path. Get this wrong and the tool prints a WARNING, exits 0, and hands back a
#    PDF with no logo.
#
# 2. CDPATH MAKES `cd` PRINT ITS TARGET, so $(cd "$d" && pwd) returns two lines and
#    every path built from it is corrupt. Cleared below.
#
# 3. A FAILED RENDER LEAVES THE PREVIOUS PDF IN PLACE, so any check run afterwards
#    silently reads a stale file and reports success. We remove the output first and
#    assert it was recreated.
#
# Finally the mark is verified by SAMPLING PIXELS, not with `pdfimages -list` —
# WeasyPrint draws SVG as vector operations, so pdfimages reports 0 images even on a
# perfectly good render.
set -euo pipefail
CDPATH=

MD_IN="${1:?usage: render-weekly.sh <path-to-report>.md}"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
MD_DIR="$(cd -- "$(dirname -- "$MD_IN")" && pwd)"
MD="$MD_DIR/$(basename -- "$MD_IN")"
OUT="${MD%.md}.pdf"
CSS="$ROOT/brand/letterhead/tradepilot-letterhead.css"

[ -f "$MD" ]  || { echo "no such report: $MD" >&2; exit 1; }
[ -f "$CSS" ] || { echo "missing letterhead: $CSS" >&2; exit 1; }

rm -f "$OUT"                      # trap 3: never let a stale PDF masquerade as fresh

# Preferred path: the documented dp pipeline. Needs the devpilot DB up, and the
# credentials rotate, so build DATABASE_URL from the credential file rather than
# trusting whatever is already in the environment.
if [ -f "$HOME/.devpilot/credentials.env" ]; then
  set -a; . "$HOME/.devpilot/credentials.env"; set +a
  export DATABASE_URL="postgres://${DB_USER}:${DB_PASSWORD}@127.0.0.1:${DB_PORT}/${DB_NAME}"
fi

rendered=""
if command -v dp >/dev/null 2>&1; then
  # cd into the report's directory — see trap 1
  if ( cd -- "$MD_DIR" && dp content render "$(basename -- "$MD")" -o "$OUT" --css "$CSS" ) >/tmp/tp-render.log 2>&1; then
    rendered="dp content render"
  else
    echo "  dp render failed, falling back to pandoc (see /tmp/tp-render.log)" >&2
  fi
fi

if [ -z "$rendered" ]; then
  pandoc "$MD" -f markdown+raw_html+fenced_divs -t html5 --standalone \
    --embed-resources --css "$CSS" \
    --resource-path="$MD_DIR:$ROOT:$ROOT/brand/letterhead" -o /tmp/tp-render.html
  weasyprint /tmp/tp-render.html "$OUT"
  rendered="pandoc+weasyprint (fallback)"
fi

[ -f "$OUT" ] || { echo "render reported success but produced no PDF" >&2; exit 1; }

PAGES=$(pdfinfo "$OUT" | awk '/^Pages:/{print $2}')

# Verify the mark actually drew. Sample the masthead band for indigo pixels; black
# body text and grey rules do not qualify, so a non-zero count means the mark is there.
pdftoppm -png -r 100 -f 1 -l 1 "$OUT" /tmp/tp-mark-chk
MARK=$(python3 -W ignore - <<'PY'
from PIL import Image
import glob
f=sorted(glob.glob('/tmp/tp-mark-chk*.png'))[0]
im=Image.open(f).convert('RGB'); w,h=im.size
c=im.crop((int(w*0.40),int(h*0.06),int(w*0.60),int(h*0.16)))
px=list(im.crop((int(w*0.40),int(h*0.06),int(w*0.60),int(h*0.16))).getdata())
print(sum(1 for r,g,b in px if b>140 and b-r>40 and b-g>40))
PY
)
rm -f /tmp/tp-mark-chk*.png

echo "  $OUT"
echo "  engine : $rendered"
echo "  pages  : $PAGES"
if [ "${MARK:-0}" -gt 50 ]; then
  echo "  mark   : rendered (${MARK} px)"
else
  echo "  mark   : MISSING (${MARK} px) — check the image path relative to $MD_DIR" >&2
  exit 1
fi
[ "${PAGES:-0}" -le 4 ] || { echo "  OVER BUDGET: $PAGES pages (limit 4)" >&2; exit 1; }
