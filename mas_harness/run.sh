#!/bin/sh
# Runs the MAS harness in a uv-managed environment (no venv to maintain).
HERE="$(cd "$(dirname "$0")" && pwd)"
exec uv run --no-project --python 3.11 \
    --with-requirements "$HERE/requirements-mas.txt" \
    "$HERE/run_headless.py" "$@"
