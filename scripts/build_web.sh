#!/usr/bin/env bash
# Build the browser version with pygbag. Only the game ships: main.py,
# tilebase/ and assets/ are copied into a staging folder, so docs and
# .env.local (the Deepgram key) never end up in the public bundle.
# Usage: scripts/build_web.sh          build into build/grok-the-gap/build/web
#        scripts/build_web.sh --serve  build and serve on localhost:8000
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
stage="$root/build/grok-the-gap"
rm -rf "$stage"
mkdir -p "$stage"
cp "$root/main.py" "$stage/"
cp -R "$root/assets" "$stage/"
mkdir "$stage/tilebase"
# speech.py needs sounddevice and raw sockets, which the browser lacks.
find "$root/tilebase" -maxdepth 1 -name '*.py' ! -name speech.py -exec cp {} "$stage/tilebase/" \;
args=(--title "Grok the Gap")
if [[ "${1:-}" != "--serve" ]]; then
  args=(--build "${args[@]}")
fi
cd "$stage"
exec pygbag "${args[@]}" .
