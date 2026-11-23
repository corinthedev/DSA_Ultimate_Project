#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
READY_FILE="$SCRIPT_DIR/.setup/environment-ready.json"

needs_setup=0
if [[ ! -x "$VENV_PY" ]] || [[ ! -f "$READY_FILE" ]]; then
  needs_setup=1
elif ! "$VENV_PY" -I -B -c "import tkinter, PIL" >/dev/null 2>&1; then
  needs_setup=1
fi

if [[ "$needs_setup" -eq 1 ]]; then
  echo "Preparing Adventure's local environment..."
  "$SCRIPT_DIR/SETUP.sh"
fi

if [[ -z "${FONTCONFIG_FILE:-}" ]] && [[ -f "$SCRIPT_DIR/.setup/fonts/fonts.conf" ]]; then
  export FONTCONFIG_FILE="$SCRIPT_DIR/.setup/fonts/fonts.conf"
fi

exec "$VENV_PY" -X utf8 -B "$SCRIPT_DIR/main.py" "$@"
