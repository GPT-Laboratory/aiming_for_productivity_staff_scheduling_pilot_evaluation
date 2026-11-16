#!/bin/sh
# Runs the MAS harness in a uv-managed environment (no venv to maintain).
# MAS_DIR selects the MAS checkout (default ./mas). The 2025 version (it has
# agents/heuristic_agent.py) gets its own dependencies, resolved as of its commit date.
HERE="$(cd "$(dirname "$0")" && pwd)"
MAS="${MAS_DIR:-$HERE/../mas}"
if [ -f "$MAS/agents/heuristic_agent.py" ]; then
    exec uv run --no-project --python 3.11 --exclude-newer 2025-05-06 \
        --with-requirements "$HERE/requirements-mas2025.txt" \
        "$HERE/run_headless.py" "$@"
fi
exec uv run --no-project --python 3.11 \
    --with-requirements "$HERE/requirements-mas.txt" \
    "$HERE/run_headless.py" "$@"
