"""Dataset D: synthetic daycare built to match the pilot task description (about 45 children in three
groups, 11 staff, the company's shift slots), plus the rule checker, a heuristic reference solution and
the replayed human baseline.

  synthetic_daycare.py make                 -> writes synthetic_daycare.xlsx, prompt.txt, reference/baseline CSVs
  synthetic_daycare.py check <table.csv>    -> scores a weekly rotation table (columns: Vko + the 11 shift slots)

Everything about children and staff profiles is SYNTHETIC. Only the shift slots and the
(pseudonymised) rotation history for weeks 5-17 come from the daycare's own material.
"""
import csv, json, math, random, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent   # the datasets directory
XLSX = HERE / "synthetic_daycare.xlsx"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
T = lambda s: int(str(s).replace(".", ":").split(":")[0]) * 60 + int(str(s).replace(".", ":").split(":")[1])
F = lambda m: f"{m // 60:02d}:{m % 60:02d}"
SLOTS = [("6.20-14.10", "06:20", "14:10"), ("(7.00) 7.30-15.10", "07:30", "15:10"), ("7.40-15.30", "07:40", "15:30"),
         ("7.50-15.40", "07:50", "15:40"), ("8.00-15.50", "08:00", "15:50"), ("8.00-16.00", "08:00", "16:00"),
         ("8.10-16.00", "08:10", "16:00"), ("8.20-16.10", "08:20", "16:10"), ("8.40-16.20", "08:40", "16:20"),
         ("9.00-16.40", "09:00", "16:40"), ("9.00-17.00", "09:00", "17:00")]
SLOT_NAMES = [s[0] for s in SLOTS]
GRID = range(T("06:20"), T("17:00"), 10)
RATIO = {"under 3": 4, "over 3": 7, "mixed": 1.75}
NEW_WEEKS = [18, 19, 20, 21]
CLOSED = {(18, "Thu"): "1 May (public holiday)"}


def build():
    """Attendance is constructed so that the stated rules are (nearly) satisfiable with 11 staff:
    about 80 % of children present per day, early mornings and late afternoons concentrated in
    one group, Friday lighter where a part-time employee is off."""
    rnd = random.Random(2025)
    off = lambda day: ",".join(d for d in DAYS if d != day)
    kids, n = [], 1
    def add(g, cat, age, arr, dep, days, m=1):
        nonlocal n
        kids.append({"Child": f"Child {n}", "Group": g, "Age group": cat, "Age": age, "Special needs multiplier": m,
                     "Arrival": arr, "Departure": dep, "Attending days": days}); n += 1
    for i in range(15):                                     # under 3: 12 of 15 present each day
        add("Robin", "under 3", rnd.randint(1, 2), rnd.choice(["07:30", "07:40", "08:00", "08:00", "08:30", "09:00"]),
            rnd.choice(["14:30", "15:00", "15:30", "15:30", "16:00"]), off(DAYS[i % 5]))
    peip_off = ["Fri"] * 8 + ["Mon"] * 4 + ["Tue"] * 4 + ["Wed"] * 4 + ["Thu"] * 5
    for i in range(25):                                     # over 3: four special-needs children here
        m = {0: 3, 1: 3, 8: 2, 12: 2}.get(i, 1)
        if i % 6 == 5: arr, dep = "08:30", rnd.choice(["12:30", "13:00"])          # part-time children
        else: arr, dep = rnd.choice(["06:30", "07:00", "07:30", "08:00", "08:00", "08:30", "09:00"]), rnd.choice(["15:00", "15:30", "16:00", "16:30", "17:00"])
        add("Finch", "over 3", rnd.randint(3, 6), arr, dep, off(peip_off[i]), m)
    for i in range(5):                                      # mixed group: two children Mon-Wed only
        add("Lark", "mixed", rnd.randint(2, 5), rnd.choice(["08:10", "08:20", "08:30"]), rnd.choice(["15:00", "15:30", "15:50"]),
            "Mon-Wed" if i >= 3 else "Mon-Fri")
    staff = [("Staff01", "Robin", "teacher"), ("Staff04", "Robin", "caregiver"), ("Staff07", "Robin", "caregiver"),
             ("Staff05", "Robin", "caregiver"), ("Staff10", "Finch", "teacher"), ("Staff02", "Finch", "teacher"),
             ("Staff09", "Finch", "caregiver"), ("Staff03", "Finch", "caregiver"), ("Staff06", "Lark", "teacher"),
             ("Staff11", "Lark", "caregiver"), ("Assistant", "Lark", "assistant")]
    hours = {"Staff03": ("30:35", "Mon-Thu"), "Assistant": ("19:08", "Mon-Wed")}
    vac = {"Staff07": "week 19 Mon-Tue", "Staff02": "week 20 Mon", "Staff04": "week 21 Fri"}
    staff = [{"Name": s, "Group": g, "Role": r, "Weekly hour target": hours.get(s, ("38:15", "Mon-Fri"))[0],
              "Working days": hours.get(s, ("38:15", "Mon-Fri"))[1], "Vacation / time off (weeks 18-21)": vac.get(s, "")}
             for s, g, r in staff]
    return kids, staff


