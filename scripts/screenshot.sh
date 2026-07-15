#!/bin/bash
# Backward-compatible wrapper.
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
python3 "${BASE_DIR}/scripts/screenshot_all.py" "$@"
