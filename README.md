# AIming for productivity? Staff scheduling pilot: evaluation

<img src="images/eu_co_funded_en.jpg" alt="Co-funded by the European Union" width="400">

In this pilot of the ERDF-funded [*AIming for productivity?* (*vAI:lla tuottavuutta?*)](https://projektit.seamk.fi/alykkaat-teknologiat/vailla-tuottavuutta/) project, a multi-agent
system (MAS) was evaluated on weekly staff rostering for a Finnish daycare. The MAS turns a task
description and attached Excel data into Python optimisation code, runs it in Docker, analyses the
output and iterates as needed or requested by the user.

The MAS was originally developed by Joni Honkanen in the AKKE-funded GPT-Lab Seinäjoki project:
<https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer>. Development of the tool was not part of the
*AIming for productivity?* (*vAI:lla tuottavuutta?*) project and it is not part of this repository. However,
adapting the MAS tool to this purpose and its evaluation were done in *AIming for productivity?* 
(*vAI:lla tuottavuutta?*). 

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
| MAS 2025 version, gpt-4o / gpt-4o-mini, datasets A–D (plus 2 C reruns with the counter fix) | 12 + 2 | 28 + 1 | 11 + 1 | 0 |
| Direct prompt, `openai/gpt-6.1-terra-pro`, dataset D | 5 | – | – | 5 valid tables |
| Direct prompt, `openai/gpt-6.1-terra-pro`, dataset C | 3 | – | – | 3 satisfy all 11 rules |
| Direct prompt, current prompt, without / with the domain skill, dataset D | 5 / 5 | – | – | 5 / 5 valid tables; mean 11.5 / 34.5 missing staff-hours a week |
| Direct prompt, current prompt, without / with the domain skill, dataset C | 3 / 3 | – | – | 3 / 3 satisfy all 11 rules |

* **The MAS produced no usable roster.** The typical failures were infeasible models caused by the generated code's own bugs, schedules that are structurally impossible, output at the wrong decision level, and the input history reprinted instead of new weeks. 55 of 98 code executions crashed, and 3 of 16 runs stopped at LangGraph's 25-step limit.
* **The MAS's self-assessment was unreliable.** It declared success in 25 of 43 rounds, none of which was usable.
* **The 2025 version of the MAS did no better.** It has shift-scheduling instructions written for this kind of task, and it classified every run as shift scheduling and chose a heuristic. Of its 28 analysed rounds, 12 reprinted the input history without new weeks, 11 were structurally impossible (for example the same two people in every shift, or one name per row), 3 were at the wrong decision level (groups instead of names), 1 broke the critical rules badly and 1 produced nothing. On dataset C, 68–79% of group time was understaffed and nobody worked the contracted 38 h 15 min. 54 of 82 code executions failed. It rated 11 rounds as achieved. In 15 rounds the program wrote the roster to an Excel file and printed only a confirmation such as "saved to …xlsx". The output analyser sees only the printed output, so it never saw these rosters, yet it rated 9 of them as achieved. Two runs crashed on a routing bug in the MAS (see [Setup](#setup)); with the fix, one rerun stopped at the step limit. The other produced one round (46% of group time understaffed, rated achieved) and then hit the 25-minute timeout while a generated heuristic ran.
* **A newer model did not help inside the MAS.** It wrote 390–510-line programs that recognised missing policy decisions, but the fixed workflow gave it no way to ask about them or to fix its Docker environment. All three runs stopped at the step limit.
* **The same newer model prompted directly solved the task.**
  * On dataset C, all 3 runs satisfied every rule on the first answer.
  * On dataset D, all 5 runs produced valid tables with 10.9–14.5 missing staff-hours a week (mean 12.8). For comparison, the best known schedule has 10.9, the company's own rotation replayed has 17.4 and random rotations about 20.7.
  * The weak point was rotation: the same person stayed in the same shift in consecutive weeks 4–8 times per run.
  * Repeated with the current prompt (16384-token cap stated in it): C 3/3 satisfied every rule again; D 5/5 valid with 10.9–12.8 missing staff-hours a week (mean 11.5), same-shift repeats 6–10. gpt-4o on the same prompt: D 16.0–39.6, C 0/3 meeting all rules.
* **The domain skill made D worse.** With `--skill`, the newer model still satisfied every rule on C (3/3), but on D it left the part-time assistant unscheduled in every week of all 5 runs: three full shifts would exceed the assistant's 19:08 weekly target, and the skill says part-time staff work only their contracted hours. Missing staff-hours rose to 34.1–35.6 a week (mean 34.5), three times the runs without the skill. The model explained the omission and listed the resulting gaps, as the skill asks, but it put the hour target before the ratio, against the skill's own priority order. For gpt-4o the skill made no clear difference (D 19.7–39.7, C 0/3).
* **A simulated manager did not improve the direct answers.** With the persona of `mas_harness/sim_user/SKILL.md` reviewing each answer, C was accepted in 2 of 3 trials; in the third the manager gave up because the roster stayed a long CSV list with staff IDs, although it met every rule. On D the manager accepted neither completed trial (13.1 and 13.3 missing staff-hours a week, about the same as without the manager); a third trial was stopped and is not counted.
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

### Where each dataset comes from

* **A: the pilot as it was.** The task description written for the pilot and the daycare's real 11-slot shift rotation table for weeks 5–17. Staff names are replaced with pseudonyms. This is the closest to what the MAS saw in the pilot, but it holds too little data to build or check a roster: no staff groups, hours or children.
* **B: A with the pilot-era child data.** A synthetic child attendance table found among the pilot material, added to A. It was made during the pilot as test input, but it does not describe the daycare in the task: its group sizes differ, and it has no children under 3. B shows what the MAS does with richer but mismatched input.
* **C: a reconstruction from the MAS thesis.** When this evaluation started, the original thesis inputs were not available. C rebuilds the daycare example described in Joni Honkanen's thesis on the MAS (section 6.2.4) as a complete, self-consistent task. The Finnish statutory staffing ratios come from the Early Childhood Education and Care Act and Decree. Children, staff and care times are generated with a fixed random seed, and the task prompt was written for C. The thesis gives no sizes, so the sizes were chosen for this evaluation. They describe an ordinary three-group daycare in which each group needs three adults at peak: 11 children under 3 (12 ratio units with one special-needs child, 1:4), 19 children aged 3–4 (20 units, 1:7) and 20 pre-schoolers (1:7), 50 in all. A 38 h 15 min week is 7 h 39 min a day, and the daycare is open 10.5 hours, so each group needs four employees to cover the opening hours. With one floating employee, that is 13. All employees are full-time; C does not model part-time contracts. It differs from the pilot in two ways:
  * The roster is a free-shift roster: the tool chooses each employee's start and end time every day, instead of filling fixed rotation slots.
  * It is solvable by construction. `make_case.py` builds a schedule that meets all 11 rules, so a perfect answer is known to exist, and any failure is the tool's.
* **D: a synthetic daycare for the pilot task.** The pilot's task description, rotation slots and rotation history, combined with a synthetic daycare that matches the daycare's real number of children per age group: 15 under 3, 25 over 3 and 5 in a mixed group. Staff profiles (groups, roles, weekly hours, vacations) are invented to fit the rotation table. D is the most realistic test of the pilot task, but it is not fully solvable. With fixed slots, home groups and the holiday weeks, every roster found leaves some understaffing (the best found has 10.9 missing staff-hours per week), so D is scored by how small the gaps are rather than pass or fail.

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
* [uv](https://docs.astral.sh/uv/), which provides Python 3.11 and the dependencies on the fly;
* Docker with the Compose V2 plugin (`docker compose version`), needed only for the MAS experiments;
* an API key for OpenAI LLM models.

1. Clone this repository and the MAS at the evaluated commit. The harness expects the MAS in `./mas2024`, or wherever `MAS_DIR` points.

   ```bash
   git clone https://github.com/GPT-Laboratory/aiming_for_productivity_staff_scheduling_pilot_evaluation.git
   cd aiming_for_productivity_staff_scheduling_pilot_evaluation
   git clone https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer.git mas2024
   git -C mas2024 checkout 7656ad92289f27e37e51a38657ed18f042dca650
   ```

   For the patched variant of the MAS, apply the evaluation patch on top of that commit:

   ```bash
   git -C mas2024 apply ../mas_harness/mas_eval_patches.diff
   ```

   The patch fixes bit rot and gaps against the intended use, without changing prompts, models or agent logic:
   * it calls `docker compose`, because Compose V1 is no longer available;
   * it adds `numpy` when the requirements list PuLP, because PuLP 3.3 needs numpy but does not install it;
   * it gives the code fixer the tail of the build and run log, because build and start-up errors used to reach it as a single line;
   * it regenerates the Docker files after a fix, because the fixer could not repair a broken Dockerfile or compose file;
   * it asks the user what to change when they request a new plan, and lets them give optional feedback for the next round;
   * it sets the LangGraph step limit explicitly to 50 instead of the implicit default of 25.

   The original results were produced without this patch.

   The MAS has a 2025 successor, [heuristic-multi-agent-system](https://github.com/JoniHonkanen/heuristic-multi-agent-system) (Feb–May 2025), which adds problem classification, a heuristic agent and problem-specific instructions, including instructions for shift scheduling. To run it instead, clone it and point `MAS_DIR` at it:

   ```bash
   git clone https://github.com/JoniHonkanen/heuristic-multi-agent-system.git mas2025
   git -C mas2025 checkout e8c2077
   git -C mas2025 apply ../mas_harness/mas2025_eval_patches.diff   # Compose V2, PuLP/numpy, fix-counter reset
   export MAS_DIR=$PWD/mas2025
   ```

   Three things differ when it runs:
   * `run.sh` detects it and installs `mas_harness/requirements-mas2025.txt`, resolved as of its commit date. Its own `requirements.txt` is a pip freeze that does not resolve.
   * The harness supports its Chainlit 2 button format.
   * The harness gives its unused Claude client a placeholder key, because the client refuses to start without one.

   The patch also fixes one bug in the MAS's own control flow. After 4 failed fixes, MAS 2025 regenerates the code, but it resets the fix counter only in its new-round agent. The next execution therefore routes to a node that is missing from the routing table and the run crashes with `KeyError: 'heuristic'` (or `'code_generator'`); this happened in 2 of the first 12 runs, both on dataset C. The patch resets the counter when code is regenerated, as the new-round agent already does. Runs that keep failing then stop at the MAS's own step limit of 50. Runs made with the patch are named `*_mas2025fix_*`.

2. Configure the API access:

   ```bash
   cp .env.example .env
   # edit .env: set OPENAI_API_KEY; keep OPENAI_API_BASE for OpenRouter, or delete it for OpenAI
   ```

   With OpenAI directly, also change the model ids, because OpenAI model ids have no `openai/` prefix.

   To use a second provider (for example Azure for one model), put its settings in `.env.<name>` and prefix a command with `UV_ENV_FILE=.env.<name>`. This works for the MAS harness and the direct-LLM script alike. Values in that file take precedence over `.env`, and each run records its endpoint and models. The direct-LLM script and the simulated manager send the output cap as `max_completion_tokens`, which reasoning models on OpenAI and Azure require, and as `max_tokens` on OpenRouter.

   The Terra runs from 17 Nov 2026 onwards use `gpt-6.1-terra` (not the pro variant) on Azure. The gpt-4o and gpt-4o-mini results were not rerun there: they come from OpenRouter's `openai/gpt-4o` and `openai/gpt-4o-mini`, whose snapshots the logs do not record. Azure serves gpt-4o-2024-11-20 and gpt-4o-mini-2024-07-18, so gpt-4o results on Azure need not match the earlier ones.

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

# a batch: <dataset dir> <name> <runs> <optimization rounds> [timeout s, default 1500]
mas_harness/run_batch.sh datasets/D_synthetic D_mas 5 2

# newer-model arm: the same, with both MAS models overridden
HEADLESS_LLM_MODEL=openai/gpt-6.1-terra-pro HEADLESS_LLM_CODE_MODEL=openai/gpt-6.1-terra-pro \
    mas_harness/run_batch.sh datasets/D_synthetic D_mas_newmodel 3 2
```

Runs take 2–5 minutes each with gpt-4o and up to 25 minutes with the newer model; the harness timeout is 25 minutes per run in batches.

How the harness works:
* **No user interface.** It replaces the MAS's Chainlit UI with a stand-in module and calls the MAS's own `main()` handler, so file ingestion, prompt formatting and the LangGraph workflow are the original code.
* **Fixed human decisions.** The plan is always accepted, and `--optimization-rounds` further rounds are requested before the final report.
* **Full recording.** Every agent step's input, output and state, the generated code, the Docker files and a run summary go to `runs/<timestamp>_<name>/`. Files the executed program writes (for example an Excel roster) are copied to the step's `outputs/` folder. Runs made before this was added lost those files; `mas_harness/reexecute_rounds.py <run>` re-executes the program behind each analysed round to recover them. Most programs are randomised, so a re-execution is not guaranteed to reproduce the original output.
* **Fix-loop analysis.** `mas_harness/fix_loop_analysis.py <run> ...` goes through the recorded run–fix loops: for each failed program execution it shows what the code fixer was given, triages the cause from the saved Dockerfile and compose.yaml (variables the MAS never sets, input files not reachable in the container) and says whether the cause lies in a file the fixer can edit. It reruns nothing unless `--replay` is given, which rebuilds the failed steps to recover errors the MAS did not pass on.
* **Compose wrapper.** `mas_harness/bin/docker-compose` forwards the MAS's `docker-compose` calls to Compose V2.
* **Model override.** `HEADLESS_LLM_MODEL` and `HEADLESS_LLM_CODE_MODEL` replace the MAS's two models (gpt-4o-mini and gpt-4o) without changing its code; this is how the newer-model arm was run. `OPENAI_API_BASE` selects the provider.
* **Temperature.** Reasoning models such as gpt-6.1-terra accept only the default temperature. The 2025 MAS sets `temperature=0` on its code model, and the 2024 MAS's LangChain version sends 0.7 by default; both are rejected with HTTP 400 on OpenAI and Azure. `HEADLESS_LLM_DEFAULT_TEMPERATURE=1` leaves the temperature out of the requests of both models. Each run records the temperatures in `summary.json`. (OpenRouter ignored the setting, so the earlier Terra runs there needed no override.)
* **Structured replies.** The agents ask for structured (JSON) replies through LangChain. The 2024 MAS's LangChain uses function calling for that, which gpt-6.1-terra on Azure's chat-completions endpoint refuses while reasoning is on (HTTP 400; the agent then fails with a `KeyError`). `HEADLESS_STRUCTURED_OUTPUT_METHOD=json_schema` makes it use a JSON-schema response format instead, which is what the 2025 MAS's newer LangChain does by default. The schemas and prompts are unchanged.
* **Root-owned leftovers.** Docker Compose creates missing bind-mount folders as root, and a generated program may write into them. The harness clears the MAS's `generated/` folder before each run and removes such leftovers through a container.
* **Output cap.** The 2025 MAS hard-codes `max_tokens=4096` for its code model (the original gpt-4o limit). A whole program comes back in one structured reply, so the harness raises the cap to 16384 (current gpt-4o's limit), or to `HEADLESS_LLM_CODE_MAX_TOKENS`. The 2024 MAS sets no cap and is left alone unless the variable is set. Replies cut off at the cap are logged as `llm_truncated` events.
* **Unchanged limits.** The MAS's own step limit is kept: LangGraph's default of 25 for MAS 2024, 50 set by MAS 2025 itself. `--recursion-limit` changes it.
* **Side effect.** The MAS runs `docker image prune -f` after every execution.

`mas_harness/make_packets.py runs/<run>...` writes a readable evaluator packet per run, showing each round's code, trimmed output and the MAS's own verdict.

## Running the direct-LLM experiment

```bash
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py D 5
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py C 3
```

* **Setup.** The model receives the task description and the data serialised the same way the MAS serialises Excel files. It is told it has no tools and must not write a program. Each reply is capped at 16384 output tokens, reasoning included (the same cap as the MAS code model in the harness), and the system prompt says so, so that the model budgets its reasoning. Earlier direct runs used a cap of 30000 and did not mention it. It is also given a fixed answer format; for D this includes the convention for reading the table.
* **Revision loop.** After each answer, a structural check looks only at format: the table parses, names are known, nobody is in two shifts at once, all weeks are present. Any problems are sent back, with at most 4 answers. The rule checkers run only afterwards, and their results are never shown to the model.
* **Domain skill (optional).** `--skill direct_llm/skills/finnish-daycare-scheduling/SKILL.md` appends a skill to the system prompt. It is a copy of the simulated manager's `SKILL.md`, rewritten for the system that builds the roster: what the manager cares about, the Finnish staffing and working-time rules, a short method, and how to handle staffing gaps (keep the ratio as the requirement, minimise the gaps and report them). It says nothing about the datasets or the checkers. The gap paragraph settles the ratio ambiguity of the pilot task text, so runs with the skill are not a test of the task text as written.
* **Configuration.** The model defaults to `openai/gpt-6.1-terra-pro`; change it with `--model`. The provider comes from `OPENAI_API_BASE` in `.env`.

## Results

| File | Contents |
|---|---|
| `results/experiments_summary.csv` | per experiment: runs, completed, stopped at step limit, code executions and failures, analysed rounds, rounds self-rated as achieved, usable schedules |
| `results/mas_round_classification.csv` | every analysed MAS round classified by failure type, with the MAS's own verdict and a short note |
| `results/mas2025_round_classification.csv` | the same for the 2025 version, plus how faithfully each round's program re-executed (see below) |
| `results/direct_llm_runs.csv` | direct-LLM runs with checker scores. Run names give the variant: `direct` (first runs, 30000-token cap), `noskill` and `skill` (current prompt, without and with `--skill`), `gpt-4o_*` (gpt-4o on the same prompt), `sim` (reviewed by the simulated manager) |
| `results/cost_by_experiment.csv` | API calls, tokens and cost per experiment, from the OpenRouter activity export of 16 Nov 2026, split by timestamp; the export ends before the last 4 direct runs |
| `results/scoresheet_template.csv` | blank rubric for human evaluators, one row per MAS round |

The 2025 runs were made before the harness kept the files the programs write, so their rosters were recovered by re-executing each round's saved program on the same input (`mas_harness/reexecute_rounds.py`). 21 of the 29 re-executions (28 rounds plus the rerun's one) reproduced the original printed output exactly, or the last 4000 characters the MAS kept; the other 8 differ because the heuristics are randomised, and their output has the same form. For dataset C, programs that printed staff presence per time slot were scored with `datasets/C_reconstructed/score_presence_output.py`, which places the floating employee where it helps most.

The round classification is the third evaluator's (an AI-assisted evaluation harness). Two human evaluators score the same rounds with the template. The raw run logs are not published.

To reproduce the tables from your own runs:

```bash
python3 analysis/aggregate_runs.py runs results/experiments_summary.csv
python3 analysis/cost_by_experiment.py openrouter_activity.csv --runs runs --utc-offset 2
```

## Data and anonymisation

* **Children and staff.** No real child data was shared nor used. All child records and staff profiles (groups, roles, hours, vacations) in datasets B, C and D are synthetic.
* **Staff names.** Staff names in the company's rotation table were replaced with `Staff01`–`Staff11` before anything was sent to an LLM provider. For publication the pseudonyms were randomly relabelled again, so their numbering carries no information about the real names, and the role label was translated to `Assistant`. The synthetic staff profiles were relabelled with them, so every computed figure is unchanged. No mapping exists in this repository.
* **Company data.** The shift slot times and the rotation pattern are the company's, published in pseudonymised form. Neither the company nor the daycare is named. The rotation file and its sheet were renamed to English (`shift_rotation.xlsx`, `Shift rotation`), and a Finnish free-text note in it was translated.
* **Group names.** The three group names in the original prompt were replaced *after the runs* with Robin, Finch and Lark, consistently in the prompts and datasets.
* **Effect on reproduction.** The runs received the original group names, pseudonym numbering and file name. These changes are cosmetic and leave every computed figure unchanged, but a re-run sees slightly different text than the logged runs did.
* **Run logs.** The raw logs are not published.

## Limitations

* The datasets are synthetic. The checkers measure the written rules, not whether the daycare would accept a roster. That requires the company's validation, which is pending.
* For dataset D, the best-known reference was found heuristically and is not a proven optimum. The human-baseline figure depends on the synthetic group assignment.
* Dataset D's workforce is partly assumed. The rotation table gives only the names in each slot, and the task text says only that "a few" employees work 30 h 35 min or 19 h 8 min. Their groups and roles, and which people work part-time, were chosen for this evaluation: one caregiver works 30 h 35 min Mon–Thu, the assistant 19 h 8 min Mon–Wed, and everyone else full-time. The person who disappears from the rotation in week 13 is left out. These choices look plausible, but the missing staff-hours figures, including the replayed human baseline, depend on them.
* In dataset D, working hours are reported but not scored. Part-time contracts affect coverage only through working days: a person covers their slot on the days they work. Separately, the checker's `working_hours_info` compares each person's weekly hours with their target, pro-rated for days off. It classifies each person-week as within ±1 h, as a minor deviation (within ±5 h) or as needing attention. With fixed slots, hours follow from working days and slot length (7 h 40 min to 8 h), so most deviations are structural and appear in every roster, the daycare's own included:
  * the assistant is about 4 h a week over target;
  * full-timers in the 8-hour slots are about 1.8 h over.

  Deviations like these are normal in practice and can be agreed locally, so they are not counted as rule violations. The best-known and replayed human rosters both have 11–12 minor deviations in 44 person-weeks and none needing attention.
* The human decisions in the MAS were fixed, so the effect of interactive steering was not measured.
* There were 3–5 runs per condition: enough to show consistent failure or success, not to estimate exact rates.

## License

MIT, see [LICENSE](LICENSE).
