#!/usr/bin/env python3
"""Analyse the rerun of Nov 2026: score every MAS round and every direct answer, and write

  results/rerun_mas_runs.csv     one row per MAS run (E3, E4)
  results/rerun_mas_rounds.csv   one row per analysed round of a MAS run
  results/rerun_direct_runs.csv  one row per direct run (E7-E12, plus the reused runs of 17 Nov)
  results/rerun_summary.csv      per experiment x dataset: mean, range and count of the main score

Scores: C = rule groups met of 7 (7 = all 11 rules) and minutes of understaffed group time;
D = missing staff-hours per week (weekly rotation; per-day roster if the weekly sheet is empty);
A, B = no rule checker: empty cells, whether Staff08 (no longer on the staff) is scheduled, and
the same person in the same slot two weeks running. Costs use Azure's gpt-6.1-terra prices of
17 Nov 2026; gpt-4o and gpt-4o-mini get token counts only.

Usage: experiments/rerun_2026-11/analyse.py   (from anywhere; reads runs/, writes results/)
"""
import csv, glob, json, re, statistics as st, sys, tempfile
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RUNS, RES = REPO / "runs", REPO / "results"
sys.path.insert(0, str(REPO / "datasets" / "C_reconstructed")); import check_schedule as cs
sys.path.insert(0, str(REPO / "datasets" / "D_synthetic")); import synthetic_daycare as sd, score_daily_detail as sdd
CX = REPO / "datasets" / "C_reconstructed" / "daycare_structure_example.xlsx"
PRICE = {"input": 1.08, "cached": 0.06, "output": 5.39}  # EUR per million tokens, gpt-6.1-terra
CURRENT = {"Staff01", "Staff02", "Staff03", "Staff04", "Staff05", "Staff06", "Staff07", "Staff09", "Staff10", "Staff11", "Assistant"}


def cost(inp, cached, out):
    return round(((inp - cached) * PRICE["input"] + cached * PRICE["cached"] + out * PRICE["output"]) / 1e6, 4)


# ------------------------------------------------------------------ scoring of one workbook
def weekly_table(x):
    sheet = next((n for n in x.sheet_names if "rotation" in n.lower()), x.sheet_names[0])
    r = x.parse(sheet, header=None).fillna("").astype(str)
    t = {}
    for row in r.values.tolist():
        w = row[0].split(".")[0].strip()
        if w.isdigit() and 18 <= int(w) <= 21:
            t[int(w)] = [c.strip() if c.strip().lower() not in ("nan", "-") else "" for c in row[1:12]]
    return t if t and sum(1 for v in t.values() for c in v if c) > 5 else None


def score_c_workbook(f):
    x = pd.ExcelFile(f)
    for sh in x.sheet_names:
        df = x.parse(sh)
        cols = {str(c).lower().strip(): c for c in df.columns}
        pick = lambda *k: next((cols[c] for c in cols if any(q in c for q in k)), None)
        e, dy, s, en, g = pick("employee"), pick("day"), pick("start"), pick("end", "finish"), pick("group")
        if all([e, dy, s, en, g]) and "home" not in str(g).lower():
            got = df[[e, dy, s, en, g]].dropna(); got.columns = ["employee", "day", "start", "end", "group"]
            got["day"] = got["day"].astype(str).str[:3]
            for c in ("start", "end"):
                got[c] = got[c].astype(str).str[:5]
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name
            got.to_csv(tmp, index=False)
            r = cs.check(tmp, CX)
            return {"score": sum(r["rules_satisfied"].values()), "failed": " ".join(k for k, v in r["rules_satisfied"].items() if not v),
                    "understaffed_min": r["R2_R6_ratio"]["group_minutes_understaffed"], "form": "workbook"}
    return None


