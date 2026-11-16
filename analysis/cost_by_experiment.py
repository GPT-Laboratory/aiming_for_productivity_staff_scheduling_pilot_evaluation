#!/usr/bin/env python
"""Splits an OpenRouter activity export (CSV) between experiment runs by timestamp.

Runs were executed one at a time, so each API call is attributed to the latest run that had
started before it. Run directories are named <YYYYmmdd-HHMMSS>_<experiment>_rNN in local time;
the export is in UTC, so pass the local UTC offset.

Only aggregate figures are written; the export itself (generation ids, key names, location
fields) should not be committed.

Usage: cost_by_experiment.py <openrouter_activity.csv> [--runs runs] [--utc-offset 2] [--out results/cost_by_experiment.csv]
"""
import argparse
import csv
import datetime as dt
import glob
import os
import re
from collections import Counter, OrderedDict

ap = argparse.ArgumentParser()
ap.add_argument("export")
ap.add_argument("--runs", default="runs")
ap.add_argument("--utc-offset", type=float, default=2)
ap.add_argument("--out")
a = ap.parse_args()

runs = []
for d in sorted(glob.glob(os.path.join(a.runs, "*"))):
    name = os.path.basename(d)
    m = re.match(r"(\d{8}-\d{6})_(.+?)(?:_r(\d+))?$", name)
    if m:
        runs.append((dt.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S"), name, m.group(2)))

per_run, per_exp = {}, OrderedDict((e, Counter()) for _, _, e in runs)
for r in csv.DictReader(open(a.export, encoding="utf-8")):
    t = dt.datetime.strptime(r["created_at"][:19], "%Y-%m-%d %H:%M:%S") + dt.timedelta(hours=a.utc_offset)
    cand = [x for x in runs if x[0] <= t]
    if not cand:
        continue
    _, name, exp = cand[-1]
    per_run.setdefault(name, exp)
    c = per_exp[exp]
    c["calls"] += 1
    c["cost_usd"] += float(r["cost_total"] or 0)
    for k in ("tokens_prompt", "tokens_completion", "tokens_reasoning", "tokens_cached"):
        c[k] += int(float(r[k] or 0))

rows = []
for exp, c in per_exp.items():
    n = sum(1 for e in per_run.values() if e == exp)
    if not n:
        continue
    rows.append(dict(experiment=exp, runs_in_export=n, calls=c["calls"], prompt_tokens=c["tokens_prompt"],
                     completion_tokens=c["tokens_completion"], reasoning_tokens=c["tokens_reasoning"],
                     cached_tokens=c["tokens_cached"], cost_usd=round(c["cost_usd"], 3),
                     cost_per_run_usd=round(c["cost_usd"] / n, 3)))
out = open(a.out, "w", newline="") if a.out else None
w = csv.DictWriter(out or __import__("sys").stdout, fieldnames=list(rows[0].keys()))
w.writeheader()
w.writerows(rows)