def daylist(spec):
    spec = spec.strip()
    if "-" in spec and "," not in spec:
        a, b = spec.split("-"); return DAYS[DAYS.index(a):DAYS.index(b) + 1]
    return [d.strip() for d in spec.split(",")]


def load():
    kids = pd.read_excel(XLSX, sheet_name="Children").to_dict("records")
    staff = pd.read_excel(XLSX, sheet_name="Staff").fillna("").to_dict("records")
    return kids, staff


def need_profile(kids):
    """(day, group, t) -> adults required."""
    need = {}
    for d in DAYS:
        for g in {k["Group"] for k in kids}:
            for t in GRID:
                u = sum(k["Special needs multiplier"] / RATIO[k["Age group"]] for k in kids
                        if k["Group"] == g and d in daylist(k["Attending days"]) and T(k["Arrival"]) <= t < T(k["Departure"]))
                need[(d, g, t)] = math.ceil(u - 1e-9)
    return need


def off_days(st, week):
    off = {d for d in DAYS if d not in daylist(st["Working days"])}
    v = st["Vacation / time off (weeks 18-21)"]
    if v.startswith(f"week {week}"):
        rest = v[len(f"week {week}"):].strip()
        off |= set(DAYS) if "whole" in rest else set(daylist(rest))
    return off | {d for (w, d) in CLOSED if w == week}


def score(table, kids=None, staff=None):
    """table: {week: [name or '' for each of the 11 slots]}"""
    if kids is None: kids, staff = load()
    need = need_profile(kids)
    by = {s["Name"]: s for s in staff}
    rep = {"weeks_scheduled": sorted(table), "unknown_names": [], "duplicate_assignments": 0, "empty_slots": 0,
           "staff_missing_from_week": 0, "vacation_or_offday_conflicts": 0}
    short_min = short_staff_min = demand = 0
    slot_hist = {s: [] for s in by}
    for w, row in sorted(table.items()):
        names = [x for x in row if x and x.lower() != "loma"]
        rep["empty_slots"] += sum(1 for x in row if not x)
        rep["unknown_names"] += [x for x in names if x not in by]
        rep["duplicate_assignments"] += len(names) - len(set(names))
        rep["staff_missing_from_week"] += sum(1 for s in by if s not in names and off_days(by[s], w) != set(DAYS))
        for i, x in enumerate(row):
            if x in by:
                slot_hist[x].append(i)
                if off_days(by[x], w) == set(DAYS): rep["vacation_or_offday_conflicts"] += 1
        for d in DAYS:
            if (w, d) in CLOSED: continue
            for g in {k["Group"] for k in kids}:
                for t in GRID:
                    have = sum(1 for i, x in enumerate(row) if x in by and by[x]["Group"] == g
                               and d not in off_days(by[x], w) and T(SLOTS[i][1]) <= t < T(SLOTS[i][2]))
                    n = need[(d, g, t)]
                    demand += 10 if n else 0
                    if n > have: short_min += 10; short_staff_min += 10 * (n - have)
    rep["ratio"] = {"share_of_group_time_understaffed": round(short_min / demand, 3) if demand else None,
                    "missing_staff_hours_per_week": round(short_staff_min / 60 / max(len(table), 1), 1)}
    rep["rotation"] = {
        "same_slot_two_weeks_running": sum(1 for h in slot_hist.values() for a, b in zip(h, h[1:]) if a == b),
        "opening_slot_holders": len({x for row in table.values() for x in row[:1] if x in by}),
        "closing_slot_holders": len({x for row in table.values() for x in row[-1:] if x in by})}
    rep["valid_table"] = not rep["unknown_names"] and rep["duplicate_assignments"] == 0 and bool(table)
    return rep


