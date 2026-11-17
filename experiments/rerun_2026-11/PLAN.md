# Rerun of all experiments on one setup (planned 17 Nov 2026)

## Why

The results so far were collected over two days with different providers (OpenRouter, then
Azure), models (`gpt-6.1-terra-pro`, then `gpt-6.1-terra`), harness versions and, for some runs,
no token counts. The MAS design changes (v2) and the revised task text worked in single smoke
runs: C with all 11 rules satisfied, D at 10.8 missing staff-hours a week. To compare like with
like, every experiment is run again on the same setup, with repetitions.

## Archive

* Raw runs of 16–17 Nov 2026: moved to the private folder
  `eval_runs/archive_2026-11-17_before_rerun/` (94 runs).
* Aggregated results as of 17 Nov: `results/archive/2026-11-17_before_rerun/`. The files directly
  in `results/` stay as they are until the rerun results replace them.

## Common setup

* Provider: Azure AI Foundry (`UV_ENV_FILE=.env.azure`), deployments `gpt-4o-mini`
  (2024-07-18), `gpt-4o` (2024-11-20) and `gpt-6.1-terra` (2026-10-26). Prices on 17 Nov 2026
  for `gpt-6.1-terra`: €1.08 / M input, €0.06 / M cached input, €5.39 / M output.
* "4o" below means the MAS's own pairing: gpt-4o-mini for the agents, gpt-4o for code.
  "Terra" means `gpt-6.1-terra` for both (`HEADLESS_LLM_DEFAULT_TEMPERATURE=1`; MAS 2024 also
  `HEADLESS_STRUCTURED_OUTPUT_METHOD=json_schema`).
* Harness at the commit that starts the rerun: token usage logged for every call, output cap
  16384, 2 optimisation rounds, fixed decisions (no simulated user unless stated), 50-step limit,
  timeout 1800 s per MAS run. MAS runs one at a time; direct runs one at a time.
* Task texts: `prompt.txt` is the pilot's original text (A, B, D) or the C prompt;
  `prompt_revised.txt` (A, B, D) separates primary requirements from secondary goals.
* Run names start with `rr_` so that they are easy to tell from the archived runs.

## Run list

| ID | System | Model | Datasets × task text | Runs | Est. time | Est. cost |
|---|---|---|---|---|---|---|
| E1 | MAS 2025 as delivered (bit-rot patch only) | 4o | A, B, C, D × original | 12 | 45 min | < €1 |
| E2 | MAS 2025 as delivered | Terra | A, B, C, D × original | 12 | 3.5 h (most stop at the step limit) | ~€15 |
| E3 | MAS 2025 v2 | 4o | A, B, D × revised; C; D × original | 15 | 1 h | < €1 |
| E4 | MAS 2025 v2 | Terra | A, B, D × revised; C; D × original | 15 | 1.5 h | ~€5 |
| E5 | MAS 2024 with the evaluation patch | 4o | A, B, C, D × original | 12 | 45 min | < €1 |
| E6 | MAS 2024 with the evaluation patch | Terra | A, B, C, D × original | 12 | 2–3 h | ~€10 |
| E7 | Direct prompt | Terra | D × original (5), D × revised (5), C (3) | 13 | 15 min | ~€1 |
| E8 | Direct prompt | gpt-4o | as E7 | 13 | 5 min | < €0.5 |
| E9 | Direct prompt | gpt-4o-mini | as E7 | 13 | 5 min | < €0.1 |
| E10 | Direct prompt + domain skill | Terra | D × original (5), C (3) | 8 | 10 min | ~€0.6 |
| E11 | Direct prompt + simulated manager | Terra | D × original (3), C (3) | 6 | 25 min | ~€1 |

Total if all are run: 131 runs, about 10–11 hours, about €35. Estimates for the MAS runs come from
single runs today and may be off by a factor of two.

Suggested order (the core comparison first, the long as-delivered Terra runs last):
E4, E3, E7, E8, E9, E1, E5, then E10, E11, E6, E2.

Not repeated: the earlier OpenRouter runs with `gpt-6.1-terra-pro` (that model is not deployed
on Azure); they stay in the archive and in the README as earlier results.

## Scoring

* C: `datasets/C_reconstructed/check_schedule.py` (all 11 rules) on the roster each round's
  program printed or wrote; `score_presence_output.py` for per-slot presence output.
* D: `synthetic_daycare.py check` for weekly rotations, `score_daily_detail.py` for rosters given
  per day. The best known rotation has 10.9 missing staff-hours a week.
* A, B: round classification as before (no checker; no ground truth for the ratios).
* MAS runs: `fix_loop_analysis.py` on every run; rounds classified as in
  `results/mas*_round_classification.csv`; tokens and cost from `summary.json`.

## Starting

`experiments/rerun_2026-11/run.sh E4 E3 E7 …` runs the listed experiments in that order and logs
to `experiments/rerun_2026-11/logs/` (git-ignored). Nothing is started without the user's go.
