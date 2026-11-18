# Which measures can be compared with which

Notes for reading the rerun results and the charts made from them (18 Nov 2026).

## The two scored cases are two different daycares

C and D are not two views of one daycare. They do not share children, staff, groups, shifts or
rules.

| | **C: fully specified case** | **D: realistic case** |
|---|---|---|
| Origin | a daycare reconstructed from the example in the MAS thesis (§6.2.4) | a synthetic daycare built to match the pilot daycare's description |
| Children | 50, in three groups | 45, in three different groups (with different age mixes) |
| Staff | 13, all full-time, one floater | 11, two part-time, with vacations |
| Roster form | free shifts: each employee's start and end time per day | the daycare's 11 fixed shift slots, as a weekly rotation |
| Period | one week | four weeks (18–21), continuing the history |
| Rules | 11 explicit rules; provably solvable | ratios, own group, availability, hours; not fully solvable |
| Score | which rules are met (7 checks: the five ratio rules count as one) | missing staff-hours per week |
| Task text | its own prompt | the revised task text (`prompt_revised.txt`) |

A setup's result on C and its result on D are two separate observations of the same method, not
two measures of one roster. A setup that does well on both is consistent evidence. But C's
numbers cannot be put on D's scale or the other way round. The two numbers also cannot be
combined, for example as missing hours per broken rule.

**Charts.** The infographic now takes both of its measures from D: the bar is the mean missing
staff-hours, and the dots count the hard-rule violations in the same five rosters. C's results
appear only as text.

## What can be compared within D (missing staff-hours per week)

Comparable across every rerun setup:

* **Same everything else:** the same synthetic daycare, task text (revised), checker and weeks
  18–21, and five runs each.
* **What is scored for each setup:**
  * for the agentic pipeline, the roster its final report picked (`rerun_mas_runs.csv`); the
    best round is reported separately;
  * for direct prompting, the last answer.
* **One E4 roster (r05)** came as one sheet per weekday, not as a weekly rotation. It was scored
  with `score_daily_detail.py`, which applies the same rules and numbers per day. It is
  comparable in missing staff-hours, but it is not in the requested format.

**Hard-rule violations on D** (`hard_violations_total` in `synthetic_daycare.score`; the
`violations` column of the rerun results). These are the hard rules other than the ratio, which
is scored as missing staff-hours:

* **What is counted:** a shift left empty (blank or "loma"), a person in two slots, a name not on
  the staff, a person on leave all week, and an available person left out.
* **One mistake, one count.** A blank or a double booking also leaves someone out, so each week
  counts the larger of the slot problems and the people left out.
* **Rules this format cannot break:** own group, part-time days, partial leave and rest periods.
  The required share of qualified staff holds whenever nobody is left out.
* **Fixed 18 Nov 2026:** the checker did not count "loma" written into a slot as an empty shift.
  That changed the `empty` counts of 10 weak-model rosters. No missing-staff-hours score changed.
* **Assumption:** the assistant counts toward the Lark group's ratio. If the assistant were
  child-specific, the law would not count them, and every roster would miss more staff-hours.
* **Results (five rosters each):**
  * agentic pipeline with Terra 0, direct Terra 0, best known and random rotations 0;
  * direct gpt-4o 2;
  * direct gpt-4o-mini 29;
  * direct Terra with the skill 4, all in the one run that left the assistant out.

The reference points need care:

* **Best known (10.9).** A heuristic local search (`reference()` in `synthetic_daycare.py`), so
  it is not a proven optimum. Rosters below it (10.3, 10.8) are possible and real.
* **Random (20.7).** The mean of 30 random permutations of the 11 names into the 11 slots each
  week. Same form as the answers, random assignment.
* **The daycare's own rotation (17.4): best left out of comparisons.**
  * It replays the daycare's weeks 14–17 as weeks 18–21. It is then scored on D's invented
    children, group assignment, part-time contracts and vacations.
  * So it measures how the real pattern fits a synthetic daycare, not how well the daycare
    staffs its own children.
  * The vacations of weeks 18–21 were invented for D. The real rotation was never planned
    around them.
  * Removed from the infographic for this reason. The README still cites it, as a reference for
    D only.

## What can be compared within C (rules met)

* **Comparable across every rerun setup:** the same case, checker and prompt.
* **Counting:** count the checks failed, out of 7 (the five ratio rules R2–R6 count as one).
  Rosters meeting all 11 rules = rosters failing 0 checks.
* **Which rosters are scored:** as on D, the pipeline's final pick and the direct prompt's last
  answer. The direct Terra row (E7) has two runs from the main rerun plus three made after E12
  (E7c), all on the same setup.
* **Reference: the hand-made schedule** (`reference_schedule.csv`). It meets all 11 rules, by
  construction of the case.
* **Random baseline for C:** not in the repository, computed 18 Nov for the infographic.
  * **How the rosters were built:** 1000 random rosters; each employee one 7 h 39 min shift a
    day in the home group (the floater in a random group), starting at a random time within
    opening hours.
  * **Result:** 3.0 failed checks per roster (2–4), always the ratio and "never alone", nearly
    always the opening rotation. About 15 over five rosters.
  * **Not a mirror of D's baseline:** these rosters are built so they cannot fail the
    opening-hours, weekly-hours or home-group checks. D's random permutations keep the form but
    can break vacations. Both baselines mean "right form, random assignment".

## What cannot be compared with anything above

* **A and B** have no rule checker. They report only whether a four-week table with current staff
  was produced.
* **The earlier experiments** (`EARLIER_EXPERIMENTS.md`) used other providers, model variants,
  the original task text and the MAS as delivered. Their numbers are not comparable with the
  rerun's.
* **Cost and time** are comparable within the rerun (Azure prices, in euros). A pipeline run's
  cost covers all of its agents. They are not comparable with the earlier experiments' dollar
  figures.