def read_table(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    return {int(r[0]): [c.strip() for c in r[1:12]] + [""] * (11 - len(r[1:12])) for r in rows[1:] if r and r[0].strip().isdigit()}


def write_table(table, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["Vko"] + SLOT_NAMES)
        for wk in sorted(table): w.writerow([wk] + table[wk])


def reference(kids, staff, prev_row):
    """Heuristic best-known solution: per week, swap-based local search over slot permutations."""
    rnd = random.Random(1)
    table, prev = {}, prev_row
    for w in NEW_WEEKS:
        avail = [s["Name"] for s in staff if off_days(s, w) != set(DAYS)]
        best = None
        for _ in range(6):
            cur = avail + [""] * (11 - len(avail)); rnd.shuffle(cur)
            cost = lambda r: score({w: r}, kids, staff)["ratio"]["missing_staff_hours_per_week"] + 0.5 * sum(a == b and a != "" for a, b in zip(r, prev))
            c, improved = cost(cur), True
            while improved:
                improved = False
                for i in range(11):
                    for j in range(i + 1, 11):
                        cur[i], cur[j] = cur[j], cur[i]; c2 = cost(cur)
                        if c2 < c - 1e-9: c, improved = c2, True
                        else: cur[i], cur[j] = cur[j], cur[i]
            if best is None or c < best[0]: best = (c, cur[:])
        table[w] = prev = best[1]
    return table


def make():
    kids, staff = build()
    hist = pd.read_excel(ROOT / "A_pilot_rotation/shift_rotation.xlsx", dtype=str).fillna("")
    shifts = pd.DataFrame([{"Shift": n, "Start": a, "End": b, "Length (h:mm)": F(T(b) - T(a))[1:] if T(b) - T(a) < 600 else F(T(b) - T(a))} for n, a, b in SLOTS])
    with pd.ExcelWriter(XLSX, engine="openpyxl") as w:
        hist.to_excel(w, sheet_name="Shift rotation", index=False)
        shifts.to_excel(w, sheet_name="Shifts", index=False)
        pd.DataFrame(staff).to_excel(w, sheet_name="Staff", index=False)
        pd.DataFrame(kids).to_excel(w, sheet_name="Children", index=False)
    src = (ROOT / "A_pilot_rotation/prompt.txt").read_text(encoding="utf-8")
    (HERE / "prompt.txt").write_text(src, encoding="utf-8")       # task description unchanged
    kids, staff = load()
    h = {int(r["Vko"]): [r[c] for c in SLOT_NAMES] for _, r in hist.iterrows() if r["Vko"].isdigit() and r[SLOT_NAMES[1]]}
    base = {NEW_WEEKS[i]: h[wk] for i, wk in enumerate([14, 15, 16, 17])}   # daycare's own last four weeks, replayed
    ref = reference(kids, staff, h[17])
    write_table(base, HERE / "human_baseline_weeks14-17_replayed.csv"); write_table(ref, HERE / "reference_heuristic.csv")
    need = need_profile(kids)
    print("children:", len(kids), {g: sum(k["Group"] == g for k in kids) for g in ["Robin", "Finch", "Lark"]},
          "| peak adults Mon:", {g: max(need[("Mon", g, t)] for t in GRID) for g in ["Robin", "Finch", "Lark"]})
    rr = random.Random(7); names = [x["Name"] for x in staff]; rand = []
    for _ in range(30):
        t = {w: rr.sample(names, 11) for w in NEW_WEEKS}; rand.append(score(t, kids, staff)["ratio"]["missing_staff_hours_per_week"])
    print("random permutations: missing staff-hours/week mean %.1f min %.1f max %.1f" % (sum(rand) / 30, min(rand), max(rand)))
    for name, t in [("human baseline", base), ("reference", ref)]:
        r = score(t, kids, staff); print(name, r["ratio"], r["rotation"], "conflicts", r["vacation_or_offday_conflicts"], "valid", r["valid_table"])


if __name__ == "__main__":
    if sys.argv[1] == "make": make()
    else: print(json.dumps(score(read_table(sys.argv[2])), indent=1, ensure_ascii=False))
