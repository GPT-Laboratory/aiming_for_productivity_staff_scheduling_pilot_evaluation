#!/bin/sh
# Usage: mas_harness/run_batch.sh <dataset-dir> <name> <n-runs> <optimization-rounds>
HERE="$(cd "$(dirname "$0")" && pwd)"; CASE="$1"; NAME="$2"; N="$3"; ROUNDS="$4"
FILES=""; for f in "$CASE"/*.xlsx; do FILES="$FILES --file $f"; done
i=1; while [ "$i" -le "$N" ]; do
  "$HERE/run.sh" --prompt-file "$CASE/prompt.txt" $FILES --optimization-rounds "$ROUNDS" \
      --name "${NAME}_r$(printf %02d "$i")" --timeout 1500 2>&1 | grep -E "^\[headless\] (<<<|outcome|run dir)|not found|not set" | cut -c1-200
  i=$((i+1))
done
