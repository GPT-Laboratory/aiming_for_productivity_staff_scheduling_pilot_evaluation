#!/usr/bin/env python3
"""Progress of the rerun: planned vs. actual, per experiment and in total.

Counts finished runs in runs/ (a MAS run is finished when it has summary.json, a direct run when it
has result.json), reads the experiment start/end times from logs/queue.log, and compares them with
the estimates in PLAN.md. The projected end extrapolates each experiment from its own mean run time.

Usage: experiments/rerun_2026-11/progress.py [--color | --no-color]   (colour by default in a terminal)
"""
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE.parents[1] / "runs"

# id, label, planned runs, planned minutes, run-name pattern (regex on the run folder name)
PLAN = [
    ("E4", "MAS v2 · Terra", 20, 120, r"_rr_[ABCD]_v2_terra_"),
    ("E3", "MAS v2 · 4o", 20, 100, r"_rr_[ABCD]_v2_4o_"),
    ("E7", "Direct · Terra", 17, 20, r"_direct[ABCD]_rr_terra(_rev)?_r\d"),
    ("E8", "Direct · gpt-4o", 20, 10, r"_direct[ABCD]_rr_gpt-4o(_rev)?_r\d"),
    ("E9", "Direct · gpt-4o-mini", 20, 10, r"_direct[ABCD]_rr_gpt-4o-mini(_rev)?_r\d"),
    ("E12", "Direct + skill · 3 models", 60, 30, r"_direct[ABCD]_rr_[a-z0-9.-]+_skill(_rev)?_r\d"),
]


def runs_of(pattern):
    done, running, minutes = 0, 0, []
    for d in sorted(RUNS.glob("*")):
        if not re.search(pattern, d.name):
            continue
        f = d / "summary.json" if (d / "steps").exists() else d / "result.json"
        if f.exists():
            done += 1
            r = json.loads(f.read_text(encoding="utf-8"))
            minutes.append((r.get("duration_s") or 0) / 60)
        else:
            running += 1
    return done, running, minutes


def queue_times():
    t = {}
    log = HERE / "logs" / "queue.log"
    for line in log.read_text().splitlines() if log.exists() else []:
        m = re.match(r"=== (E\d+) (start|done) (\S+ \S+)", line)
        if m:
            t[(m.group(1), m.group(2))] = dt.datetime.strptime(m.group(3), "%Y-%m-%d %H:%M")
    return t


import os
import sys

COLOR = sys.stdout.isatty() and "--no-color" not in sys.argv or "--color" in sys.argv
BLUE, GREEN, YELLOW, GREY, BOLD, RESET = ("\033[34m", "\033[32m", "\033[33m", "\033[90m", "\033[1m", "\033[0m") if COLOR else ("",) * 6


def bar(frac, glyph, color, width=24):
    full = round(max(0.0, min(1.0, frac)) * width)
    return f"{color}{glyph * full}{RESET}{GREY}{'·' * (width - full)}{RESET}"


def hm(minutes):
    return f"{int(minutes // 60)}:{int(minutes % 60):02d}"


def main():
    now = dt.datetime.now().replace(second=0, microsecond=0)
    t = queue_times()
    start = min((v for (e, k), v in t.items() if k == "start"), default=now)
    print(f"{BOLD}Rerun progress{RESET}  ·  started {start:%H:%M}  ·  now {now:%H:%M}   "
          f"{BLUE}▒ plan{RESET} = where the plan expected to be now   {GREEN}█ actual{RESET} = runs finished\n")
    tot_done = tot_plan = 0
    plan_cursor, proj_end = start, now
    plan_total = sum(p[3] for p in PLAN)
    for eid, label, n, plan_min, pat in PLAN:
        done, running, mins = runs_of(pat)
        tot_done += done; tot_plan += n
        w0 = plan_cursor; plan_cursor += dt.timedelta(minutes=plan_min)
        plan_frac = (now - w0).total_seconds() / 60 / plan_min
        plan_frac = max(0.0, min(1.0, plan_frac))
        act_frac = done / n
        s, e = t.get((eid, "start")), t.get((eid, "done"))
        if e:
            status = f"done in {hm((e - s).total_seconds() / 60)} (planned {hm(plan_min)})"
        elif s:
            elapsed = (now - s).total_seconds() / 60
            mean = elapsed / done if done else plan_min / n
            remaining = mean * (n - done)
            proj_end = now + dt.timedelta(minutes=remaining)
            status = f"running {hm(elapsed)}, ~{hm(remaining)} left (planned {hm(plan_min)})"
        else:
            proj_end += dt.timedelta(minutes=plan_min)
            status = f"queued (planned {hm(plan_min)})"
        col = GREEN if act_frac >= plan_frac else YELLOW
        mean_run = f"{sum(mins) / len(mins):.1f} min/run" if mins else ""
        print(f"{BOLD}{eid:<4}{RESET} {label:<26} plan   {bar(plan_frac, '▒', BLUE)} {plan_frac:>4.0%}")
        print(f"{'':<31} actual {bar(act_frac, '█', col)} {act_frac:>4.0%}  {done:>2}/{n:<2} {mean_run:<13} {status}")
    plan_frac = max(0.0, min(1.0, (now - start).total_seconds() / 60 / plan_total))
    act = tot_done / tot_plan
    col = GREEN if act >= plan_frac else YELLOW
    print(f"\n{BOLD}{'Total':<31}{RESET} plan   {bar(plan_frac, '▒', BLUE)} {plan_frac:>4.0%}   planned end {plan_cursor:%H:%M}")
    print(f"{'':<31} actual {bar(act, '█', col)} {act:>4.0%}  {tot_done}/{tot_plan}  projected end {proj_end:%H:%M}")


if __name__ == "__main__":
    main()
