#!/usr/bin/env bash
# Convert an E16 .etheme and install it as a Plasma 6 Aurorae decoration.
#
# Usage:
#   scripts/install_theme.sh <theme.etheme> [--apply] [--scale N] [--render]
#
#   --apply    also switch the live KWin session to the theme
#              (Border size is picked from the generated rc; revert with
#              `themey apply Breeze`)
#   --scale N  border/image upscale factor 1|2|3 (default 2)
#   --render   after installing, screenshot it in a headless nested KWin
#              and print the PNG path (no effect on your session)
set -euo pipefail

usage() { sed -n '2,13p' "$0"; exit 2; }

theme=""; apply=0; scale=2; render=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)  apply=1 ;;
    --render) render=1 ;;
    --scale)  scale="${2:?--scale needs a value}"; shift ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $1" >&2; usage ;;
    *)  theme="$1" ;;
  esac
  shift
done
[[ -n "$theme" ]] || usage
[[ -f "$theme" ]] || { echo "not a file: $theme" >&2; exit 1; }

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

# Snap-launched shells (e.g. VS Code's terminal) point XDG_DATA_HOME into the
# snap sandbox; KWin reads the real ~/.local/share, so install there.
if [[ "${XDG_DATA_HOME:-}" == *"/snap/"* ]]; then
  echo "note: XDG_DATA_HOME=$XDG_DATA_HOME is a snap sandbox; installing to ~/.local/share instead" >&2
  unset XDG_DATA_HOME
fi

cd "$repo"
uv run themey convert "$theme" --scale "$scale" --no-open

name="$(uv run python -c 'import sys; from themey.slug import slugify; print(slugify(sys.argv[1]))' "$(basename "${theme%.etheme}")")"
report="$HOME/.local/share/themey/previews/$name.report.txt"
if [[ -f "$report" ]]; then
  echo
  sed -n '/^## Apply/,/^$/p' "$report"
fi

if (( render )); then
  uv run themey render "$name" -o "/tmp/themey-$name.png"
fi

if (( apply )); then
  uv run themey apply "$name"
  echo "Revert with: uv run themey apply Breeze"
else
  echo "To switch your desktop to it: uv run themey apply $name"
fi
