#!/bin/sh
# E7, C: 3 more fresh runs (so that E7's C set is 5 fresh runs), after E12 in the direct lane.
cd "$(dirname "$0")/../.." || exit 1
L=experiments/rerun_2026-11/logs
while ! grep -q "=== E12 done" $L/queue.log; do sleep 30; done
echo "=== E7c start $(date '+%F %H:%M')" | tee -a $L/queue.log
UV_ENV_FILE=.env.azure uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py C 3 --model gpt-6.1-terra --tag _rr_terra > $L/E7c.log 2>&1
echo "=== E7c done $(date '+%F %H:%M')" | tee -a $L/queue.log
