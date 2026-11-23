#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

find_python() {
  local candidate=""
  if command -v uv >/dev/null 2>&1; then
    candidate="$(uv python find --no-project --managed-python 3.12 2>/dev/null || uv python find --no-project 3.12 2>/dev/null || true)"
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      if "$candidate" -I -B -c "import tkinter" >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  fi

  for name in python3.12 python3.13 python3.11 python3 python; do
    candidate="$(command -v "$name" 2>/dev/null || true)"
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      if "$candidate" -I -B -c "import tkinter" >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done

  if command -v uv >/dev/null 2>&1; then
    echo "Installing Python 3.12 with Tk via uv..." >&2
    if uv python install 3.12 >/dev/null 2>&1; then
      candidate="$(uv python find --no-project --managed-python 3.12 2>/dev/null || uv python find --no-project 3.12 2>/dev/null || true)"
      if [[ -n "$candidate" && -x "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  fi

  for name in python3 python; do
    candidate="$(command -v "$name" 2>/dev/null || true)"
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3 was not found. Install Python 3 (with tkinter) or uv, then retry ./SETUP.sh." >&2
  exit 2
fi

"$PYTHON_BIN" -X utf8 -B "$SCRIPT_DIR/setup_project.py" "$@"
setup_status=$?
if [[ "$setup_status" -ne 0 ]]; then
  echo "Setup did not finish. Your student files and saved runs are unchanged." >&2
fi
exit "$setup_status"
