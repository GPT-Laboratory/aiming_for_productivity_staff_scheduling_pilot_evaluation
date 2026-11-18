# Changes to the 2025 MAS, for a pull request upstream

Target: <https://github.com/JoniHonkanen/heuristic-multi-agent-system>, based on commit `e8c2077`
("instructions for scheduling problems"). The changes live in two patch files in this folder:

* `mas2025_eval_patches.diff`: bit rot and one control-flow bug (applied to `mas2025/`, the
  version "as delivered" in the evaluation);
* `mas2025v2_design_patches.diff`: design changes, applied on top of the first (`mas2025v2/`).

*Status 18 Nov 2026:* submitted as three PRs:

* [#1 "make it run again"](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/1): items 1–7, with the PuLP fix of item 2 corrected;
* [#3 "fixer workflow"](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/3): items 8–11, built on #1;
* [#2 "shift-scheduling guidance"](https://github.com/JoniHonkanen/heuristic-multi-agent-system/pull/2): item 12.

The same fixes, plus a limit on fix attempts that the 2024 version lacks, are submitted to the
2024 version ([ucs-llm-code-docker-optimizer #1, #2](https://github.com/JoniHonkanen/ucs-llm-code-docker-optimizer/pull/1)) and to its copy
([GPT-Laboratory/ai-code-optimizer #1, #2](https://github.com/GPT-Laboratory/ai-code-optimizer/pull/1)).

They are split below into separate PRs, smallest first. Each item says what was wrong, how it
showed up, what was changed, and which files are touched. Line numbers refer to `e8c2077`.

## PR 1: bit rot (no behaviour change intended)

1. **Docker Compose V2.** `docker-compose` (V1) is no longer shipped with Docker. The run agent
   now calls `docker compose build`, `docker compose up …` and `docker compose down`.
   File: `agents/docker_execution_agent.py`.
2. **PuLP 4.** *Corrected 17 Nov 2026:* the `No module named 'numpy'` errors came from PuLP 4.0
   (September 2026, Python ≥ 3.12), not 3.3: PuLP 4 imports numpy without depending on it, and it
   also removed `PULP_CBC_CMD` and renamed the `LpVariable` bounds that generated programs use.
   PuLP 3.x works without numpy. The eval patch appends `numpy` to `requirements.txt` when `pulp`
   is listed without it, which only moves the failure to the API change. The pull request instead
   caps an unpinned PuLP below 4.
   File: `agents/docker_execution_agent.py`.
3. **`requirements.txt` does not resolve.** It is a pip freeze with conflicts (chainlit 2.4.0
   needs a newer uptrace; langchain-anthropic 0.3.9 needs a newer langchain-core) and two
   merged lines. Our harness uses `requirements-mas2025.txt` (the direct imports only, resolved
   as of the commit date). Suggest replacing the freeze with the direct dependencies.

## PR 2: fix-counter bug (crash)

4. **`KeyError: 'heuristic'` / `'code_generator'` after four failed fixes.** `fixIterations` is
   reset only in `new_loop_agent`. When the fix budget runs out before any program has run,
   `decide_next_step_after_fix` routes to the heuristic or code generator, which write a new
   program but keep the counter at 4; the next execution goes through `decide_next_step`, which
   returns `"heuristic"`/`"code_generator"`, and `start_docker`'s path map has no such keys.
   Seen in 2 of 12 runs with gpt-4o. Fix: reset `state["fixIterations"] = 0` in
   `heuristic_agent` and `code_generator_agent`, as `new_loop_agent` already does.
   Files: `agents/heuristic_agent.py`, `agents/code_generator_agent.py`.

## PR 3: model settings (small, configurable)

Not in the patch files (our harness sets these from outside), but worth making configurable:

5. **Output cap of the code model.** `llm_code` has `max_tokens=4096`. A whole program comes back
   in one structured reply; current models allow 16384, and 4096 can cut a program off.
6. **Temperature for reasoning models.** `temperature=0` on `llm_code` (and LangChain's default
   0.7 elsewhere) is rejected by reasoning models (OpenAI/Azure: "only the default (1) value is
   supported"). Make it configurable, or omit it for such models.
7. **Token usage.** With `stream_usage=True` on the models, streamed calls report token usage,
   so runs can be costed. (Our harness logs it; upstream could show it in the UI.)

## PR 4: design changes (behaviour changes)

Evidence for these comes from running the MAS with a current reasoning model
(`gpt-6.1-terra`) on four daycare rostering tasks; numbers below. All are in
`mas2025v2_design_patches.diff` and marked `[design patch v2]` in the code.

8. **Tell the agents how the program is built and run** (`EXECUTION_CONTRACT` in
   `prompts/prompts.py`). The Docker files agent did not know that the MAS puts the input files
   next to `generated.py` and runs `docker compose build` / `up` with no environment variables,
   arguments or interaction. Generated compose files mounted `./data` and passed
   `/data/<file>.xlsx`, or required `${YEAR}`; 188 of 215 failed executions in 12 runs came
   from this. The section is appended to the prompts of the Docker files agent, the code fixer,
   the heuristic, code-generator and new-loop agents. It also says the program runs unattended
   and must finish with stated assumptions instead of waiting for approvals or extra files
   (programs otherwise stopped to ask for `policy.json`, `holidays.json`, approval flags).
9. **The code fixer can ask for the full logs** (`need_full_logs`, `full_logs_reason` in
   `CodeFix`). The run agent passes on only lines matching `Traceback`, `ERROR:` or
   `exited with code`; programs that report errors themselves (`argparse` prints `error: …`,
   others `Error: …` then exit) left the fixer with only an exit code (148 of 215 failures). The
   run agent now keeps the tail of the unfiltered build+run log (`docker_full_log`); if the fixer
   asks, it is called again in the same step with that log and the Docker files. Nothing is
   added to its prompt unless it asks.
   Files: `agents/docker_execution_agent.py`, `agents/code_fixer_agent.py`, `schemas.py`.
   (Simpler alternative: make the error patterns case-insensitive and include the last N lines.)
10. **The code fixer decides where the fault is** (`route`: `code` | `docker` | `give_up`, plus
    `route_note`). There was no agent that could repair the Dockerfile or `compose.yaml`: the
    fixer edits only the program, so four attempts in a row ran against the same broken Docker
    files (161 such retries in 12 runs).
    * `docker`: the program is left as it is; the Docker files agent is called with its previous
      files, the error and the fixer's note, and corrects them (same fix budget).
    * `give_up`: the program cannot be made to work (wrong approach, the same error keeps
      coming back). The fix attempts stop and the round goes to the output analyzer as a failed
      round with the reason; the next round's program is written knowing it.
    Files: `agents/code_fixer_agent.py`, `agents/docker_environment_agent.py`,
    `agents/code_output_agent.py` (resets the counter after `give_up`, so routing stays valid),
    `main.py` (two new edges from `code_fixer`), `schemas.py`, `prompts/prompts.py`.
11. **The code fixer sees its earlier attempts on the same program** (`fix_history`). Each fix
    call got only the current program and error, so attempts could repeat. The fixer's own
    `original_error` and `fix_description` (already produced, previously discarded) are kept
    and shown as "earlier fix attempts; do not repeat them". Cleared when a new program is written.
12. **Shift-scheduling guidance rewritten** (`SHIFT_SCHEDULING` in `prompts/instuctions.py`).
    The original lists every rule as a hard constraint ("your schedule must satisfy every
    constraint"), makes weekly hours a hard upper limit, and forbids inferring missing values.
    On a realistic instance, where some understaffing is unavoidable, a strong model then
    returns "infeasible" and an empty schedule, or gives people four shifts instead of five to
    stay under the hour limit. The new text separates hard rules (one entry per cell, no
    overlap, availability, closures, past data, legal rest) from soft rules in priority order
    (coverage, contracted hours, grouping, fairness), lets the task move a rule between them,
    says never to return nothing but to relax soft rules from the lowest priority up, allows
    plausible estimates from history (listed in the report), defines weekly-rotation templates,
    asks the program to print a short report within the analyzer's 4000-character window, and
    gives a solver choice by instance size with independent validation.

## Results that motivate PR 4 (gpt-6.1-terra as both models, Azure, 17 Nov 2026)

| Setup | Dataset | Outcome |
|---|---|---|
| as delivered (PRs 1–2 only), 12 runs | A–D | 11 stopped at the 50-step limit; 215 / 225 executions failed; 2 near-usable rosters (C, 10 of 11 rules) |
| + PR 4 items 8–11, original guidance | D | runs of 7–13 min; drafts "infeasible" or ~57 missing staff-hours a week (hour limit kept hard) |
| + PR 4 items 8–12 | C | 6.8 min, 3 executions, 0 failures; rounds 2 and 3 satisfy all 11 rules, round 3 with one continuous shift per person per day |
| + PR 4 items 8–11, task text with primary/secondary constraints | D | 8.7 min; 10.3 missing staff-hours a week (as a daily roster; best known weekly rotation 10.9) |
| + PR 4 items 8–12, task text with primary/secondary constraints | D | 4.7 min, 3 executions, 0 failures; weekly rotation in the template's format, no empty slots, 10.8 missing staff-hours a week (best known 10.9; the model prompted directly 10.9–14.5) |

With gpt-4o / gpt-4o-mini the same changes removed the Docker failures but did not lead to
usable rosters; there the model, not the plumbing, is the limit.

## Not changed, but worth raising upstream

* The output analyzer sees only the last 4000 characters of printed output; rosters written to
  Excel are invisible to it, and it rated such rounds "achieved" without seeing them (9 of 15
  with gpt-4o).
* Free text the user types at the plan and between-round questions is not used; only the button
  choice is.
* The code generator agent does not receive the problem-class guidance (only the heuristic and
  new-loop agents do).
* Docker Compose creates missing bind-mount folders as root; programs then write root-owned files
  into `generated/`, and the next run cannot clear the folder (our harness removes them via a
  container).

## Not for the PR

The evaluation harness (`run_headless.py`, recording, simulated user), the datasets and their
revised task texts (`prompt_revised.txt`), and the analysis tools belong to this repository only.
