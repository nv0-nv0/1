#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT/runtime_vendor${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
python3 tests/test_all.py
