#!/usr/bin/env python
"""Aggregates run directories under runs/ into one table per experiment.

Runs are grouped by their name without the trailing _rNN (e.g. D_mas_r01 .. D_mas_r05 -> D_mas).
Handles both MAS-harness runs (summary.json + steps/) and direct-LLM runs (result.json).

Usage: aggregate_runs.py [runs-dir] [out.csv]
"""
import csv
import glob
import json
import os
import re
import sys
from collections import OrderedDict

RUNS = sys.argv[1] if len(sys.argv) > 1 else "runs"
OUT = sys.argv[2] if len(sys.argv) > 2 else None


def experiment(run_dir):
    name = os.path.basename(run_dir)
    name = re.sub(r"^\d{8}-\d{6}_", "", name)
    return re.sub(r"_r\d+$", "", name)


def analysed_rounds(run_dir):
    """Rounds that reached the output analyzer (also present in runs aborted at the step limit)."""
    out = []
    for st in sorted(glob.glob(os.path.join(run_dir, "steps", "*code_output_analyzer_agent", "state.json"))):
        r = json.load(open(st)).get("result")
        if isinstance(r, dict):
            out.append(r)
    return out


rows = OrderedDict()
for d in sorted(glob.glob(os.path.join(RUNS, "*"))):
    exp = experiment(d)
    if os.path.exists(os.path.join(d, "summary.json")):
        s = json.load(open(os.path.join(d, "summary.json")))
        res = analysed_rounds(d)
        r = rows.setdefault(exp, dict(experiment=exp, kind="mas", runs=0, completed=0, stopped_at_step_limit=0,
                                      executions=0, failed_executions=0, analysed_rounds=0, self_rated_achieved=0,
                                      mean_duration_s=0.0, model=s["models"]["llm_code"]))
        r["runs"] += 1
        r["completed"] += s["outcome"] == "completed"
        r["stopped_at_step_limit"] += "Recursion" in (s.get("error") or "")
        r["executions"] += s["n_docker_executions"]
        r["failed_executions"] += s["n_docker_failures"]
        r["analysed_rounds"] += len(res)
        r["self_rated_achieved"] += sum(1 for x in res if re.match(r"\s*(true|yes)", str(x.get("is_goal_achieved")), re.I))
        r["mean_duration_s"] += s["duration_s"]
    elif os.path.exists(os.path.join(d, "result.json")):
        s = json.load(open(os.path.join(d, "result.json")))
        r = rows.setdefault(exp, dict(experiment=exp, kind="direct", runs=0, completed=0, stopped_at_step_limit=0,
                                      executions=0, failed_executions=0, analysed_rounds=0, self_rated_achieved=0,
                                      mean_duration_s=0.0, model=s["model"]))
        r["runs"] += 1
        r["completed"] += bool(s.get("valid"))
        r["analysed_rounds"] += s.get("n_turns", 0)
        r["mean_duration_s"] += s.get("duration_s", 0)
for r in rows.values():
    r["mean_duration_s"] = round(r["mean_duration_s"] / r["runs"], 1)

fields = list(next(iter(rows.values())).keys()) if rows else []
w = csv.DictWriter(open(OUT, "w", newline="") if OUT else sys.stdout, fieldnames=fields)
w.writeheader()
w.writerows(rows.values())