def score_d_workbook(f):
    x = pd.ExcelFile(f)
    t = weekly_table(x)
    if t:
        r = sd.score(t)
        return {"score": r["ratio"]["missing_staff_hours_per_week"], "empty": r["empty_slots"],
                "conflicts": r["vacation_or_offday_conflicts"], "repeats": r["rotation"]["same_slot_two_weeks_running"], "form": "weekly"}
    if any("daily" in n.lower() for n in x.sheet_names):
        dd = sdd.score_daily(sdd.read_daily(f))
        if dd["days_given"]:
            return {"score": dd["ratio"]["missing_staff_hours_per_week"], "empty": dd["empty_slots"],
                    "conflicts": dd["assigned_on_day_off"], "repeats": None, "form": "daily"}
    return None


def score_ab_workbook(f):
    t = weekly_table(pd.ExcelFile(f))
    if not t:
        return None
    return describe_ab(t) | {"form": "weekly"}


def describe_ab(t):
    cells = [c for row in t.values() for c in row]
    names = {c for c in cells if c and c.lower() != "loma"}
    hist = {}
    for w in sorted(t):
        for i, x in enumerate(t[w]):
            if x and x.lower() != "loma":
                hist.setdefault(x, []).append(i)
    return {"score": None, "weeks": len(t), "empty": sum(1 for c in cells if not c), "staff08": "Staff08" in names,
            "unknown": " ".join(sorted(names - CURRENT - {"Staff08"})),
            "repeats": sum(1 for h in hist.values() for a, b in zip(h, h[1:]) if a == b)}


SCORER = {"A": score_ab_workbook, "B": score_ab_workbook, "C": score_c_workbook, "D": score_d_workbook}


def score_round(case, step_dir):
    """Score the workbook(s) the round's program wrote; the first scorable one counts."""
    for f in sorted(step_dir.glob("outputs/**/*.xlsx")):
        try:
            r = SCORER[case](f)
        except Exception:
            r = None
        if r:
            return r | {"file": f.name}
    return None


# ------------------------------------------------------------------ MAS runs
def mas_meta(name):
    m = re.search(r"_rr_([ABCD])_v2_(terra|4o)(_rev)?_r(\d+)$", name)
    return {"experiment": "E4" if m.group(2) == "terra" else "E3", "model": m.group(2), "dataset": m.group(1),
            "task_text": "revised" if m.group(3) else "C prompt", "rep": int(m.group(4))}


def analyse_mas():
    runs, rounds = [], []
    for d in sorted(RUNS.glob("*_rr_?_v2_*_r0?")):
        if not (d / "summary.json").exists():
            continue
        s = json.loads((d / "summary.json").read_text())
        meta = mas_meta(d.name)
        steps = sorted(p for p in (d / "steps").iterdir() if p.is_dir())
        last_run, rs = None, []
        for p in steps:
            if p.name.endswith("start_docker_container_agent"):
                last_run = p
            elif p.name.endswith("code_output_analyzer_agent") and last_run is not None:
                rs.append(last_run)
        pick = None
        fr = next((p for p in steps if p.name.endswith("final_report_agent")), None)
        if fr and (fr / "stream.txt").exists():
            m = re.search(r'"index_of_optimization"\s*:\s*(\d+)', (fr / "stream.txt").read_text())
            pick = int(m.group(1)) if m else None
        scored = []
        for i, p in enumerate(rs, 1):
            r = score_round(meta["dataset"], p) or {}
            ach = str((s["results"][i - 1] if i <= len(s["results"]) else {}).get("is_goal_achieved", ""))
            row = meta | {"run": d.name, "round": i, "program_step": p.name[:2], "picked": i == pick,
                          "self_rated_achieved": ach.strip().lower().startswith(("true", "yes")),
                          **{k: r.get(k) for k in ("score", "failed", "understaffed_min", "empty", "conflicts", "repeats", "staff08", "form", "file")}}
            rounds.append(row); scored.append(row)
        u = s.get("token_usage") or {}
        inp = sum(v["input"] for v in u.values()); ca = sum(v["cached_input"] for v in u.values())
        out = sum(v["output"] for v in u.values()); rea = sum(v["reasoning"] for v in u.values())
        final = next((r for r in scored if r["picked"]), scored[-1] if scored else None)
        runs.append(meta | {"run": d.name, "outcome": "step limit" if "Recursion" in str(s.get("error")) else s["outcome"],
                            "steps": s["n_steps"], "executions": s["n_docker_executions"], "failed_executions": s["n_docker_failures"],
                            "rounds": s["n_results"], "minutes": round(s["duration_s"] / 60, 1), "final_report_pick": pick,
                            "final_score": final["score"] if final else None, "final_form": final["form"] if final else None,
                            "scorable_rounds": sum(1 for r in scored if r["form"]),
                            "empty": final["empty"] if final else None, "staff08": final["staff08"] if final else None,
                            "repeats": final["repeats"] if final else None,
                            "best_round_score": (max if meta["dataset"] == "C" else min)([r["score"] for r in scored if r["score"] is not None], default=None),
                            "llm_calls": sum(v["calls"] for v in u.values()), "input_tokens": inp, "cached_input_tokens": ca,
                            "output_tokens": out, "reasoning_tokens": rea,
                            "cost_eur": cost(inp, ca, out) if meta["model"] == "terra" else None})
    return runs, rounds


