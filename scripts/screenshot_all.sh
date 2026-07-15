#!/bin/bash
# Cross-platform wrapper. Prefer `python scripts/screenshot_all.py` on Windows.
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "${BASE_DIR}/scripts/screenshot_all.py" "$@"
