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
* Task texts: A, B and D use `prompt_revised.txt`, which separates primary requirements from
  secondary goals; C uses its own prompt. The pilot's original text (`prompt.txt` in A, B, D) is
  not used: its author is unknown and it contradicts itself (the ratios are listed as "Hard
  Constraints" but the goals ask to "minimize violations of staffing ratios"). Its effect is
  documented by the smoke runs of 17 Nov and the reused direct runs below.
* Run names start with `rr_` so that they are easy to tell from the archived runs.

## Run list

| ID | System | Model | Datasets | Runs to make | Est. time | Est. cost |
|---|---|---|---|---|---|---|
| E1, E2 | MAS 2025 as delivered | – | dropped: its flaws are documented (fix-loop analysis, archived results) | 0 | – | – |
| E3 | MAS 2025 v2 | 4o | A, B, C, D × 3 | 12 | 1 h | < €1 |
| E4 | MAS 2025 v2 | Terra | A, B, C, D × 3 | 12 | 1.2 h | ~€4 |
| E5, E6 | MAS 2024 | – | dropped: no longer part of the comparison | 0 | – | – |
| E7 | Direct prompt | Terra | A, B, D × 5; C × 2 (+ 3 reused) | 17 | 20 min | ~€1.5 |
| E8 | Direct prompt | gpt-4o | A, B, C, D × 5 | 20 | 10 min | < €1 |
| E9 | Direct prompt | gpt-4o-mini | A, B, C, D × 5 | 20 | 10 min | < €0.2 |
| E10 | Direct prompt + domain skill | Terra | D × 5, C × 3, original text, all reused | 0 | – | – |
| E11 | Direct prompt + simulated manager | Terra | D × 3, C × 3, original text, all reused | 0 | – | – |

A and B have no rule checker (no staff profiles). Direct answers for them use the same weekly
format as D (weeks 18–21) and are checked for format; the score records names used, empty
cells and repeats. The B prompt includes the children's attendance sheet (about 40k tokens).

Reused runs: the 22 direct runs with `gpt-6.1-terra` made on 17 Nov 2026 between 10:58 and 11:25
were made on this setup (Azure, 16384-token cap stated in the prompt, `max_completion_tokens`).
They were moved back from the archive to `runs/` under their original names: `*_directC_terra_r0*`
(3 of E7's C runs), `*_directD_terra_r0*` (D with the original text, kept as the comparison with
the pilot text), `*_direct?_terra_skill_r0*` (E10), `*_direct?_terra_sim_r0*` (E11). The direct runs
of 16 Nov (OpenRouter, `gpt-6.1-terra-pro` and gpt-4o) stay in the archive.

Total to make: 81 runs, about 3 hours, about €7. Estimates for the MAS runs come from single
runs and may be off by a factor of two.

Order: E4, E3, E7, E8, E9.

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
