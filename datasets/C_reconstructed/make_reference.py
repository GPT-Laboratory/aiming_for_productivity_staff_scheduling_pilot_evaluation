"""Hand-constructed feasible reference schedule (shows the instance is solvable)."""
import csv
from pathlib import Path
D = 459
f = lambda x: f"{x // 60:02d}:{x % 60:02d}"
t = lambda s: int(s[:2]) * 60 + int(s[3:])
import itertools, math
import pandas as pd
kids = pd.read_excel(Path(__file__).with_name("daycare_structure_example.xlsx"), sheet_name="Children").to_dict("records")
def required(g, m):
    u3 = ft = pt = 0
    for c in kids:
        a, d = t(c["Arrival"]), t(c["Departure"])
        if c["Group"] != g or not (a <= m < d): continue
        w = 2 if c["Special needs (counts as 2)"] == "yes" else 1
        if c["Age"] < 3: u3 += w
        elif d - a > 300: ft += w
        else: pt += w
    return math.ceil(u3 / 4 + ft / 7 + pt / 13 - 1e-9)
grid = list(range(390, 561, 15)) + [561]
pat = {}
for g in ["Nuput", "Tenavat", "Eskarit"]:
    need = {m: required(g, m) for m in range(390, 1020)}
    sol = next(c for c in itertools.combinations_with_replacement(grid, 4) if 390 in c and 561 in c
               and all(sum(1 for s in c if s <= m < s + D) >= n for m, n in need.items()))
    pat[g] = [f(x) for x in sol]
print("reference shift starts:", pat)
emp = {"Nuput": ["E01", "E02", "E03", "E04"], "Tenavat": ["E05", "E06", "E07", "E08"], "Eskarit": ["E09", "E10", "E11", "E12"]}
days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
rows = []
for g in pat:
    for d, day in enumerate(days):
        for i, e in enumerate(emp[g]):
            rows.append([e, day, pat[g][(i + d) % 4], g])
# Floating employee E13 relieves one double opening and one double closing; the relieved
# employee works an extra mid shift in the home group instead.
def swap(e, day, new_start):
    for r in rows:
        if r[0] == e and r[1] == day:
            old = r[2]; r[2] = new_start; return old, r[3]
o, g = swap("E01", "Fri", "08:00"); rows.append(["E13", "Fri", o, g])
o, g = swap("E08", "Mon", "08:00"); rows.append(["E13", "Mon", o, g])
for day in ["Tue", "Wed", "Thu"]:
    rows.append(["E13", day, "08:00", "Eskarit"])
with open(Path(__file__).with_name("reference_schedule.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["employee", "day", "start", "end", "group"])
    for e, day, s, g in sorted(rows):
        w.writerow([e, day, s, f(t(s) + D), g])
