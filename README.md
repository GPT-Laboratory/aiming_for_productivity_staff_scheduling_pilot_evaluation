# AIming for productivity? Staff scheduling pilot: evaluation

In this pilot of the *AIming for productivity?* (*vAI:lla tuottavuutta?*) project, a multi-agent
system (MAS) was evaluated on weekly staff rostering for a Finnish daycare. The MAS turns a task
description and attached Excel data into Python optimisation code, runs it in Docker, analyses the
output and iterates.

The MAS was developed by Joni Honkanen in the AKKE-funded GPT-Lab Seinäjoki project:
<https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer>. It is not part of this repository.

This repository contains everything used to evaluate it, except the MAS itself:

* a **headless harness** that runs the unmodified MAS repeatably and records every step;
* four **datasets**: the pilot task (pseudonymised) and synthetic, fully specified variants;
* **rule checkers** with reference solutions, so outputs can be scored independently of the MAS's own self-assessment;
* a **direct frontier-LLM experiment** that asks a current model to produce the roster by reasoning alone, with no tools and no code;
* the **aggregated results**.

No personal data is included. See [Data and anonymisation](#data-and-anonymisation).

## Main findings

| Experiment | Runs | Analysed rounds | Rounds the system rated "goal achieved" | Usable schedules |
|---|---|---|---|---|
| MAS, gpt-4o / gpt-4o-mini, datasets A–D | 16 | 43 | 25 | 0 |
| MAS with `openai/gpt-6.1-terra-pro` as both models, dataset D | 3 | 3 | 0 | 0 |
| Direct prompt, `openai/gpt-6.1-terra-pro`, dataset D | 5 | – | – | 5 valid tables |
| Direct prompt, `openai/gpt-6.1-terra-pro`, dataset C | 3 | – | – | 3 satisfy all 11 rules |

* **The MAS produced no usable roster.** The typical failures were infeasible models caused by the generated code's own bugs, schedules that are structurally impossible, output at the wrong decision level, and the input history reprinted instead of new weeks. 55 of 98 code executions crashed, and 3 of 16 runs stopped at LangGraph's 25-step limit.
* **The MAS's self-assessment was unreliable.** It declared success in 25 of 43 rounds, none of which was usable.
* **A newer model did not help inside the MAS.** It wrote 390–510-line programs that recognised missing policy decisions, but the fixed workflow gave it no way to ask about them or to fix its Docker environment. All three runs stopped at the step limit.
* **The same newer model prompted directly solved the task.**
  * On dataset C, all 3 runs satisfied every rule on the first answer.
  * On dataset D, all 5 runs produced valid tables with 10.9–14.5 missing staff-hours a week (mean 12.8). For comparison, the best known schedule has 10.9, the company's own rotation replayed has 17.4 and random rotations about 20.7.
  * The weak point was rotation: the same person stayed in the same shift in consecutive weeks 4–8 times per run.
* **Cost was not the limiting factor.** A MAS run with gpt-4o cost $0.04–0.18, a MAS run with the newer model about $1.10, and a direct-prompt run about $0.05.

Our interpretation is that the fixed generate–run–describe workflow was the main bottleneck, more than model capability. Nothing in the loop checks the result against the rules, and information is lost between agents. These conclusions rest on synthetic data and a rule checker, not on validation by the daycare.

## Repository layout

```
datasets/
  A_pilot_rotation/                pilot task prompt + existing rotation (weeks 5-17), staff pseudonymised
  B_pilot_rotation_with_children/  as A + the child attendance table used during the pilot (synthetic)
  C_reconstructed/                 fully specified synthetic task (50 children, 13 staff, 11 rules)
                                   + generator, checker, hand-made reference schedule
  D_synthetic/                     synthetic daycare matching the pilot description (45 children, 11 staff)
                                   + generator/checker, heuristic reference, replayed human baseline
  smoke_cutting_stock/             small cutting-stock task used to smoke-test the harness
mas_harness/                       headless runner for the MAS (no changes to the MAS code)
direct_llm/                        direct frontier-LLM experiment (no tools, simple revision loop)
analysis/                          run aggregation and cost split from an OpenRouter export
results/                           aggregated results (see below)
```

## Datasets

| | Contents | Prompt | Checker |
|---|---|---|---|
| **A** | Original task description and the company's 11-slot shift rotation for weeks 5–17. No staff profiles, groups or child data. | original | – |
| **B** | As A, plus the synthetic child attendance table that was used during the pilot (42 children, 15 days). It does not match the daycare described in the prompt; for example, it has no children under 3. | original | – |
| **C** | Reconstructed full task: 50 children with individual care times, 13 employees, 11 explicit rules (Finnish statutory ratios 1:4 / 1:7 / 1:13, special needs ×2, 38 h 15 min weeks, home groups, rotation, never alone). Provably feasible. | written for C | `check_schedule.py`, all 11 rules |
| **D** | Synthetic daycare built to the task description: 45 children (15 under 3, 25 over 3, 5 mixed; four with ×2/×3 support multipliers), 11 staff with groups, roles, weekly hours and vacations, the 11 shift slots and the rotation history. | original | `synthetic_daycare.py check`, missing staff-hours per week |

All children and staff profiles are invented. The task prompt is the one written for the pilot.

The two checkers model different rules:
* **Dataset C** schedules are lists of shifts per employee and day, and are checked minute by minute against all 11 rules.
* **Dataset D** schedules are weekly rotation tables in the company's format: one row per week, one column per shift. A person in a column works that shift on every day of the week they are available. The checker reports understaffing per group in 10-minute steps, vacation conflicts, duplicates and rotation.

Regenerate the datasets and reference solutions with:

```bash
uv run --no-project --python 3.11 --with-requirements requirements.txt datasets/D_synthetic/synthetic_daycare.py make
uv run --no-project --python 3.11 --with-requirements requirements.txt datasets/C_reconstructed/make_case.py
uv run --no-project --python 3.11 --with-requirements requirements.txt datasets/C_reconstructed/make_reference.py
```

## Setup

Prerequisites:
* Linux (the harness was used on Ubuntu 20.04);
* [uv](https://docs.astral.sh/uv/), which provides Python 3.11 and the dependencies on the fly, so no virtual environment needs to be maintained;
* Docker with the Compose V2 plugin (`docker compose version`), needed only for the MAS experiments;
* an API key for [OpenRouter](https://openrouter.ai/) (as used here) or OpenAI.

1. Clone this repository and the MAS at the evaluated commit. The harness expects the MAS in `./mas`, or wherever `MAS_DIR` points.

   ```bash
   git clone https://github.com/GPT-Laboratory/aiming_for_productivity_staff_scheduling_pilot_evaluation.git
   cd aiming_for_productivity_staff_scheduling_pilot_evaluation
   git clone https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer.git mas
   git -C mas checkout 7656ad92289f27e37e51a38657ed18f042dca650
   ```

2. Configure the API access:

   ```bash
   cp .env.example .env
   # edit .env: set OPENAI_API_KEY; keep OPENAI_API_BASE for OpenRouter, or delete it for OpenAI
   ```

   With OpenAI directly, also delete the two `HEADLESS_LLM_*` lines, because OpenAI model ids have no `openai/` prefix.

3. Check that the MAS runs end to end with the small cutting-stock task. It takes about 2–3 minutes and costs about one cent.

   ```bash
   mas_harness/run.sh --prompt-file datasets/smoke_cutting_stock/prompt.txt \
       --file datasets/smoke_cutting_stock/cutting_stock_problem_data.xlsx \
       --optimization-rounds 1 --name smoke
   ```

   It should end with `[headless] outcome: completed` and a run directory under `runs/`. On the first call, `run.sh` installs the MAS's pinned dependencies into a cached Python 3.11 environment. These are in `mas_harness/requirements-mas.txt`: the MAS's own list, converted to UTF-8, without the Windows-only `pywin32`.

The direct-LLM experiment and the dataset scripts need only uv and the API key, not the MAS or Docker.

## Running the MAS evaluation

```bash
# one run
mas_harness/run.sh --prompt-file datasets/D_synthetic/prompt.txt \
    --file datasets/D_synthetic/synthetic_daycare.xlsx --optimization-rounds 2 --name D_mas_r01

# a batch: <dataset dir> <name> <runs> <optimization rounds>
mas_harness/run_batch.sh datasets/D_synthetic D_mas 5 2

# newer-model arm: the same, with both MAS models overridden
HEADLESS_LLM_MODEL=openai/gpt-6.1-terra-pro HEADLESS_LLM_CODE_MODEL=openai/gpt-6.1-terra-pro \
    mas_harness/run_batch.sh datasets/D_synthetic D_mas_newmodel 3 2
```

Runs take 2–5 minutes each with gpt-4o and up to 25 minutes with the newer model; the harness timeout is 25 minutes per run in batches.

How the harness works:
* **No user interface.** It replaces the MAS's Chainlit UI with a stand-in module and calls the MAS's own `main()` handler, so file ingestion, prompt formatting and the LangGraph workflow are the original code.
* **Fixed human decisions.** The plan is always accepted, and `--optimization-rounds` further rounds are requested before the final report.
* **Full recording.** Every agent step's input, output and state, the generated code, the Docker files and a run summary go to `runs/<timestamp>_<name>/`.
* **Compose wrapper.** `mas_harness/bin/docker-compose` forwards the MAS's `docker-compose` calls to Compose V2.
* **Model override.** `HEADLESS_LLM_MODEL` and `HEADLESS_LLM_CODE_MODEL` replace the MAS's two models (gpt-4o-mini and gpt-4o) without changing its code; this is how the newer-model arm was run. `OPENAI_API_BASE` selects the provider.
* **Unchanged limits.** LangGraph's default limit of 25 steps is kept; `--recursion-limit` raises it.
* **Side effect.** The MAS runs `docker image prune -f` after every execution.

`mas_harness/make_packets.py runs/<run>...` writes a readable evaluator packet per run, showing each round's code, trimmed output and the MAS's own verdict.

## Running the direct-LLM experiment

```bash
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py D 5
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py C 3
```

* **Setup.** The model receives the task description and the data serialised the same way the MAS serialises Excel files. It is told it has no tools and must not write a program. It is also given a fixed answer format; for D this includes the convention for reading the table.
* **Revision loop.** After each answer, a structural check looks only at format: the table parses, names are known, nobody is in two shifts at once, all weeks are present. Any problems are sent back, with at most 4 answers. The rule checkers run only afterwards, and their results are never shown to the model.
* **Configuration.** The model defaults to `openai/gpt-6.1-terra-pro`; change it with `--model`. The provider comes from `OPENAI_API_BASE` in `.env`.

## Results

| File | Contents |
|---|---|
| `results/experiments_summary.csv` | per experiment: runs, completed, stopped at step limit, code executions and failures, analysed rounds, rounds self-rated as achieved, usable schedules |
| `results/mas_round_classification.csv` | every analysed MAS round classified by failure type, with the MAS's own verdict and a short note |
| `results/direct_llm_runs.csv` | direct-LLM runs with checker scores |
| `results/cost_by_experiment.csv` | API calls, tokens and cost per experiment, from the OpenRouter activity export of 16 Nov 2026, split by timestamp; the export ends before the last 4 direct runs |
| `results/scoresheet_template.csv` | blank rubric for human evaluators, one row per MAS round |

The round classification is the third evaluator's (an AI-assisted evaluation harness). Two human evaluators score the same rounds with the template. The raw run logs are not published.

To reproduce the tables from your own runs:

```bash
python3 analysis/aggregate_runs.py runs results/experiments_summary.csv
python3 analysis/cost_by_experiment.py openrouter_activity.csv --runs runs --utc-offset 2
```

## Data and anonymisation

* **Children and staff.** No real child data was used. All child records and staff profiles (groups, roles, hours, vacations) in datasets B, C and D are synthetic.
* **Staff names.** Staff names in the company's rotation table were replaced with `Staff01`–`Staff11` before anything was sent to an LLM provider. For publication the pseudonyms were randomly relabelled again, so their numbering carries no information about the real names, and the role label was translated to `Assistant`. The synthetic staff profiles were relabelled with them, so every computed figure is unchanged. No mapping exists in this repository.
* **Company data.** The shift slot times and the rotation pattern are the company's, published in pseudonymised form. Neither the company nor the daycare is named. The rotation file and its sheet were renamed to English (`shift_rotation.xlsx`, `Shift rotation`), and a Finnish free-text note in it was translated.
* **Group names.** The three group names in the original prompt were replaced *after the runs* with Robin, Finch and Lark, consistently in the prompts and datasets.
* **Effect on reproduction.** The runs received the original group names, pseudonym numbering and file name. These changes are cosmetic and leave every computed figure unchanged, but a re-run sees slightly different text than the logged runs did.
* **Run logs.** The raw logs are not published.

## Limitations

* The datasets are synthetic. The checkers measure the written rules, not whether the daycare would accept a roster. That requires the company's validation, which is pending.
* For dataset D, the best-known reference was found heuristically and is not a proven optimum. The human-baseline figure depends on the synthetic group assignment.
* gpt-4o and gpt-4o-mini were called through OpenRouter in November 2026 and may differ from the versions used during the pilot in spring 2025.
* The human decisions in the MAS were fixed, so the effect of interactive steering was not measured.
* There were 3–5 runs per condition: enough to show consistent failure or success, not to estimate exact rates.

## License

MIT, see [LICENSE](LICENSE).
