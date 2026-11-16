"""Generates the RECONSTRUCTED daycare case (synthetic structural example).

Not the original project data: built from the thesis description (section 6.2.4)
and the Finnish Early Childhood Education Act staffing ratios. Deterministic.
Also verifies that a feasible schedule exists (simple staggered reference).
"""
import math, random
import pandas as pd

random.seed(20261116)
T = lambda h, m=0: h * 60 + m
fmt = lambda x: f"{x // 60:02d}:{x % 60:02d}"
OPEN, CLOSE = T(6, 30), T(17, 0)
WEEK_MIN = 38 * 60 + 15  # 38 h 15 min
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]

groups = [  # name, age range, n children, n special-needs
    ("Nuput", (1, 2), 11, 1),
    ("Tenavat", (3, 4), 19, 1),
    ("Eskarit", (5, 6), 20, 0),
]
children, cid = [], 1
for g, (a0, a1), n, n_sn in groups:
    for i in range(n):
        arr = random.choice(range(T(6, 30), T(9, 16), 15))
        dep = random.choice(range(T(14, 30), T(17, 1), 15))
        part = a0 >= 3 and i % 6 == 5          # some part-time children (<= 5 h/day)
        if part:
            arr = random.choice([T(8, 0), T(8, 30), T(9, 0)]); dep = arr + random.choice([240, 270, 300])
        children.append({"Child ID": f"C{cid:02d}", "Group": g, "Age": random.randint(a0, a1),
                         "Arrival": fmt(arr), "Departure": fmt(dep),
                         "Special needs (counts as 2)": "yes" if i < n_sn else "no",
                         "_a": arr, "_d": dep, "_sn": i < n_sn})
        cid += 1

staff, sid = [], 1
for g, *_ in groups:
    for role in ["Teacher", "Childcare nurse", "Childcare nurse", "Childcare nurse"]:
        staff.append({"Employee ID": f"E{sid:02d}", "Home group": g, "Role": role,
                      "Weekly hours": "38:15"}); sid += 1
staff.append({"Employee ID": f"E{sid:02d}", "Home group": "Floating (any group)", "Role": "Childcare nurse",
              "Weekly hours": "38:15"})

rules = [
    ("R1", "Opening hours", "Daycare is open Mon-Fri 06:30-17:00."),
    ("R2", "Ratio under 3 years", "At least 1 adult per 4 children aged under 3 present."),
    ("R3", "Ratio 3+ years, full-time", "At least 1 adult per 7 children aged 3 or older whose daily care time exceeds 5 hours."),
    ("R4", "Ratio 3+ years, part-time", "At least 1 adult per 13 children aged 3 or older whose daily care time is at most 5 hours."),
    ("R5", "Special needs", "A child with special needs counts as two children in the ratio calculation."),
    ("R6", "Ratios hold per group at all times", "Ratios must hold in every group at every moment, based on each child's own arrival and departure time."),
    ("R7", "Weekly working time", "Every employee works exactly 38 h 15 min per week."),
    ("R8", "Home groups", "Employees work in their home group; the floating employee may work in any group."),
    ("R9", "Rotating tasks", "Opening shift (starts 06:30) and closing shift (ends 17:00) rotate between employees."),
    ("R10", "Balanced workload", "Opening and closing shifts are distributed as evenly as possible over the week."),
    ("R11", "Never alone at open/close", "At least 2 employees are in the building whenever any child is present."),
]

def required(group, t):
    u3 = ft = pt = 0.0
    for c in children:
        if c["Group"] != group or not (c["_a"] <= t < c["_d"]): continue
        w = 2 if c["_sn"] else 1
        if c["Age"] < 3: u3 += w
        elif c["_d"] - c["_a"] > 300: ft += w
        else: pt += w
    return math.ceil(u3 / 4 + ft / 7 + pt / 13 - 1e-9)

# Feasibility witness: per group, search four 7h39 shifts (15-min start grid) covering
# the requirement all day with at least one opener (06:30) and one closer (17:00).
# The same pattern can rotate between the four home-group employees over the week,
# so a schedule satisfying R1-R11 exists even without using the floating employee.
import itertools
D = WEEK_MIN // 5
grid = list(range(OPEN, CLOSE - D, 15)) + [CLOSE - D]
ok = True
for g, *_ in groups:
    need = {t: required(g, t) for t in range(OPEN, CLOSE)}  # every minute
    sol = next((c for c in itertools.combinations_with_replacement(grid, 4)
                if OPEN in c and CLOSE - D in c
                and all(sum(1 for s in c if s <= t < s + D) >= n for t, n in need.items())), None)
    print(g, "peak need", max(need.values()), "reference shift starts:", [fmt(x) for x in sol] if sol else None)
    ok &= sol is not None
print("feasible:", ok, "| children:", len(children), "| staff:", len(staff))

pub = lambda rows: [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
with pd.ExcelWriter(__import__("pathlib").Path(__file__).with_name("daycare_structure_example.xlsx"), engine="openpyxl") as w:
    pd.DataFrame(pub(children)).to_excel(w, sheet_name="Children", index=False)
    pd.DataFrame(staff).to_excel(w, sheet_name="Staff", index=False)
    pd.DataFrame(rules, columns=["Rule ID", "Rule", "Description"]).to_excel(w, sheet_name="Rules", index=False)
