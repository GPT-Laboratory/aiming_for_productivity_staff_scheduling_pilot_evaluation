"""Independent checker for the reconstructed daycare case.

Input: a canonical schedule CSV with columns
    employee,day,start,end,group
(employee = E01..E13, day = Mon..Fri, times HH:MM, group = Nuput/Tenavat/Eskarit)
and the case Excel file. Checks rules R1-R11 minute by minute and prints a JSON report.

Usage: check_schedule.py <schedule.csv> [daycare_structure_example.xlsx]
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
OPEN, CLOSE = 6 * 60 + 30, 17 * 60
WEEK_MIN = 38 * 60 + 15


def mins(s):
    h, m = str(s).strip().split(":")[:2]
    return int(h) * 60 + int(m)


def check(schedule_csv, xlsx):
    children = pd.read_excel(xlsx, sheet_name="Children").to_dict("records")
    staff = pd.read_excel(xlsx, sheet_name="Staff").to_dict("records")
    home = {s["Employee ID"]: s["Home group"] for s in staff}
    groups = sorted({c["Group"] for c in children})
    for c in children:
        c["a"], c["d"] = mins(c["Arrival"]), mins(c["Departure"])
        c["w"] = 2 if str(c["Special needs (counts as 2)"]).lower() == "yes" else 1

    def required(group, t):
        u3 = ft = pt = 0
        for c in children:
            if c["Group"] != group or not (c["a"] <= t < c["d"]):
                continue
            if c["Age"] < 3:
                u3 += c["w"]
            elif c["d"] - c["a"] > 300:
                ft += c["w"]
            else:
                pt += c["w"]
        return math.ceil(u3 / 4 + ft / 7 + pt / 13 - 1e-9)

    shifts, bad_rows = [], []
    with open(schedule_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                shifts.append((row["employee"].strip(), row["day"].strip()[:3].title(),
                               mins(row["start"]), mins(row["end"]), row["group"].strip()))
            except Exception as exc:
                bad_rows.append(f"{row}: {exc}")

    rep = {"n_shifts": len(shifts), "unparseable_rows": bad_rows}
    rep["unknown_employees"] = sorted({e for e, *_ in shifts if e not in home})
    rep["employees_without_shifts"] = sorted(set(home) - {e for e, *_ in shifts})
    rep["R1_outside_opening_hours"] = sum(1 for _, _, s, e, _ in shifts if s < OPEN or e > CLOSE or e <= s)

    # R2-R6 ratios per group and minute
    present = defaultdict(int)       # (day, group, minute) -> adults
    building = defaultdict(int)      # (day, minute) -> adults
    for e, d, s, en, g in shifts:
        for t in range(max(s, 0), min(en, 24 * 60)):
            present[(d, g, t)] += 1
            building[(d, t)] += 1
    need = {(g, t): required(g, t) for g in groups for t in range(OPEN, CLOSE)}
    short_min = short_staff_min = demand_min = 0
    worst = defaultdict(int)
    for d in DAYS:
        for g in groups:
            for t in range(OPEN, CLOSE):
                n = need[(g, t)]
                demand_min += 1 if n else 0
                gap = n - present[(d, g, t)]
                if gap > 0:
                    short_min += 1
                    short_staff_min += gap
                    worst[g] = max(worst[g], gap)
    rep["R2_R6_ratio"] = {
        "group_minutes_with_children": demand_min,
        "group_minutes_understaffed": short_min,
        "share_understaffed": round(short_min / demand_min, 3) if demand_min else None,
        "missing_staff_hours": round(short_staff_min / 60, 1),
        "worst_gap_adults_by_group": dict(worst),
    }

    # R7 weekly hours
    worked = defaultdict(int)
    for e, d, s, en, g in shifts:
        worked[e] += en - s
    rep["R7_weekly_hours"] = {
        "employees_exact_38h15": sum(1 for e in home if worked[e] == WEEK_MIN),
        "employees_total": len(home),
        "hours_by_employee": {e: f"{worked[e] // 60}:{worked[e] % 60:02d}" for e in sorted(home)},
    }

    # R8 home group
    rep["R8_shifts_outside_home_group"] = sum(
        1 for e, _, _, _, g in shifts if e in home and not home[e].startswith("Floating") and home[e] != g
    )
    rep["unknown_groups"] = sorted({g for *_, g in shifts if g not in groups})

    # R9/R10 opening and closing rotation
    opens, closes = defaultdict(int), defaultdict(int)
    for e, d, s, en, g in shifts:
        opens[e] += s == OPEN
        closes[e] += en == CLOSE
    ov = [opens[e] for e in home]
    cv = [closes[e] for e in home]
    rep["R9_R10_rotation"] = {
        "days_with_opener": len({d for e, d, s, *_ in shifts if s == OPEN}),
        "days_with_closer": len({d for e, d, s, en, g in shifts if en == CLOSE}),
        "employees_with_opening": sum(1 for v in ov if v),
        "employees_with_closing": sum(1 for v in cv if v),
        "opening_spread_max_minus_min": max(ov) - min(ov),
        "closing_spread_max_minus_min": max(cv) - min(cv),
    }

    # R11 at least two adults in the building while any child is present
    any_child = {t for t in range(OPEN, CLOSE) if any(c["a"] <= t < c["d"] for c in children)}
    rep["R11_minutes_with_fewer_than_2_adults"] = sum(
        1 for d in DAYS for t in any_child if building[(d, t)] < 2
    )

    rep["rules_satisfied"] = {
        "R1": rep["R1_outside_opening_hours"] == 0 and bool(shifts),
        "R2-R6": short_min == 0 and bool(shifts),
        "R7": rep["R7_weekly_hours"]["employees_exact_38h15"] == len(home),
        "R8": rep["R8_shifts_outside_home_group"] == 0 and not rep["unknown_groups"] and bool(shifts),
        "R9": rep["R9_R10_rotation"]["employees_with_opening"] > 1
        and rep["R9_R10_rotation"]["employees_with_closing"] > 1,
        "R10": rep["R9_R10_rotation"]["opening_spread_max_minus_min"] <= 1
        and rep["R9_R10_rotation"]["closing_spread_max_minus_min"] <= 1 and bool(shifts),
        "R11": rep["R11_minutes_with_fewer_than_2_adults"] == 0 and bool(shifts),
    }
    return rep


if __name__ == "__main__":
    xlsx = sys.argv[2] if len(sys.argv) > 2 else Path(__file__).with_name("daycare_structure_example.xlsx")
    print(json.dumps(check(sys.argv[1], xlsx), indent=2))
