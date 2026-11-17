#!/bin/sh
# Rerun of all experiments on one setup; see PLAN.md in this folder.
# Usage: experiments/rerun_2026-11/run.sh E4 E3 E7 ...   (experiments run in the order given)
# Everything runs one at a time. Progress: logs/queue.log; per experiment: logs/<ID>.log
cd "$(dirname "$0")/../.." || exit 1
REPO=$PWD; LOGS=$REPO/experiments/rerun_2026-11/logs; mkdir -p "$LOGS"
export UV_ENV_FILE=.env.azure
TIMEOUT=1800; ROUNDS=2; N=3

mas() {  # mas <mas dir> <models: 4o|terra> <dataset dir> <prompt file> <name>
  dir=$1; models=$2; ds=$3; pf=$4; name=$5
  if [ "$models" = terra ]; then
    m="HEADLESS_LLM_MODEL=gpt-6.1-terra HEADLESS_LLM_CODE_MODEL=gpt-6.1-terra HEADLESS_LLM_DEFAULT_TEMPERATURE=1"
    [ "$dir" = mas2024 ] && m="$m HEADLESS_STRUCTURED_OUTPUT_METHOD=json_schema"
  else
    m="HEADLESS_LLM_MODEL=gpt-4o-mini HEADLESS_LLM_CODE_MODEL=gpt-4o"
  fi
  echo "--- $name $(date +%H:%M)"
  env $m MAS_DIR=$REPO/$dir mas_harness/run_batch.sh "datasets/$ds" "$name" $N $ROUNDS $TIMEOUT "$pf"
}

direct() {  # direct <model> <tag> [extra args]
  model=$1; tag=$2; shift 2
  R="uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py"
  echo "--- direct $tag $(date +%H:%M)"
  $R D 5 --model "$model" --tag "_rr_${tag}_orig" --prompt prompt.txt "$@"
  $R D 5 --model "$model" --tag "_rr_${tag}_rev" --prompt prompt_revised.txt "$@"
  $R C 3 --model "$model" --tag "_rr_${tag}" "$@"
}

v2set() {  # v2set <models>: A, B, D revised; C; D original
  mas mas2025v2 "$1" A_pilot_rotation prompt_revised.txt "rr_A_v2_$1_rev"
  mas mas2025v2 "$1" B_pilot_rotation_with_children prompt_revised.txt "rr_B_v2_$1_rev"
  mas mas2025v2 "$1" C_reconstructed prompt.txt "rr_C_v2_$1"
  mas mas2025v2 "$1" D_synthetic prompt_revised.txt "rr_D_v2_$1_rev"
  mas mas2025v2 "$1" D_synthetic prompt.txt "rr_D_v2_$1_orig"
}

origset() {  # origset <mas dir> <models> <label>: A-D, original texts
  mas "$1" "$2" A_pilot_rotation prompt.txt "rr_A_$3_$2"
  mas "$1" "$2" B_pilot_rotation_with_children prompt.txt "rr_B_$3_$2"
  mas "$1" "$2" C_reconstructed prompt.txt "rr_C_$3_$2"
  mas "$1" "$2" D_synthetic prompt.txt "rr_D_$3_$2"
}

for e in "$@"; do
  echo "=== $e start $(date '+%F %H:%M')" | tee -a "$LOGS/queue.log"
  case $e in
    E1) origset mas2025 4o mas2025 ;;
    E2) origset mas2025 terra mas2025 ;;
    E3) v2set 4o ;;
    E4) v2set terra ;;
    E5) origset mas2024 4o mas2024 ;;
    E6) origset mas2024 terra mas2024 ;;
    E7) direct gpt-6.1-terra terra ;;
    E8) direct gpt-4o gpt-4o ;;
    E9) direct gpt-4o-mini gpt-4o-mini ;;
    E10) R="uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py"
         S=direct_llm/skills/finnish-daycare-scheduling/SKILL.md
         $R D 5 --model gpt-6.1-terra --tag _rr_terra_skill --skill $S; $R C 3 --model gpt-6.1-terra --tag _rr_terra_skill --skill $S ;;
    E11) R="uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py"
         $R D 3 --model gpt-6.1-terra --tag _rr_terra_sim --sim-user; $R C 3 --model gpt-6.1-terra --tag _rr_terra_sim --sim-user ;;
    *) echo "unknown experiment $e" ;;
  esac > "$LOGS/$e.log" 2>&1
  echo "=== $e done $(date '+%F %H:%M')" | tee -a "$LOGS/queue.log"
done
echo "=== queue done $(date '+%F %H:%M')" | tee -a "$LOGS/queue.log"
