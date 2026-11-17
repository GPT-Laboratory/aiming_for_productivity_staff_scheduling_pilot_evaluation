"""Independent recount of dataset D's main score, missing staff-hours per week, for cross-checking
`synthetic_daycare.py check`. Written from the workbook and the task text only; it shares no code
with the checker. Rules: a child counts towards its group's need while present (arrival <= t <
departure) on its attending days, weighted by its special-needs multiplier and divided by the
ratio for its age group (under 3: 4, over 3: 7, mixed: 1.75); the group needs the rounded-up sum.
An adult counts in their own group during their shift slot on days they work (working days minus
vacation; 1 May, week 18 Thursday, is closed). Time is checked every 10 minutes, 06:20-17:00.

Usage: recount_independent.py <weekly table.csv> [--compare]   (csv: Vko + the 11 shift slots)
       --compare also runs the checker and reports whether the two agree.
"""
import math, re, sys
from pathlib import Path
import pandas as pd

X = Path(__file__).with_name("synthetic_daycare.xlsx")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
SLOTS = [("06:20", "14:10"), ("07:30", "15:10"), ("07:40", "15:30"), ("07:50", "15:40"), ("08:00", "15:50"), ("08:00", "16:00"),
         ("08:10", "16:00"), ("08:20", "16:10"), ("08:40", "16:20"), ("09:00", "16:40"), ("09:00", "17:00")]
PER_ADULT = {"under 3": 4, "over 3": 7, "mixed": 1.75}
CLOSED = {(18, "Thu")}  # 1 May


def mins(t):
    h, m = re.split("[:.]", str(t).strip())[:2]
    return int(h) * 60 + int(m)


def days(spec):
    spec = str(spec).strip()
    if "-" in spec and "," not in spec:
        a, b = spec.split("-")
        return DAYS[DAYS.index(a):DAYS.index(b) + 1]
    return [x.strip() for x in spec.split(",")]


def recount(table_csv):
    kids = pd.read_excel(X, sheet_name="Children")
    staff = {r["Name"]: r for _, r in pd.read_excel(X, sheet_name="Staff").fillna("").iterrows()}

    def off(person, week):
        o = {d for d in DAYS if d not in days(person["Working days"])}
        v = str(person["Vacation / time off (weeks 18-21)"])
        if v.startswith(f"week {week}"):
            o |= set(days(v[len(f"week {week}"):].strip()))
        return o

    table = pd.read_csv(table_csv, dtype=str).fillna("")
    missing_minutes = 0
    for _, row in table.iterrows():
        week = int(row.iloc[0])
        names = [str(x).strip() for x in row.iloc[1:12]]
        for d in DAYS:
            if (week, d) in CLOSED:
                continue
            for g in kids["Group"].unique():
                for t in range(mins("06:20"), mins("17:00"), 10):
                    load = sum(k["Special needs multiplier"] / PER_ADULT[k["Age group"]] for _, k in kids.iterrows()
                               if k["Group"] == g and d in days(k["Attending days"]) and mins(k["Arrival"]) <= t < mins(k["Departure"]))
                    need = math.ceil(load - 1e-9)
                    have = sum(1 for i, n in enumerate(names) if n in staff and staff[n]["Group"] == g
                               and d not in off(staff[n], week) and mins(SLOTS[i][0]) <= t < mins(SLOTS[i][1]))
                    missing_minutes += 10 * max(0, need - have)
    return round(missing_minutes / 60 / len(table), 1)


if __name__ == "__main__":
    value = recount(sys.argv[1])
    print(f"independent recount: missing staff-hours per week = {value}")
    if "--compare" in sys.argv:
        sys.path.insert(0, str(Path(__file__).parent))
        import synthetic_daycare as sd
        checker = sd.score(sd.read_table(sys.argv[1]))["ratio"]["missing_staff_hours_per_week"]
        print(f"checker:             missing staff-hours per week = {checker}  ->  {'agree' if checker == value else 'DIFFER'}")
