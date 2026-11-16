"""Scores a run whose program output lists, per weekday and 15-min slot, the employees present
(run r05 format). Converts it to the canonical CSV and runs check_schedule on it. The floating
employee is placed, slot by slot, in the group with the largest staffing gap (most favourable).
Usage: score_slot_output.py <step state.json> <out.csv>"""
import csv, json, re, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import check_schedule as cs

X = Path(__file__).with_name("daycare_structure_example.xlsx")
out = json.load(open(sys.argv[1]))["docker_output"]
home = dict(pd.read_excel(X, sheet_name="Staff")[["Employee ID", "Home group"]].values)
kids = pd.read_excel(X, sheet_name="Children").to_dict("records")
def need(g, t):
    import math
    u = f = p = 0
    for c in kids:
        a, d = cs.mins(c["Arrival"]), cs.mins(c["Departure"])
        if c["Group"] != g or not a <= t < d: continue
        w = 2 if c["Special needs (counts as 2)"] == "yes" else 1
        if c["Age"] < 3: u += w
        elif d - a > 300: f += w
        else: p += w
    return math.ceil(u / 4 + f / 7 + p / 13 - 1e-9)
rows, day, frag = [], None, {}
for line in out.splitlines():
    m = re.match(r"\s*(Monday|Tuesday|Wednesday|Thursday|Friday):\s*$", line)
    if m: day = m.group(1)[:3]; continue
    m = re.match(r"\s+(\d\d):(\d\d):00:\s*(.*)$", line)
    if not (m and day): continue
    t = int(m.group(1)) * 60 + int(m.group(2))
    emps = [e.strip() for e in m.group(3).split(",") if e.strip()]
    cnt = {}
    for e in emps:
        if not home[e].startswith("Floating"): cnt[home[e]] = cnt.get(home[e], 0) + 1
    for e in emps:
        g = home[e]
        if g.startswith("Floating"): g = max(["Nuput", "Tenavat", "Eskarit"], key=lambda x: need(x, t) - cnt.get(x, 0))
        rows.append([e, day, f"{t//60:02d}:{t%60:02d}", f"{(t+15)//60:02d}:{(t+15)%60:02d}", g])
        frag.setdefault((e, day), []).append(t)
with open(sys.argv[2], "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["employee", "day", "start", "end", "group"]); w.writerows(rows)
r = cs.check(sys.argv[2], X)
pieces = [1 + sum(1 for a, b in zip(v, v[1:]) if b - a != 15) for v in frag.values()]
r["separate_work_fragments_per_employee_day"] = {"mean": round(sum(pieces) / len(pieces), 1), "max": max(pieces)}
print(json.dumps({k: r[k] for k in ["rules_satisfied", "R2_R6_ratio", "R7_weekly_hours", "R9_R10_rotation", "R11_minutes_with_fewer_than_2_adults", "separate_work_fragments_per_employee_day"]}, indent=1))
