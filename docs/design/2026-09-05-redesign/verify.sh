#!/bin/bash
# Screenshot every redesigned page at desktop + phone, dump client DOM for banned words.
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT="$(dirname "$0")/verify"; mkdir -p "$OUT"
PAGES="app:/app app-calls:/app#calls app-book:/app#book app-record:/app#record login:/app/login signup:/app/signup terminal:/ live:/live lab:/lab team:/team decisions:/decisions portfolio:/portfolio dashboard:/dashboard landing:/landing"
for p in $PAGES; do n=${p%%:*}; u=${p#*:}
  "$C" --headless=new --disable-gpu --hide-scrollbars --window-size=1366,900 --virtual-time-budget=6000 --screenshot="$OUT/${n}_desktop.png" "http://localhost:5050$u" >/dev/null 2>&1 &
  "$C" --headless=new --disable-gpu --hide-scrollbars --window-size=390,844 --virtual-time-budget=6000 --screenshot="$OUT/${n}_phone.png" "http://localhost:5050$u" >/dev/null 2>&1 &
  wait
done
for u in "/app" "/app#calls" "/app#book" "/app#record"; do
  "$C" --headless=new --disable-gpu --virtual-time-budget=6000 --dump-dom "http://localhost:5050$u" 2>/dev/null | sed 's/<script.*<\/script>//g' | sed 's/<[^>]*>/ /g' > "$OUT/dom_$(echo $u | tr -c 'a-z' '_').txt"
done
echo "banned words in client DOM:"; grep -ioE "\bv[4-9](_[a-z]+)?\b|regime|composite|alpha.hunter" "$OUT"/dom_*.txt | sort | uniq -c | head
ls "$OUT" | wc -l