# ------------------------------------------------------------------ direct runs
def direct_meta(name):
    m = re.search(r"_direct([ABCD])_(rr_)?(terra|gpt-4o-mini|gpt-4o)(_skill)?(_rev)?(_sim)?_r(\d+)$", name)
    if not m:
        return None
    if m.group(2):
        exp = "E12" if m.group(4) else {"terra": "E7", "gpt-4o": "E8", "gpt-4o-mini": "E9"}[m.group(3)]
        text = "revised" if m.group(5) else ("C prompt" if m.group(1) == "C" else "original")
    else:  # reused runs of 17 Nov, original text
        exp = "E10" if m.group(4) else ("E11" if m.group(6) else "E7-reused")
        text = "C prompt" if m.group(1) == "C" else "original"
    return {"experiment": exp, "model": m.group(3), "dataset": m.group(1), "skill": bool(m.group(4)),
            "sim_manager": bool(m.group(6)), "task_text": text, "rep": int(m.group(7))}


def analyse_direct():
    rows = []
    for d in sorted(RUNS.glob("*_direct?_*_r0?")):
        meta = direct_meta(d.name)
        if not meta or not (d / "result.json").exists():
            continue
        r = json.loads((d / "result.json").read_text())
        c = r.get("checker") or {}
        sc = {}
        if r["valid"] and c:
            if meta["dataset"] == "C":
                sc = {"score": sum(c["rules_satisfied"].values()), "failed": " ".join(k for k, v in c["rules_satisfied"].items() if not v),
                      "understaffed_min": c["R2_R6_ratio"]["group_minutes_understaffed"]}
            elif meta["dataset"] == "D":
                sc = {"score": c["ratio"]["missing_staff_hours_per_week"], "empty": c["empty_slots"],
                      "conflicts": c["vacation_or_offday_conflicts"], "repeats": c["rotation"]["same_slot_two_weeks_running"]}
            else:
                t = sd.read_table(d / "final_table.csv")
                sc = describe_ab(t)
        tu = r["turns"]
        inp = sum(t.get("prompt_tokens") or 0 for t in tu); out = sum(t.get("completion_tokens") or 0 for t in tu)
        ca = sum(t.get("cached_prompt_tokens") or 0 for t in tu); rea = sum(t.get("reasoning_tokens") or 0 for t in tu)
        rows.append(meta | {"run": d.name, "valid": r["valid"], "answers": r["n_turns"], "seconds": round(r["duration_s"]),
                            **{k: sc.get(k) for k in ("score", "failed", "understaffed_min", "empty", "conflicts", "repeats", "staff08")},
                            "input_tokens": inp, "cached_input_tokens": ca, "output_tokens": out, "reasoning_tokens": rea,
                            "tokens_detail": "full" if any("cached_prompt_tokens" in t for t in tu) else "prompt+completion only",
                            "cost_eur": cost(inp, ca, out) if meta["model"] == "terra" else None})
    return rows


