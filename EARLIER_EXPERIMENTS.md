# Earlier experiments (16–17 Nov 2026): the road to the final rerun

These experiments came before the final rerun reported in the [README](README.md). They were run
over two days and the setup changed between them:

* **Providers:** OpenRouter, then Azure.
* **Models:** `gpt-6.1-terra-pro`, then `gpt-6.1-terra`.
* **Task text:** the pilot's original task text.
* **Harness:** versions that did not yet keep the programs' output files or count tokens.
* **MAS variants:** MAS 2024 (unpatched and with the evaluation patch) and MAS 2025 v1, as
  defined in [The MAS versions](README.md#the-mas-versions).

They are not directly comparable with the rerun, or with each other. They are kept because they
show why the MAS failed, what was changed in response (MAS 2025 v2, the revised task text) and
why everything was then run again on one setup. Their aggregated results are in
`results/archive/2026-11-17_before_rerun/`; the raw logs are not published.

## How one step led to the next

1. **MAS 2024 with its own models (gpt-4o / gpt-4o-mini) produced no usable roster** on any
   dataset, but rated more than half of its rounds "goal achieved".
2. **A newer model inside MAS 2024 (`gpt-6.1-terra-pro`) did not help.** All runs stopped at the
   step limit, with programs that asked for decisions the workflow cannot pass on.
3. **The same newer model prompted directly solved the task.** It satisfied every rule on C and
   came close to the best known roster on D. So the model was capable, and the MAS's workflow was
   suspect.
4. **MAS 2025 v1, most likely the pilot's version, did no better than MAS 2024** with gpt-4o.
   These runs also exposed a crash in its fix counter, which v1 fixes.
5. **MAS 2025 v1 with `gpt-6.1-terra` on Azure was blocked by the Docker plumbing.** The
   fix-loop analysis traced most failures to Docker files that no agent could repair, and to
   errors that never reached the code fixer.
6. **MAS 2024 with the evaluation patch** (log tail to the fixer, Docker files regenerated)
   removed some of these failures but still produced no roster.
7. **The design changes of MAS 2025 v2 were built from these findings, and tried in single
   runs** (below).
   - Fixing the plumbing alone left the original shift-scheduling guidance in the way: rosters
     came back "infeasible", or kept the hour limit hard at the cost of coverage.
   - With the guidance rewritten, C met all 11 rules.
   - With the revised task text as well, D reached 10.8 missing staff-hours a week.
8. **Everything was then rerun on one setup** (Azure, 5 runs per cell, revised task text, token
   counts), with MAS 2025 v2 as the MAS. MAS 2024 and MAS 2025 v1 were dropped from the
   comparison, because their failures were already documented here. See
   `experiments/rerun_2026-11/PLAN.md`.

## Results

| Experiment | Runs | Analysed rounds | Rounds the system rated "goal achieved" | Usable schedules |
|---|---|---|---|---|
| MAS 2024 (unpatched), gpt-4o / gpt-4o-mini, datasets A–D | 16 | 43 | 25 | 0 |
| MAS 2024 (unpatched) with `openai/gpt-6.1-terra-pro` as both models, dataset D | 3 | 3 | 0 | 0 |
| MAS 2025 v1, gpt-4o / gpt-4o-mini, datasets A–D (12 runs before the counter reset was added, plus 2 C reruns with it) | 12 + 2 | 28 + 1 | 11 + 1 | 0 |
| Direct prompt, `openai/gpt-6.1-terra-pro`, dataset D | 5 | – | – | 5 valid tables |
| Direct prompt, `openai/gpt-6.1-terra-pro`, dataset C | 3 | – | – | 3 satisfy all 11 rules |
| Direct prompt, current prompt, without / with the domain skill, dataset D | 5 / 5 | – | – | 5 / 5 valid tables; mean 11.5 / 34.5 missing staff-hours a week |
| Direct prompt, current prompt, without / with the domain skill, dataset C | 3 / 3 | – | – | 3 / 3 satisfy all 11 rules |
| MAS 2025 v1, `gpt-6.1-terra` (Azure) as both models, datasets A–D | 12 | 10 | 1 | 0 (2 near-usable on C: 10 of 11 rules) |
| MAS 2024 + evaluation patch, `gpt-6.1-terra` (Azure), dataset D | 3 | 7 | 0 | 0 |
| Direct prompt, `gpt-6.1-terra` (Azure): without the skill / with the skill / with the simulated manager, dataset D | 5 / 5 / 3 | – | – | all valid; mean 13.2 / 34.0 / 35.0 missing staff-hours a week |
| Direct prompt, `gpt-6.1-terra` (Azure): without the skill / with the skill / with the simulated manager, dataset C | 3 / 3 / 3 | – | – | 2 / 2 / 2 satisfy all 11 rules (each miss: R10 only) |

Single runs of MAS 2025 v2 with `gpt-6.1-terra` (Azure, 17 Nov), before the rerun:

| Design changes | Task text | Dataset | Outcome |
|---|---|---|---|
| 1–4 (plumbing), original guidance | original | D | 7–13 min; drafts "infeasible", or about 57 missing staff-hours a week with the hour limit kept hard |
| 1–5 (guidance rewritten) | C's own | C | 6.8 min, 3 executions, 0 failures; rounds 2 and 3 satisfy all 11 rules |
| 1–4, original guidance | revised | D | 8.7 min; 10.3 missing staff-hours a week, but as a daily roster instead of the requested weekly rotation |
| 1–5 | revised | D | 4.7 min, 3 executions, 0 failures; weekly rotation in the template's format, 10.8 missing staff-hours a week |

The design changes are numbered as in [Setup](README.md#setup).

## Findings at the time

* **MAS 2024 produced no usable roster.**
  - The typical failures were:
    - infeasible models caused by the generated code's own bugs;
    - schedules that are structurally impossible;
    - output at the wrong decision level;
    - the input history reprinted instead of new weeks.
  - 55 of 98 code executions crashed, and 3 of 16 runs stopped at LangGraph's 25-step limit.
* **The MAS's self-assessment was unreliable.** It declared success in 25 of 43 rounds, none of
  which was usable.
* **MAS 2025 v1, most likely the pilot's version, did no better.**
  - **Approach.** It has shift-scheduling instructions written for this kind of task. It
    classified every run as shift scheduling and chose a heuristic.
  - **What its 28 analysed rounds produced:**
    - 12 reprinted the input history without new weeks;
    - 11 were structurally impossible, for example the same two people in every shift, or one
      name per row;
    - 3 were at the wrong decision level (groups instead of names);
    - 1 broke the critical rules badly;
    - 1 produced nothing.
  - **Dataset C.** 68–79% of group time was understaffed, and nobody worked the contracted
    38 h 15 min.
  - **Executions.** 54 of 82 code executions failed.
  - **Self-assessment.** It rated 11 rounds as achieved. In 15 rounds the program wrote the
    roster to an Excel file and printed only a confirmation such as "saved to …xlsx". The output
    analyser sees only the printed output, so it never saw these rosters, yet it rated 9 of them
    as achieved.
  - **The counter bug.** Two runs crashed on a routing bug in the MAS (the fix-counter reset in
    v1). With the fix:
    - one rerun stopped at the step limit;
    - the other produced one round (46% of group time understaffed, rated achieved), then hit
      the 25-minute timeout while a generated heuristic ran.
* **A newer model did not help inside the MAS** (`gpt-6.1-terra-pro` via OpenRouter, MAS 2024
  before the evaluation patch). It wrote 390–510-line programs that recognised missing policy
  decisions, but the fixed workflow gave it no way to ask about them or to fix its Docker
  environment. All three runs stopped at the step limit.
* **Inside MAS 2025 v1, `gpt-6.1-terra` was blocked by the Docker plumbing, not by the task.**
  - **Scale.** 11 of 12 runs stopped at the 50-step limit, and 215 of 225 program executions
    failed.
  - **Docker files or folder layout.** `mas_harness/fix_loop_analysis.py` traces 188 of the
    failures to these:
    - in 147, the compose file mounted `./data` and passed `/data/<file>.xlsx`, while the MAS
      puts the inputs in the project folder;
    - in 41, `compose.yaml` required a variable (`${YEAR}`, `${WEEKS}`) that the MAS never sets.
  - **No agent could repair them.** The code fixer rewrites only the program. It is never shown
    the Dockerfile or `compose.yaml` and cannot change them, and no other agent can either. So
    161 retries ran with unchanged Docker files, four fix attempts at a time, until a new program
    brought new Docker files.
  - **Errors that never reached the fixer.** In 148 failures the fixer was shown only an exit
    code. The MAS passes on only lines matching `Traceback`, `ERROR:` or `exited with code`, and
    the model's programs reported their own errors as `error: …` and exited. Where an error in
    the program itself did reach the fixer, it was fixed within one or two attempts.
  - **Rosters.** Within these limits, the model produced two near-usable rosters on dataset C,
    one of them rated achieved. Both had 0 minutes understaffed, everyone at 38 h 15 min and home
    groups kept; only the opening rotation (R10) was missed.
  - **Self-assessment.** It was accurate: it rated 1 of 10 rounds achieved, against 11 of 28 for
    gpt-4o.
  - **The other rounds.** Most ended with a program that stopped to ask for policy decisions or
    approval flags, or printed diagnostics, which the fixed workflow has no way to answer.
* **With the 2024 evaluation patch the model saw its errors but still produced no roster on D.**
  - **What the patch fixed.** It passes the last log lines to the fixer and regenerates the
    Docker files after each fix. The fixer was never left with only an exit code, and no retry
    ran with unchanged Docker files.
  - **What still failed.** 2 of 3 runs completed, but 26 of 33 executions failed. 22 of these
    failed on the input path layout, because the Docker files agent is not told where the MAS
    puts the inputs.
  - **The programs.** Every program stopped for policy decisions, a self-test or diagnostics.
* **The same newer model prompted directly solved the task.**
  * On dataset C, all 3 runs satisfied every rule on the first answer.
  * On dataset D, all 5 runs produced valid tables with 10.9–14.5 missing staff-hours a week
    (mean 12.8). For comparison:
    * the best known schedule has 10.9;
    * the company's own rotation replayed has 17.4;
    * random rotations about 20.7.
  * The weak point was rotation: the same person stayed in the same shift in consecutive weeks
    4–8 times per run.
  * Repeated with the current prompt, with the 16384-token cap stated in it:
    * C: 3 of 3 satisfied every rule again.
    * D: 5 of 5 valid, with 10.9–12.8 missing staff-hours a week (mean 11.5) and 6–10
      same-shift repeats.
    * gpt-4o on the same prompt: D 16.0–39.6, and C 0 of 3 meeting all rules.
* **The domain skill made D worse.**
  - **C.** With `--skill`, the newer model still satisfied every rule (3 of 3).
  - **D.** It left the part-time assistant unscheduled in every week of all 5 runs. Three full
    shifts would exceed the assistant's 19:08 weekly target, and the skill says part-time staff
    work only their contracted hours. Missing staff-hours rose to 34.1–35.6 a week (mean 34.5),
    three times the runs without the skill.
  - **Priorities.** The model explained the omission and listed the resulting gaps, as the skill
    asks. But it put the hour target before the ratio, against the skill's own priority order.
  - **gpt-4o.** The skill made no clear difference (D 19.7–39.7, C 0 of 3).
* **A simulated manager did not improve the direct answers.** The manager reviewed each answer,
  with the persona of `mas_harness/sim_user/SKILL.md`.
  - **C:** accepted in 2 of 3 trials. In the third, the manager gave up because the roster
    stayed a long CSV list with staff IDs, although it met every rule.
  - **D:** the manager accepted neither completed trial (13.1 and 13.3 missing staff-hours a
    week, about the same as without the manager). A third trial was stopped and is not counted.
* **The non-pro `gpt-6.1-terra` (Azure) prompted directly was close behind.**
  - **Alone:** D 5 of 5 valid, 12.0–14.4 missing staff-hours a week (mean 13.2). C: 2 of 3
    satisfied every rule, and the third missed only R10. About 30 s per answer.
  - **With the skill:** it again left the assistant unscheduled on D (mean 34.0).
  - **With the simulated manager:**
    - D got worse, for the same reason: the manager kept asking it to respect the weekly hour
      targets, and it dropped the assistant (mean 35.0, no roster accepted);
    - on C, the manager accepted 1 of 3, and in one trial kept asking to fix a gap in the
      pre-school group that the checker does not find.
* **Cost was not the limiting factor.**
  - **Per run:** a MAS run with gpt-4o cost $0.04–0.18, a MAS run with the newer model about
    $1.10, and a direct-prompt run about $0.05.
  - **Azure:** at the prices for `gpt-6.1-terra` on 17 Nov 2026 (€1.08 per million input
    tokens, €0.06 cached input, €5.39 output), the 22 direct runs used 0.44 M input and 0.20 M
    output tokens, about €0.07 a run.
  - **Not recorded:** the harness did not yet count tokens for the MAS runs on Azure.

At that point, our interpretation was that the fixed generate–run–describe workflow was the main
bottleneck, more than model capability. Nothing in the loop checked the result against the rules,
and information was lost between agents. The rerun shows that fixing those gaps lets a strong
model succeed inside the MAS.

## Notes on the setup of these runs

* **Models.**
  - The Terra runs on OpenRouter used `openai/gpt-6.1-terra-pro`; from 17 Nov the runs used
    `gpt-6.1-terra` (not the pro variant) on Azure.
  - The gpt-4o and gpt-4o-mini results here come from OpenRouter's `openai/gpt-4o` and
    `openai/gpt-4o-mini`, whose snapshots the logs do not record. Azure, used in the rerun,
    serves gpt-4o-2024-11-20 and gpt-4o-mini-2024-07-18.
* **Task text and limits.**
  - All MAS runs used the pilot's original task text (`prompt.txt`).
  - The MAS 2024 runs before the evaluation patch had LangGraph's implicit 25-step limit.
  - The harness timeout was 25 minutes per run.
* **Earlier direct runs.** The first direct runs capped each answer at 30000 tokens and did not
  mention the cap in the prompt. Later direct runs used 16384, stated in the prompt.
* **Recovered rosters.** The MAS 2025 v1 runs with gpt-4o were made before the harness kept the
  files the programs write, so their rosters were recovered by re-executing each round's saved
  program on the same input (`mas_harness/reexecute_rounds.py`).
  - **Reproduced exactly:** 21 of the 29 re-executions (the 28 rounds plus one from the C reruns with the counter reset)
    reproduced the original printed output, or the last 4000 characters of it that the MAS kept.
  - **Different:** the other 8 differ because the heuristics are randomised; their output has
    the same form.
  - **Scoring on C:** programs that printed staff presence per time slot were scored with
    `datasets/C_reconstructed/score_presence_output.py`, which places the floating employee where
    it helps most.
* **Classification.** The round classification is the third evaluator's (an AI-assisted
  evaluation harness). `results/scoresheet_template.csv` is the rubric for human evaluators of
  the same rounds.

## Results files

| File | Contents |
|---|---|
| `results/archive/2026-11-17_before_rerun/` | the results files as they were before the rerun |
| `results/experiments_summary.csv` | per experiment: runs, completed, stopped at step limit, code executions and failures, analysed rounds, rounds self-rated as achieved, usable schedules |
| `results/mas_round_classification.csv` | every analysed MAS 2024 round classified by failure type, with the MAS's own verdict and a short note |
| `results/mas2025_round_classification.csv` | the same for MAS 2025 v1 with gpt-4o, plus how faithfully each round's program re-executed |
| `results/mas_terra_round_classification.csv` | every analysed round of the MAS runs with `gpt-6.1-terra` on Azure (MAS 2025 v1, MAS 2024 + evaluation patch) |
| `results/direct_llm_runs.csv` | direct-LLM runs with checker scores. Run names give the variant: `direct` (first runs, 30000-token cap), `noskill` and `skill` (current prompt, without and with `--skill`), `gpt-4o_*` (gpt-4o on the same prompt), `sim` (reviewed by the simulated manager) |
| `results/cost_by_experiment.csv` | API calls, tokens and cost per experiment, from the OpenRouter activity export of 16 Nov 2026, split by timestamp; the export ends before the last 4 direct runs |

To reproduce these tables from your own runs:

```bash
python3 analysis/aggregate_runs.py runs results/experiments_summary.csv
python3 analysis/cost_by_experiment.py openrouter_activity.csv --runs runs --utc-offset 2
```

The commands for these runs are those of the README, with the MAS variant chosen by `MAS_DIR`
and, for the newer model, both models overridden. For example:

```bash
HEADLESS_LLM_MODEL=openai/gpt-6.1-terra-pro HEADLESS_LLM_CODE_MODEL=openai/gpt-6.1-terra-pro \
    mas_harness/run_batch.sh datasets/D_synthetic D_mas_newmodel 3 2
```
