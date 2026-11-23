#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$HOME/mc-verify"
export TMPDIR="$HOME/mc-verify-tmp"
mkdir -p "$TMPDIR"
fail=0
ok()  { echo "PASS: $1"; }
bad() { echo "FAIL: $1"; fail=1; }

rm -rf "$V"
echo "Installing into a clean venv (takes a few minutes, please wait)..."
python3 -m venv "$V" && "$V/bin/pip" install -q "$ROOT" && ok "installs" || { bad "installs"; exit 1; }

[ -x "$V/bin/maxclipper" ] && ok "maxclipper command exists" || { bad "maxclipper command missing"; exit 1; }
"$V/bin/maxclipper" --version >/dev/null 2>&1 && ok "--version works" || bad "--version"

(cd "$HOME" && "$V/bin/maxclipper" --no-browser --port 3066 > "$TMPDIR/server.log" 2>&1 &)
sleep 14

for u in "" static/css/style.css static/js/app.js api/health; do
  c=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3066/$u")
  [ "$c" = "200" ] && ok "/$u" || bad "/$u returned $c"
done

html=$(curl -s http://127.0.0.1:3066/)
echo "$html" | grep -qi "<title>Max Clipper" && ok "page title is Max Clipper" || bad "page title"
if echo "$html" | grep -qiE 'clipforge|gta ?-?6|viralforge'; then bad "old name in page"; else ok "no old names in page"; fi
if curl -s http://127.0.0.1:3066/static/js/app.js | grep -qiE 'clipforge|gta6|viralforge'; then bad "old name in app.js"; else ok "no old names in app.js"; fi

SP=$("$V/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
bad_fonts=0
for f in "$SP"/app/assets/fonts/*.ttf; do
  head -c4 "$f" | od -An -tx1 | tr -d ' \n' | grep -qE '^(00010000|4f54544f|74727565)$' || bad_fonts=1
done
[ "$bad_fonts" = "0" ] && ok "installed fonts are real fonts" || bad "an installed font is not a real font"

pkill -f "maxclipper --no-browser --port 3066"
if grep -q "Traceback" "$TMPDIR/server.log"; then bad "traceback in server log"; tail -8 "$TMPDIR/server.log"; else ok "server log clean"; fi

rm -rf "$V" "$TMPDIR"
[ "$fail" = "0" ] && echo "ALL PASS" || echo "SOME CHECKS FAILED"
exit $fail
