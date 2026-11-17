"""Scores a dataset-D roster given per day instead of per week: one row per (week, weekday) with a
name (or nothing) in each of the 11 shift slots, e.g. the "Daily detail" sheet some programs
write when the weekly rotation format cannot hold day-to-day changes.

Uses the same child data, ratios, groups, days off and 10-minute grid as `synthetic_daycare.py
check`, so "missing_staff_hours_per_week" is comparable with the weekly tables. A person counts
only in their own group and only on days they are available.

Two layouts are read: wide (week, day, then the 11 slots with a name or nothing) and long (one
row per person and day with columns Week, Day, Employee and Start/End or Shift; a row whose
Status says unassigned/vacancy is skipped). In the long layout a shift is matched to its slot
by its start and end times.

Usage: score_daily_detail.py <workbook.xlsx> [sheet name; default: the first sheet whose name
contains "daily"]   or   score_daily_detail.py <file.csv> with columns week,day,slot1..slot11
"""
import csv, json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import synthetic_daycare as sd


def slot_of(start, end, label=""):
    for i, (lab, a, b) in enumerate(sd.SLOTS):
        if (str(start)[:5], str(end)[:5]) == (a, b) or (label and str(label).strip() == lab):
            return i
    return None


def read_daily(path, sheet=None):
    """-> {(week, day): [(slot index, name), ...]}"""
    if str(path).endswith(".csv"):
        rows = list(csv.reader(open(path, encoding="utf-8")))
    else:
        x = pd.ExcelFile(path)
        sheet = sheet or next(s for s in x.sheet_names if "daily" in s.lower())
        rows = x.parse(sheet, header=None).fillna("").astype(str).values.tolist()
    head = [str(c).strip().lower() for c in rows[0]]
    daily = {}
    if "employee" in head:  # long layout
        col = {h: i for i, h in enumerate(head)}
        for r in rows[1:]:
            w, d = str(r[col["week"]]).split(".")[0].strip(), str(r[col["day"]]).strip()[:3]
            name = str(r[col["employee"]]).strip()
            status = str(r[col["status"]]).lower() if "status" in col else ""
            if not (w.isdigit() and d in sd.DAYS) or not name or "unassign" in status or "vacan" in status:
                continue
            i = slot_of(r[col["start"]] if "start" in col else "", r[col["end"]] if "end" in col else "",
                        r[col["shift"]] if "shift" in col else "")
            daily.setdefault((int(w), d), [])
            if i is not None:
                daily[(int(w), d)].append((i, name))
        return daily
    for r in rows[1:]:  # wide layout
        w, d = str(r[0]).strip().split(".")[0], str(r[1]).strip()[:3]
        if w.isdigit() and d in sd.DAYS:
            daily[(int(w), d)] = [(i, c.strip()) for i, c in enumerate(r[2:13]) if c.strip() not in ("", "-", "nan")]
    return daily


def score_daily(daily):
    kids, staff = sd.load()
    need = sd.need_profile(kids)
    by = {s["Name"]: s for s in staff}
    groups = {k["Group"] for k in kids}
    weeks = sorted({w for w, _ in daily})
    rep = {"weeks": weeks, "days_given": len(daily), "unknown_names": [], "empty_slots": 0,
           "double_booked_person_days": 0, "assigned_on_day_off": 0}
    short_min = short_staff_min = demand = 0
    minutes = {}
    for w in weeks:
        for d in sd.DAYS:
            if (w, d) in sd.CLOSED:
                continue
            row = daily.get((w, d), [])
            names = [x for _, x in row if x.lower() != "loma"]
            rep["empty_slots"] += 11 - len({i for i, x in row if x.lower() != "loma"})
            rep["unknown_names"] += [x for x in names if x not in by]
            rep["double_booked_person_days"] += len(names) - len(set(names))
            ok = []
            for i, x in row:
                if x not in by:
                    continue
                if d in sd.off_days(by[x], w):
                    rep["assigned_on_day_off"] += 1
                    continue
                ok.append((i, x))
                minutes[(w, x)] = minutes.get((w, x), 0) + sd.T(sd.SLOTS[i][2]) - sd.T(sd.SLOTS[i][1])
            for g in groups:
                for t in sd.GRID:
                    have = sum(1 for i, x in ok if by[x]["Group"] == g and sd.T(sd.SLOTS[i][1]) <= t < sd.T(sd.SLOTS[i][2]))
                    n = need[(d, g, t)]
                    demand += 10 if n else 0
                    if n > have:
                        short_min += 10; short_staff_min += 10 * (n - have)
    rep["unknown_names"] = sorted(set(rep["unknown_names"]))
    rep["ratio"] = {"share_of_group_time_understaffed": round(short_min / demand, 3) if demand else None,
                    "missing_staff_hours_per_week": round(short_staff_min / 60 / max(len(weeks), 1), 1)}
    over = []
    for (w, x), m in sorted(minutes.items()):
        st = by[x]
        days = [d for d in sd.DAYS if d not in sd.off_days(st, w)]
        target = sd.T(st["Weekly hour target"]) * len(days) / len(sd.daylist(st["Working days"]))
        if m - target > 60:
            over.append(f"week {w} {x}: {m / 60:.1f} h vs target {target / 60:.1f} h")
    rep["hours_over_target_by_more_than_1h"] = over
    rep["mean_weekly_hours_vs_target"] = round(sum(minutes.values()) / 60 / max(len(minutes), 1), 1)
    return rep


if __name__ == "__main__":
    print(json.dumps(score_daily(read_daily(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)), indent=1))
