#!/bin/sh
# Usage: mas_harness/run_batch.sh <dataset-dir> <name> <n-runs> <optimization-rounds> [timeout-s, default 1500] [prompt file in the dataset dir, default prompt.txt]
HERE="$(cd "$(dirname "$0")" && pwd)"; CASE="$1"; NAME="$2"; N="$3"; ROUNDS="$4"; TIMEOUT="${5:-1500}"; PROMPT="${6:-prompt.txt}"
FILES=""; for f in "$CASE"/*.xlsx; do FILES="$FILES --file $f"; done
i=1; while [ "$i" -le "$N" ]; do
  "$HERE/run.sh" --prompt-file "$CASE/$PROMPT" $FILES --optimization-rounds "$ROUNDS" \
      --name "${NAME}_r$(printf %02d "$i")" --timeout "$TIMEOUT" 2>&1 | grep -E "^\[headless\] (<<<|outcome|run dir)|not found|not set" | cut -c1-200
  i=$((i+1))
done
