#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT/runtime_vendor${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$ROOT/server_app.py"
