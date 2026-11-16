"""Scores a program output that lists, per weekday and time slot, the employees present, in the form
    Day: 0, Time: 06:30:00, Staff: ['E01', 'E02']
(the form several MAS 2025 programs printed; day 0 = Monday). Generalises score_slot_output.py to
any slot length. Each slot becomes one row of the canonical CSV and check_schedule runs on it. The
floating employee is placed, slot by slot, in the group with the largest staffing gap (most
favourable to the program). The output does not say which group anyone works in; employees are
counted in their home group.
Usage: score_presence_output.py <program stdout> <out.csv>"""
import ast, csv, json, math, re, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import check_schedule as cs

X = Path(__file__).with_name("daycare_structure_example.xlsx")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
home = dict(pd.read_excel(X, sheet_name="Staff")[["Employee ID", "Home group"]].values)
kids = pd.read_excel(X, sheet_name="Children").to_dict("records")


def need(g, t):
    u = f = p = 0
    for c in kids:
        a, d = cs.mins(c["Arrival"]), cs.mins(c["Departure"])
        if c["Group"] != g or not a <= t < d:
            continue
        w = 2 if c["Special needs (counts as 2)"] == "yes" else 1
        if c["Age"] < 3: u += w
        elif d - a > 300: f += w
        else: p += w
    return math.ceil(u / 4 + f / 7 + p / 13 - 1e-9)


def score(text, out_csv):
    slots = []
    for line in text.splitlines():
        m = re.match(r"\s*Day:\s*(\d+),\s*Time:\s*(\d\d):(\d\d)(?::\d\d)?,\s*Staff:\s*(\[.*\])\s*$", line)
        if m:
            slots.append((int(m.group(1)), int(m.group(2)) * 60 + int(m.group(3)), ast.literal_eval(m.group(4))))
    if not slots:
        return None
    times = sorted({t for _, t, _ in slots})
    step = min(b - a for a, b in zip(times, times[1:]))
    rows, frag = [], {}
    for d, t, emps in slots:
        cnt = {}
        for e in emps:
            if not home[e].startswith("Floating"):
                cnt[home[e]] = cnt.get(home[e], 0) + 1
        for e in emps:
            g = home[e]
            if g.startswith("Floating"):
                g = max(["Nuput", "Tenavat", "Eskarit"], key=lambda x: need(x, t) - cnt.get(x, 0))
            rows.append([e, DAYS[d], f"{t//60:02d}:{t%60:02d}", f"{(t+step)//60:02d}:{(t+step)%60:02d}", g])
            frag.setdefault((e, d), []).append(t)
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["employee", "day", "start", "end", "group"]); w.writerows(rows)
    r = cs.check(out_csv, X)
    pieces = [1 + sum(1 for a, b in zip(v, v[1:]) if b - a != step) for v in frag.values()]
    r["slot_minutes"] = step
    r["max_staff_present_at_once"] = max(len(e) for _, _, e in slots)
    r["employees_appearing"] = len({e for _, _, es in slots for e in es})
    r["separate_work_fragments_per_employee_day"] = {"mean": round(sum(pieces) / len(pieces), 1), "max": max(pieces)}
    return r


if __name__ == "__main__":
    res = score(Path(sys.argv[1]).read_text(encoding="utf-8"), sys.argv[2])
    print(json.dumps(res, indent=1, default=str) if res else "no presence lines found")