# ------------------------------------------------------------------ summary
def summarise(mas, direct):
    out = []
    groups = {}
    for r in mas:
        groups.setdefault((r["experiment"], f"MAS v2 · {r['model']}", r["dataset"]), []).append((r["final_score"], r))
    for r in direct:
        label = f"direct · {r['model']}" + (" + skill" if r["skill"] else "") + (" + manager" if r["sim_manager"] else "") + f" · {r['task_text']}"
        groups.setdefault((r["experiment"], label, r["dataset"]), []).append((r["score"], r))
    for (exp, label, ds), xs in sorted(groups.items()):
        vals = [v for v, _ in xs if v is not None]
        rows = [r for _, r in xs]
        row = {"experiment": exp, "setup": label, "dataset": ds, "runs": len(xs), "scored": len(vals)}
        if "scorable_rounds" in rows[0]:
            row["runs_with_a_scorable_round"] = sum(1 for r in rows if r["scorable_rounds"])
        if ds == "C":
            row |= {"metric": "rule groups met of 7", "all_rules_met": sum(1 for v in vals if v == 7)}
            if "best_round_score" in rows[0]:
                row["all_rules_met_best_round"] = sum(1 for r in rows if r["best_round_score"] == 7)
        elif ds == "D" and "best_round_score" in rows[0]:
            row |= {"metric": "missing staff-hours per week (best known 10.9, random 20.7)"}
            b = [r["best_round_score"] for r in rows if r["best_round_score"] is not None]
            if b:
                row["mean_best_round"] = round(st.mean(b), 1)
        elif ds == "D":
            row |= {"metric": "missing staff-hours per week (best known 10.9, random 20.7)"}
        else:
            row |= {"metric": "no checker", "staff08_scheduled": sum(1 for r in rows if r.get("staff08")),
                    "with_a_table": sum(1 for r in rows if r.get("empty") is not None),
                    "with_empty_cells": sum(1 for r in rows if r.get("empty"))}
        if vals:
            row |= {"mean": round(st.mean(vals), 1), "min": min(vals), "max": max(vals)}
        mins = [r.get("minutes") or (r.get("seconds") or 0) / 60 for r in rows]
        row |= {"mean_minutes": round(st.mean(mins), 1),
                "mean_tokens_in": round(st.mean(r["input_tokens"] for r in rows)), "mean_tokens_out": round(st.mean(r["output_tokens"] for r in rows))}
        costs = [r["cost_eur"] for r in rows if r.get("cost_eur") is not None]
        if costs:
            row["mean_cost_eur"] = round(st.mean(costs), 3)
        if "steps" in rows[0]:
            row |= {"mean_steps": round(st.mean(r["steps"] for r in rows), 1), "step_limit": sum(1 for r in rows if r["outcome"] == "step limit")}
        out.append(row)
    return out


def write(path, rows):
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    mas, rounds = analyse_mas()
    direct = analyse_direct()
    write(RES / "rerun_mas_runs.csv", mas)
    write(RES / "rerun_mas_rounds.csv", rounds)
    write(RES / "rerun_direct_runs.csv", direct)
    summ = summarise(mas, direct)
    write(RES / "rerun_summary.csv", summ)
    print(f"{len(mas)} MAS runs, {len(rounds)} rounds, {len(direct)} direct runs")
    for r in summ:
        extra = ((f" all-rules {r['all_rules_met']}" if "all_rules_met" in r else "")
                 + (f" (best round {r['all_rules_met_best_round']})" if "all_rules_met_best_round" in r else "")
                 + (f" (best-round mean {r['mean_best_round']})" if "mean_best_round" in r else "")
                 + (f" tables {r['with_a_table']} Staff08 {r['staff08_scheduled']}" if "staff08_scheduled" in r else "")
                 + (f" runs-with-roster {r['runs_with_a_scorable_round']}" if "runs_with_a_scorable_round" in r else ""))
        print(f"{r['experiment']:<9} {r['setup']:<44} {r['dataset']}  n={r['runs']:<2} scored={r['scored']:<2} "
              f"mean={r.get('mean', '–')!s:<5} range={r.get('min', '–')}–{r.get('max', '–')}{extra}  "
              f"{r['mean_minutes']} min" + (f"  steps {r['mean_steps']} (limit {r['step_limit']})" if "mean_steps" in r else "")
              + (f"  €{r['mean_cost_eur']}" if "mean_cost_eur" in r else ""))
