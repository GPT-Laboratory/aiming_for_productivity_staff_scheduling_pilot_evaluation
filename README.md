# AIming for productivity? Staff scheduling pilot: evaluation

<img src="images/eu_co_funded_en.jpg" alt="Co-funded by the European Union" width="400">

In a pilot of the ERDF-funded [*AIming for productivity?* (*vAI:lla tuottavuutta?*)](https://projektit.seamk.fi/alykkaat-teknologiat/vailla-tuottavuutta/) project in spring 2025,
a multi-agent system (MAS) was tried on weekly staff rostering for a Finnish daycare. The MAS turns
a task description and attached Excel data into Python optimisation code, runs it in Docker,
analyses the output and iterates as needed or as the user requests. This repository holds the
extended tests and experiments that evaluated the MAS afterwards (November 2026), on the pilot
task and on synthetic, fully specified variants of it.

The MAS was developed by Joni Honkanen in the AKKE-funded [GPT-Lab Seinäjoki project](https://www.tuni.fi/fi/tau/tutkimus/gpt-lab-seinajoki), and later completed as part of his MSc thesis project. Two
different iterations of the tool were included in this evaluation (see [The MAS versions](#the-mas-versions)):

* **2024:** the original LLM code optimizer,
  [ucs-llm-code-docker-optimizer](https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer)
  (an identical copy is [GPT-Laboratory/ai-code-optimizer](https://github.com/GPT-Laboratory/ai-code-optimizer));
* **2025:** the optimization tool derived from it,
  [heuristic-multi-agent-system](https://github.com/JoniHonkanen/heuristic-multi-agent-system),
  which adds problem classification, a heuristic agent and problem-class guidance, including
  guidance for shift scheduling. The pilot most likely used this version, before the fixes
  described here.

Developing the MAS was not part of *AIming for productivity?*, and the MAS is not part of this
repository. Adapting it to staff scheduling and evaluating it were done in *AIming for
productivity?*.

This repository contains everything used to evaluate it, except the MAS itself:

* a **headless harness** that runs the MAS repeatably, without its user interface, and records every step;
* the **patches** applied to the MAS: bit-rot fixes for running it as delivered, and the design changes found in the evaluation (offered upstream as [pull requests](#the-mas-versions));
* four **datasets**: the pilot task (pseudonymised) and synthetic, fully specified variants;
* **rule checkers** with reference solutions, so outputs can be scored independently of the MAS's own self-assessment;
* a **direct frontier-LLM experiment** that asks a current model to produce the roster by reasoning alone, with no tools and no code;
* the **aggregated results**.

No personal data is included. See [Data and anonymisation](#data-and-anonymisation).

## The MAS versions

Joni Honkanen's two repositories hold two different systems. We evaluated them in four
variants:

* **MAS 2024** is
  [ucs-llm-code-docker-optimizer](https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer)
  at commit `7656ad9`, the original LLM code optimizer.
  [GPT-Laboratory/ai-code-optimizer](https://github.com/GPT-Laboratory/ai-code-optimizer) at
  `9a1a7b2` has identical files. Its agents analyse the problem, write the program and its Docker
  files, run it, fix it when it fails, analyse its output and start new rounds. It has no
  problem-specific guidance. Two variants were run:
  * **MAS 2024 (unpatched):** the commit as published.
  * **MAS 2024 + evaluation patch:** with `mas_harness/mas_eval_patches.diff`.
* **MAS 2025** is
  [heuristic-multi-agent-system](https://github.com/JoniHonkanen/heuristic-multi-agent-system) at
  commit `e8c2077` (developed February–May 2025). It is the optimization tool derived from MAS
  2024: it adds problem classification, a heuristic agent and guidance for each problem class,
  among them `SHIFT_SCHEDULING`, which was written for this daycare task. The pilot most likely
  used this version, at this commit or an earlier one, without any of the changes below. Two
  variants were run:
  * **MAS 2025 v1 ("as delivered"):** `e8c2077` with `mas_harness/mas2025_eval_patches.diff`.
  * **MAS 2025 v2 (also "MAS v2"):** v1 plus `mas_harness/mas2025v2_design_patches.diff`.

| Variant | What was changed in the MAS's code | Runs |
|---|---|---|
| **MAS 2024 (unpatched)** | nothing; the harness forwards `docker-compose` to Compose V2 | 16 runs with gpt-4o / gpt-4o-mini on A–D, 3 with `gpt-6.1-terra-pro` on D ([earlier experiments](EARLIER_EXPERIMENTS.md)) |
| **MAS 2024 + evaluation patch** | Compose V2; numpy added next to PuLP; a log tail for the code fixer; Docker files regenerated after each fix; the user's typed answer used for a new plan and between rounds; step limit 50. Unlike v1 below, this changes behaviour. | 3 runs with `gpt-6.1-terra` on D ([earlier experiments](EARLIER_EXPERIMENTS.md)) |
| **MAS 2025 v1 ("as delivered")** | bit-rot fixes only: Compose V2, numpy added next to PuLP, and a reset of the fix counter that avoids a crash. No prompt or model is changed, and the agents' logic is unchanged apart from the counter reset. | 12 runs with gpt-4o / gpt-4o-mini on A–D (made before the counter reset was added; 2 crashed on it), 2 reruns of C with it, 12 runs with `gpt-6.1-terra` on A–D ([earlier experiments](EARLIER_EXPERIMENTS.md)) |
| **MAS 2025 v2** | v1 plus five design changes: the agents are told how the program is built and run; the code fixer can ask for the full log; the fixer can route a fault to the Docker files or give up; the fixer sees its earlier attempts; and the shift-scheduling guidance is rewritten into hard and soft rules in priority order (details in [Setup](#setup)) | the final rerun: E3 (gpt-4o / gpt-4o-mini) and E4 (`gpt-6.1-terra`) on A–D, 5 runs each |

Some settings come from the harness and apply to all four variants, without changing the MAS's
code: the models, the temperature, structured output by JSON schema (MAS 2024 on Azure), the
code model's output cap (MAS 2025: 16384 instead of 4096) and clearing `generated/` between runs.
See [How the harness works](#running-the-mas-evaluation).

**The pull requests** (opened 18 Nov 2026) carry the v1 and v2 changes upstream:

* **heuristic-multi-agent-system**, three PRs:
  * [#1 *Make it run again*](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/1): the v1 fixes, plus model settings read from `.env`. Here
    PuLP is capped below 4 instead of adding numpy, because the numpy errors came from PuLP 4.
  * [#3 *Fixer workflow*](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/3): v2's changes 1–4. It builds on #1.
  * [#2 *Shift-scheduling guidance*](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/2): v2's change 5.
* **ucs-llm-code-docker-optimizer** ([#1](https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer/pull/1), [#2](https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer/pull/2)) **and ai-code-optimizer**
  ([#1](https://github.com/GPT-Laboratory/ai-code-optimizer/pull/1), [#2](https://github.com/GPT-Laboratory/ai-code-optimizer/pull/2)): the first two, ported to MAS 2024.

The PR branches were only smoke-tested; all results here come from the variants above.
`mas_harness/MAS2025_PR_NOTES.md` lists every change with its reason and evidence.

## Main findings

### Final comparison (rerun, 17 Nov 2026)

All experiments were run again on one setup: Azure (EU Data Zone), 5 runs per cell, the revised
task text for A, B and D (see [Datasets](#datasets)), C with its own prompt, token use logged for
every call. Plan, run list and scripts: `experiments/rerun_2026-11/`. "4o" is the MAS's own model
pair (gpt-4o-mini for the agents, gpt-4o for the code); "Terra" is `gpt-6.1-terra` for both.
MAS 2025 v1 and v2 are defined in [The MAS versions](#the-mas-versions).

| Setup | C: rosters meeting all 11 rules | D: missing staff-hours / week, mean (range) | A and B: four-week table with current staff only | Min / run | € / run |
|---|---|---|---|---|---|
| **MAS 2025 v2 · Terra** (E4) | 2 / 5 as picked by the MAS, 3 / 5 in the best round; the rest miss only R10; 0 min understaffed in all 15 rounds | **11.5** (10.3–14.6); 3 of 5 at 10.8, one per-weekday roster at 10.3 | A 0 / 5 (one run planned only week 18, four wrote no table), B 0 / 5 (two runs planned three weeks with Staff08, three wrote no table) | 6.1 | 0.29 |
| MAS 2025 v2 · 4o (E3) | 0 / 5, no roster | no roster (5 / 5) | A 0 / 5 (3 tables, all with Staff08), B 0 / 5 | 2.4 | 0.23 |
| Direct · Terra (E7) | 1 / 5; misses are mostly the staffing ratio | 14.1 (11.2–17.6) | 10 / 10 | 0.6 | 0.02 |
| **Direct · Terra + skill** (E12a) | **4 / 5** | 18.0 (13.0–34.6); one run left the assistant out | A 3 / 5 (Staff08 in 2), B 5 / 5 | 0.7 | 0.02 |
| Direct · gpt-4o (E8) | 0 / 5 | 21.0 (18.1–25.3); 1 invalid | 7 / 10 (Staff08 in 3) | 0.4 | 0.04 |
| Direct · gpt-4o + skill (E12b) | 0 / 5 | 25.9 (17.8–37.1) | 4 / 10 (Staff08 in 6) | 0.3 | 0.04 |
| Direct · gpt-4o-mini (E9) | 0 / 5 | 50.3 (22.0–72.4) | 0 / 10 (Staff08 in all) | 0.2 | 0.005 |
| Direct · gpt-4o-mini + skill (E12c) | 0 / 5 | 36.5 (27.0–50.5); 1 invalid | 0 / 10 (Staff08 in all) | 0.2 | 0.005 |

Baselines for D: the best known rotation misses 10.9 staff-hours a week, the daycare's own
rotation replayed 17.4, random rotations about 20.7. A and B have no rule checker (no staff
profiles); Staff08 appears in the old rotation but is not on the staff any more.
C and D are two different daycares, so their scores cannot be combined, and the replayed rotation
fits the daycare's real pattern to invented staff and children; see
`experiments/rerun_2026-11/COMPARABILITY.md`.

* **With a current model and the design fixes, the MAS does what it was built for.** MAS 2025 v2 with
  Terra completed every run in 14–20 steps (2–10 min; no run near the 50-step limit) and produced
  the best rosters of all setups on D: three of five runs reached 10.8 missing staff-hours a week,
  slightly better than the best known rotation, and a fourth 10.3 with a roster that varies by
  weekday (one sheet per day), which is more flexible than the requested weekly rotation. On C every round of every run kept the staffing
  ratio and the 38 h 15 min weeks; what remained was the opening rotation (R10).
* **The older model does not benefit.** The same MAS with gpt-4o and gpt-4o-mini ran just as
  smoothly (no Docker failures) but produced no roster on C or D: placeholder workbooks, copies of
  the history, or "no feasible solution found". It is not much cheaper per run (€0.23 against
  €0.29): gpt-4o's input price is about 2.5 times Terra's.
* **Prompted directly, the strong model is close, and the skill decides C.** Terra alone met all
  rules on C in 1 of 5 runs, breaking mostly the staffing ratio; with the domain skill in 4 of 5.
  On D direct prompting stays behind the MAS (14.1 against 11.5, and 18.0 with the skill, where one
  run again left the assistant out to protect the 19:08 hour target). The direct runs cost about
  a tenth of a MAS run.
* **Underspecified input separates the approaches.** A and B give only the old rotation (B also
  children's attendance), no staff profiles and no number of weeks. Prompted directly, Terra
  always produced four weeks with the current staff. Inside the MAS it never did: its programs
  planned one or three weeks, or wrote no table and asked for the missing data (staff profiles,
  closures); the weaker models scheduled Staff08, who has left.
* **The MAS's final choice is not always its best round.** In one C run the final report agent
  picked round 1 over two rounds that met all rules, citing a 48:15 week for one employee in
  round 2; that employee's shifts add up to 38:15, as the program printed. Every round is
  therefore scored, not only the pick (`results/rerun_mas_rounds.csv`).
* **Cost and tokens.** The whole rerun (160 runs) used about €13; a MAS 2025 v2 run with Terra about
  100k input and 45k output tokens on D. Prices: Azure EU Data Zone Standard, Terra €0.99 /
  €0.054 / €4.94 per million input / cached input / output tokens; gpt-4o and gpt-4o-mini
  converted from USD third-party list prices at 0.8977 EUR/USD. Everything run on the Azure
  endpoint, including the earlier Azure experiments, smoke tests and the tests of the pull
  requests, cost €32.42 in all.

Our interpretation: the MAS's workflow can deliver good rosters, but only with a strong model and
after fixing how the program is built and run, how errors reach the fixer, and how hard and soft
rules are stated. With the model of its own time it did not deliver. A strong model prompted
directly gets close at a fraction of the cost and time; the MAS's generated code is more reliable
on the staffing arithmetic of the realistic case (D). These conclusions rest on synthetic data
and rule checkers, not on validation by the daycare.

### How we got here

The final comparison was preceded by two days of earlier experiments (16–17 Nov 2026), on mixed
providers and models, the pilot's original task text, and MAS 2024 and MAS 2025 v1. In short:

* **The MAS as delivered failed.** Neither MAS 2024 nor MAS 2025 v1 produced a usable roster with
  gpt-4o, yet they rated many rounds "goal achieved".
* **A newer model did not help inside the MAS**, although it solved the task when prompted
  directly.
* **For the strong model, the obstacle was the workflow.** A fix-loop analysis of MAS 2025 v1 with
  `gpt-6.1-terra` traced most failures to Docker files that no agent could repair and to errors
  that never reached the code fixer.
* **These findings became MAS 2025 v2 and the revised task text.** Both worked in single runs, so
  everything was rerun on one setup.

The details, tables and results files are in [EARLIER_EXPERIMENTS.md](EARLIER_EXPERIMENTS.md).

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
mas_harness/                       headless runner for the MAS (the MAS's code is not changed by it),
                                   the patches to the MAS and their notes (MAS2025_PR_NOTES.md)
direct_llm/                        direct frontier-LLM experiment (no tools, simple revision loop)
experiments/rerun_2026-11/         plan, run list and analysis of the final rerun
EARLIER_EXPERIMENTS.md             the experiments before the rerun, and how they led to it
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
* **D: a synthetic daycare for the pilot task.** The pilot's task description, rotation slots and rotation history, combined with a synthetic daycare that matches the daycare's real number of children per age group: 15 under 3, 25 over 3 and 5 in a mixed group. Staff profiles (groups, roles, weekly hours, vacations) are invented to fit the rotation table. The history keeps the rotation table as it was: `Staff08` appears in weeks 5–11 (in the slot later held by `Assistant`) but has no staff profile, so programs that cross-check names flag it. D is the most realistic test of the pilot task, but it is not fully solvable. With fixed slots, home groups and the holiday weeks, every roster found leaves some understaffing (the best found has 10.9 missing staff-hours per week), so D is scored by how small the gaps are rather than pass or fail. `prompt_revised.txt` (also in A and B) is our revision of the pilot text, not the pilot's: the same facts, but the constraints are split into primary requirements (ratios, own group, availability, one shift a day, hours close to target) and secondary goals (continuity, rotation, fairness, simplicity), and it says what to do when the ratios cannot be met (keep the shortfall small and list it). The pilot text lists the ratios under "Hard Constraints" but also asks to "minimize violations of staffing ratios". `score_daily_detail.py` scores a D roster given per day instead of per week, with the same rules and numbers as the weekly checker.

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

1. Clone this repository and the MAS version to evaluate, at the evaluated commit (see [The MAS versions](#the-mas-versions)). The harness expects the MAS in `./mas2024`, or wherever `MAS_DIR` points.

   ```bash
   git clone https://github.com/GPT-Laboratory/aiming_for_productivity_staff_scheduling_pilot_evaluation.git
   cd aiming_for_productivity_staff_scheduling_pilot_evaluation
   ```

   **MAS 2024** ([ucs-llm-code-docker-optimizer](https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer)), the harness default:

   ```bash
   git clone https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer.git mas2024
   git -C mas2024 checkout 7656ad92289f27e37e51a38657ed18f042dca650
   ```

   For the patched variant of MAS 2024, apply the evaluation patch on top of that commit:

   ```bash
   git -C mas2024 apply ../mas_harness/mas_eval_patches.diff
   ```

   The patch fixes bit rot and gaps against the intended use, without changing prompts, models or agent logic:
   * it calls `docker compose`, because Compose V1 is no longer available;
   * it adds `numpy` when the requirements list PuLP. The reason given at the time, "PuLP 3.3 needs numpy", was wrong: the `No module named 'numpy'` errors came from PuLP 4 (September 2026, Python ≥ 3.12), which imports numpy without depending on it. With numpy added, PuLP 4 programs then failed on its changed API (`lowBound`, `PULP_CBC_CMD`). The upstream pull request caps an unpinned PuLP below 4 instead. None of the rerun's MAS programs used PuLP, so its results are not affected;
   * it gives the code fixer the tail of the build and run log, because build and start-up errors used to reach it as a single line;
   * it regenerates the Docker files after a fix, because the fixer could not repair a broken Dockerfile or compose file;
   * it asks the user what to change when they request a new plan, and lets them give optional feedback for the next round;
   * it sets the LangGraph step limit explicitly to 50 instead of the implicit default of 25.

   The earlier MAS 2024 runs with gpt-4o / gpt-4o-mini and with `gpt-6.1-terra-pro` were made without this patch.

   **MAS 2025** ([heuristic-multi-agent-system](https://github.com/JoniHonkanen/heuristic-multi-agent-system), Feb–May 2025), the optimization tool derived from MAS 2024 and most likely the pilot's version. It adds problem classification, a heuristic agent and problem-class instructions, including instructions for shift scheduling. Clone it and point `MAS_DIR` at it:

   ```bash
   git clone https://github.com/JoniHonkanen/heuristic-multi-agent-system.git mas2025
   git -C mas2025 checkout e8c2077
   git -C mas2025 apply ../mas_harness/mas2025_eval_patches.diff   # Compose V2, PuLP/numpy (see above), fix-counter reset
   export MAS_DIR=$PWD/mas2025      # MAS 2025 v1
   ```

   Three things differ when it runs:
   * `run.sh` detects it and installs `mas_harness/requirements-mas2025.txt`, resolved as of its commit date. Its own `requirements.txt` is a pip freeze that does not resolve.
   * The harness supports its Chainlit 2 button format.
   * The harness gives its unused Claude client a placeholder key, because the client refuses to start without one.

   The patch also fixes one bug in the MAS's own control flow. After 4 failed fixes, MAS 2025 regenerates the code, but it resets the fix counter only in its new-round agent. The next execution therefore routes to a node that is missing from the routing table and the run crashes with `KeyError: 'heuristic'` (or `'code_generator'`); this happened in 2 of the first 12 runs, both on dataset C. The patch resets the counter when code is regenerated, as the new-round agent already does. Runs that keep failing then stop at the MAS's own step limit of 50. Runs made with the patch are named `*_mas2025fix_*`.

   **MAS 2025 v2 (design variant).** The runs with `gpt-6.1-terra` showed gaps in the MAS's design rather than bit rot (see [EARLIER_EXPERIMENTS.md](EARLIER_EXPERIMENTS.md)). `mas_harness/mas2025v2_design_patches.diff`, applied on top of the evaluation patch in a separate checkout `mas2025v2/` (`MAS_DIR=$PWD/mas2025v2`), makes five changes: (1) the agents that write programs, the Docker files agent and the code fixer are told how the program is built and run (inputs side by side in the build context, `docker compose build` and `up` with no variables, arguments or interaction, unattended: finish with stated assumptions); (2) the run agent keeps the tail of the unfiltered log, and the code fixer can ask for it (`need_full_logs`), getting a second call in the same step; (3) the code fixer decides where the fault is: `code`, `docker` (the Docker files agent corrects its files with the fixer's note) or `give_up` (the round ends as a failed round, and the next program is written knowing why); (4) the code fixer sees its earlier attempts on the same program; (5) the shift-scheduling guidance (`SHIFT_SCHEDULING` in `prompts/instuctions.py`) separates hard rules from soft rules in priority order and says never to return nothing. Runs with v2 are named `*_mas2025v2_*` and reported separately from v1. To build the v2 checkout:

   ```bash
   git clone https://github.com/JoniHonkanen/heuristic-multi-agent-system.git mas2025v2
   git -C mas2025v2 checkout e8c2077
   git -C mas2025v2 apply ../mas_harness/mas2025_eval_patches.diff ../mas_harness/mas2025v2_design_patches.diff
   export MAS_DIR=$PWD/mas2025v2
   ```

   `mas_harness/MAS2025_PR_NOTES.md` lists every change to the MAS with its reason. The changes are submitted as pull requests to heuristic-multi-agent-system ([#1](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/1), [#2](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/2), [#3](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/3)); there, the PuLP fix caps an unpinned PuLP below 4 instead of adding numpy, and the model settings that the harness sets from outside (output cap, temperature, token usage) are read from `.env`.

2. Configure the API access:

   ```bash
   cp .env.example .env
   # edit .env: set OPENAI_API_KEY; keep OPENAI_API_BASE for OpenRouter, or delete it for OpenAI
   ```

   With OpenAI directly, also change the model ids, because OpenAI model ids have no `openai/` prefix.

   To use a second provider (for example Azure for one model), put its settings in `.env.<name>` and prefix a command with `UV_ENV_FILE=.env.<name>`. This works for the MAS harness and the direct-LLM script alike. Values in that file take precedence over `.env`, and each run records its endpoint and models. The direct-LLM script and the simulated manager send the output cap as `max_completion_tokens`, which reasoning models on OpenAI and Azure require, and as `max_tokens` on OpenRouter.

   The rerun used Azure (`UV_ENV_FILE=.env.azure`) for every model: `gpt-6.1-terra`, gpt-4o-2024-11-20 and gpt-4o-mini-2024-07-18. The earlier experiments also used OpenRouter; see [EARLIER_EXPERIMENTS.md](EARLIER_EXPERIMENTS.md).

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
mas_harness/run.sh --prompt-file datasets/D_synthetic/prompt_revised.txt \
    --file datasets/D_synthetic/synthetic_daycare.xlsx --optimization-rounds 2 --name D_mas_r01

# a batch: <dataset dir> <name> <runs> <optimization rounds> [timeout s, default 1500] [prompt file]
mas_harness/run_batch.sh datasets/D_synthetic D_mas 5 2 1800 prompt_revised.txt

# as in the rerun's E4: MAS 2025 v2 with gpt-6.1-terra as both models, on Azure
UV_ENV_FILE=.env.azure MAS_DIR=$PWD/mas2025v2 \
HEADLESS_LLM_MODEL=gpt-6.1-terra HEADLESS_LLM_CODE_MODEL=gpt-6.1-terra HEADLESS_LLM_DEFAULT_TEMPERATURE=1 \
    mas_harness/run_batch.sh datasets/D_synthetic rr_D_v2_terra_rev 5 2 1800 prompt_revised.txt
```

`experiments/rerun_2026-11/run.sh E3 E4 E7 …` runs the rerun's experiments as listed in its `PLAN.md`. In the rerun a MAS 2025 v2 run took 2.4 min on average with gpt-4o and 6.1 min with `gpt-6.1-terra`; the timeout was 30 minutes per run.

How the harness works:
* **No user interface.** It replaces the MAS's Chainlit UI with a stand-in module and calls the MAS's own `main()` handler, so file ingestion, prompt formatting and the LangGraph workflow are the original code.
* **Fixed human decisions.** The plan is always accepted, and `--optimization-rounds` further rounds are requested before the final report.
* **Full recording.** Every agent step's input, output and state, the generated code, the Docker files and a run summary go to `runs/<timestamp>_<name>/`. Files the executed program writes (for example an Excel roster) are copied to the step's `outputs/` folder. Runs made before this was added lost those files; `mas_harness/reexecute_rounds.py <run>` re-executes the program behind each analysed round to recover them. Most programs are randomised, so a re-execution is not guaranteed to reproduce the original output.
* **Token usage.** Every LLM call is logged as an `llm_usage` event (step, model, input, cached input, output and reasoning tokens) and summed per model in `summary.json` (`token_usage`). Runs before 17 Nov 2026, 15:00 have no token counts.
* **Fix-loop analysis.** `mas_harness/fix_loop_analysis.py <run> ...` goes through the recorded run–fix loops: for each failed program execution it shows what the code fixer was given, triages the cause from the saved Dockerfile and compose.yaml (variables the MAS never sets, input files not reachable in the container) and says whether the cause lies in a file the fixer can edit. It reruns nothing unless `--replay` is given, which rebuilds the failed steps to recover errors the MAS did not pass on.
* **Compose wrapper.** `mas_harness/bin/docker-compose` forwards the MAS's `docker-compose` calls to Compose V2.
* **Model override.** `HEADLESS_LLM_MODEL` and `HEADLESS_LLM_CODE_MODEL` replace the MAS's two models (gpt-4o-mini and gpt-4o) without changing its code; this is how the Terra runs were made. `OPENAI_API_BASE` selects the provider.
* **Temperature.** Reasoning models such as gpt-6.1-terra accept only the default temperature. The 2025 MAS sets `temperature=0` on its code model, and the 2024 MAS's LangChain version sends 0.7 by default; both are rejected with HTTP 400 on OpenAI and Azure. `HEADLESS_LLM_DEFAULT_TEMPERATURE=1` leaves the temperature out of the requests of both models. Each run records the temperatures in `summary.json`. (OpenRouter ignored the setting, so the earlier Terra runs there needed no override.)
* **Structured replies.** The agents ask for structured (JSON) replies through LangChain. The 2024 MAS's LangChain uses function calling for that, which gpt-6.1-terra on Azure's chat-completions endpoint refuses while reasoning is on (HTTP 400; the agent then fails with a `KeyError`). `HEADLESS_STRUCTURED_OUTPUT_METHOD=json_schema` makes it use a JSON-schema response format instead, which is what the 2025 MAS's newer LangChain does by default. The schemas and prompts are unchanged.
* **Root-owned leftovers.** Docker Compose creates missing bind-mount folders as root, and a generated program may write into them. The harness clears the MAS's `generated/` folder before each run and removes such leftovers through a container.
* **Output cap.** The 2025 MAS hard-codes `max_tokens=4096` for its code model (the original gpt-4o limit). A whole program comes back in one structured reply, so the harness raises the cap to 16384 (current gpt-4o's limit), or to `HEADLESS_LLM_CODE_MAX_TOKENS`. The 2024 MAS sets no cap and is left alone unless the variable is set. Replies cut off at the cap are logged as `llm_truncated` events.
* **Step limits.** MAS 2025 sets 50 itself. MAS 2024 relies on LangGraph's implicit default of 25; the MAS 2024 runs before the evaluation patch used that, and the patch sets 50. `--recursion-limit` changes it.
* **Side effect.** The MAS runs `docker image prune -f` after every execution.

`mas_harness/llm_extract.py <run>...` gives an LLM (by default `gpt-6.1-terra`) what one round's program printed and every file it wrote (workbooks as CSV text per sheet) and asks for the roster in one fixed JSON schema: a weekly rotation (A, B, D) or a list of daily shifts (C), plus what the program reported about itself. The model is told to copy only, not to compute, add up or guess, and to leave anything not shown empty. The JSON is converted to the checkers' input and scored, so every run gets a machine-checkable result in the same way, whatever form its program chose. `--all-rounds` processes every analysed round, not only the one the final report picked.

`mas_harness/make_packets.py runs/<run>...` writes a readable evaluator packet per run, showing each round's code, trimmed output and the MAS's own verdict.

## Running the direct-LLM experiment

```bash
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py D 5
uv run --no-project --python 3.11 --with-requirements requirements.txt direct_llm/direct_llm.py C 3
```

* **Setup.** The model receives the task description and the data serialised the same way the MAS serialises Excel files. It is told it has no tools and must not write a program. Each reply is capped at 16384 output tokens, reasoning included (the same cap as the MAS code model in the harness), and the system prompt says so, so that the model budgets its reasoning. Earlier direct runs used a cap of 30000 and did not mention it. It is also given a fixed answer format; for D this includes the convention for reading the table.
* **Revision loop.** After each answer, a structural check looks only at format: the table parses, names are known, nobody is in two shifts at once, all weeks are present. Any problems are sent back, with at most 4 answers. The rule checkers run only afterwards, and their results are never shown to the model.
* **Domain skill (optional).** `--skill direct_llm/skills/finnish-daycare-scheduling/SKILL.md` appends a skill to the system prompt. It is a copy of the simulated manager's `SKILL.md`, rewritten for the system that builds the roster: what the manager cares about, the Finnish staffing and working-time rules, a short method, and how to handle staffing gaps (keep the ratio as the requirement, minimise the gaps and report them). It says nothing about the datasets or the checkers. The gap paragraph settles the ratio ambiguity of the pilot task text, so runs with the skill are not a test of the task text as written.
* **Datasets and task text.** Cases A, B, C and D. A and B use the same weekly answer format as D (weeks 18–21) and are checked for format only (no staff profiles, so no rule checker). `--prompt prompt_revised.txt` uses the revised task text instead of the pilot's original (`prompt.txt`).
* **Configuration.** The model defaults to `DIRECT_LLM_MODEL` from the provider profile; change it with `--model`. The provider comes from `OPENAI_API_BASE`. Token use is logged per answer, with cached and reasoning tokens.

## Results

| File | Contents |
|---|---|
| `results/rerun_summary.csv` | **rerun of 17 Nov 2026**: per experiment and dataset, the main score (mean, range), rosters meeting all rules, steps, minutes, tokens and euros per run |
| `results/rerun_mas_runs.csv` | rerun, one row per MAS run: outcome, steps, executions, the round the final report picked, its score and the best round's score, tokens and cost |
| `results/rerun_mas_rounds.csv` | rerun, one row per analysed MAS round: score, failed rules, the workbook it came from, whether the final report picked it |
| `results/rerun_direct_runs.csv` | rerun, one row per direct run (and the reused direct runs of 17 Nov): score, answers needed, tokens and cost |
| `results/rerun_llm_extract.csv` | rerun, every MAS round's roster as extracted by an LLM into a fixed JSON schema and scored (see below) |
| `results/scoresheet_template.csv` | blank rubric for human evaluators, one row per MAS round, from the earlier experiments. The expert evaluation instead uses two rosters on D (the second-best run of E4 and of E7), shown blind; the selection and the form are in `experiments/rerun_2026-11/PLAN.md` |

**Cross-check by LLM extraction.** For every analysed round of the 40 rerun MAS runs (119 rounds), `mas_harness/llm_extract.py` had `gpt-6.1-terra` copy the roster from what the program printed and wrote into a fixed JSON schema, which was then scored with the same checkers (`results/rerun_llm_extract.csv`; about €1.65, 6 s per round). It agrees with the workbook-based scores in all 119 rounds: the same score in 30 C/D rounds, no roster in 29, and the same presence or absence of a named table in all 60 A/B rounds. The first pass found three faults that were then fixed: the workbook scorer read only the Monday sheet of a roster given per weekday (E4 · D r05, now 10.3 instead of 18.8); the extraction schema had no way to hold such a roster; and the model, not told where the reproduced history ends, refused to extract a table that continued it. Where the programs left the roster empty and gave only "unverified suggestions", the model copied the empty table and said so, as instructed.

The rerun's tables come from `experiments/rerun_2026-11/analyse.py`, which scores every MAS round's workbook and every direct answer with the checkers; prices are set at its top. `datasets/D_synthetic/recount_independent.py <table.csv> --compare` recounts D's missing staff-hours with independent code (written from the workbook and the task text, sharing no code with the checker) and was used to spot-check the scores; it agrees with the checker on the reference, the replayed human rotation and rerun rosters. `experiments/rerun_2026-11/progress.py` shows the progress of a running rerun against the plan.

The results files of the earlier experiments, and how to reproduce them, are listed in [EARLIER_EXPERIMENTS.md](EARLIER_EXPERIMENTS.md#results-files). The raw run logs are not published.

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
* The rerun made 5 runs per cell (the earlier experiments 3–5): enough to show consistent failure or success, not to estimate exact rates.
* Rule R10 ("opening and closing shifts are distributed as evenly as possible") is checked as: each employee's number of openings, and of closings, differs by at most one from every other employee's. Most remaining C failures are R10 under this reading.
* Datasets A and B have no rule checker; for them we report only whether a table of the requested weeks with current staff was produced. The revised task text (`prompt_revised.txt`) is our revision, not the pilot's.
* MAS rosters come in many forms. The rerun scores the workbooks the programs wrote, located by sheet and column names; `mas_harness/llm_extract.py` extracts them independently with an LLM as a cross-check (see Results).

## License

MIT, see [LICENSE](LICENSE).
