#!/usr/bin/env python3
"""Extract the roster a MAS run delivered into schema-following JSON with an LLM, then score it.

The programs the MAS writes deliver their rosters in many forms: Excel workbooks with differently
named sheets and columns, printed tables, JSON files, or only a summary. This script gives an LLM
(by default gpt-6.1-terra) what one round's program printed and every file it wrote (workbooks as
CSV text per sheet), and asks for the roster in one fixed JSON schema. The LLM is told to copy
values only: no computing, adding up or guessing, and to leave anything that is not shown empty.
The JSON is then converted to the checkers' input and scored, so every run gets a machine-checkable
result in the same way.

Formats: "weekly_rotation" (datasets A, B, D: one row per week, a name per shift slot) and
"daily_shifts" (dataset C: employee, day, start, end, group). "none" if no roster is shown.

Writes <run>/llm_extract/round<N>.json (the LLM's JSON plus the score) and, with --summary,
a CSV of all processed runs.

Usage:
  UV_ENV_FILE=.env.azure uv run ... mas_harness/llm_extract.py <run-dir> [...] [--all-rounds]
        [--model gpt-6.1-terra] [--summary results/rerun_llm_extract.csv]
"""
import argparse, csv, io, json, os, re, sys, tempfile, time
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "datasets" / "C_reconstructed")); import check_schedule as cs
sys.path.insert(0, str(REPO / "datasets" / "D_synthetic")); import synthetic_daycare as sd, score_daily_detail as sdd
CX = REPO / "datasets" / "C_reconstructed" / "daycare_structure_example.xlsx"
MAX_ROWS, MAX_TEXT = 300, 20000
SLOT_LABELS = [s[0] for s in sd.SLOTS]
CURRENT = {"Staff01", "Staff02", "Staff03", "Staff04", "Staff05", "Staff06", "Staff07", "Staff09", "Staff10", "Staff11", "Assistant"}

STR_OR_NULL = {"type": ["string", "null"]}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["roster_found", "format", "source", "weekly_rotation", "daily_shifts", "program_report", "notes"],
    "properties": {
        "roster_found": {"type": "boolean"},
        "format": {"type": "string", "enum": ["weekly_rotation", "daily_shifts", "none"]},
        "source": {"type": "string", "description": "file and sheet, or 'printed output', the roster was copied from"},
        "weekly_rotation": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["week", "day", "slots"],
            "properties": {"week": {"type": ["integer", "null"]},
                           "day": {"type": ["string", "null"], "description": "null if the row holds for the whole week; the weekday if the program gives a separate rotation per day"},
                           "slots": {"type": "array", "items": {
                               "type": "object", "additionalProperties": False, "required": ["slot", "employee"],
                               "properties": {"slot": {"type": "string"}, "employee": STR_OR_NULL}}}}}},
        "daily_shifts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["employee", "day", "start", "end", "group"],
            "properties": {"employee": {"type": "string"}, "day": STR_OR_NULL, "start": STR_OR_NULL,
                           "end": STR_OR_NULL, "group": STR_OR_NULL}}},
        "program_report": {"type": "object", "additionalProperties": False,
                           "required": ["status", "objective", "violations"],
                           "properties": {"status": STR_OR_NULL, "objective": STR_OR_NULL, "violations": STR_OR_NULL}},
        "notes": {"type": "string", "description": "anything ambiguous, missing or truncated; empty if nothing"},
    },
}

SYSTEM = """You extract data from the output of a staff-scheduling program into JSON. You copy; you do not solve, compute or judge.

Rules:
- Copy names, weeks, days, times and groups exactly as they appear. Do not normalise, translate or correct them.
- Do not compute, add up, convert or infer any value. Do not fill gaps from the input data, from other weeks or from common sense.
- If a value is not shown, leave it empty: null for a field, an empty array for a list. An empty cell in a table is null.
- If no roster is shown, set roster_found to false and format to "none".
- If several rosters are shown, take the one the program presents as its result (for example the final or updated one) and say which in "source"; mention the others in "notes".
- If the material is cut off (it says "[truncated]"), copy what is shown and say so in "notes".
- program_report: copy the program's own statements about its status, objective value and violations, briefly and verbatim where possible; null if not stated."""


def task_hint(dataset):
    if dataset == "C":
        return ('The requested result is a one-week roster: for each employee and working day a start time, end time and group. '
                'Use format "daily_shifts", one item per shift piece as listed (an employee may have several pieces on one day).')
    return ('The requested result is a weekly rotation: one row per week, and for each shift slot the name of the person who works it. '
            f'The shift slots are: {", ".join(SLOT_LABELS)}. Use format "weekly_rotation" with one item per week and, in each, one '
            'item per slot (slot = the slot label as written in the output, employee = the name, or null if the cell is empty). '
            'Set "day" to null when a row holds for the whole week. If the program gives a separate rotation for each weekday '
            '(for example one sheet per day), add one item per week and day with "day" set to that weekday. '
            'The input history ends at week 17; only the newly scheduled weeks (18 and later) count, not reproduced history.')


def file_as_text(f):
    if f.suffix.lower() in (".xlsx", ".xls"):
        try:
            x = pd.ExcelFile(f)
        except Exception as e:
            return f"(unreadable workbook: {type(e).__name__})"
        parts = []
        for sh in x.sheet_names:
            df = x.parse(sh, header=None).fillna("")
            note = f" [truncated: first {MAX_ROWS} of {len(df)} rows]" if len(df) > MAX_ROWS else ""
            parts.append(f"--- sheet '{sh}' ({len(df)} rows){note} ---\n" + df.head(MAX_ROWS).to_csv(index=False, header=False))
        return "\n".join(parts)
    if f.suffix.lower() in (".csv", ".json", ".txt", ".md"):
        t = f.read_text(encoding="utf-8", errors="replace")
        return t[:MAX_TEXT] + (f"\n[truncated: first {MAX_TEXT} of {len(t)} characters]" if len(t) > MAX_TEXT else "")
    return f"(binary file, {f.stat().st_size} bytes, not shown)"


def rounds_of(run):
    steps = sorted(p for p in (run / "steps").iterdir() if p.is_dir())
    last, out = None, []
    for p in steps:
        if p.name.endswith("start_docker_container_agent"):
            last = p
        elif p.name.endswith("code_output_analyzer_agent") and last is not None:
            out.append(last)
    pick = None
    fr = next((p for p in steps if p.name.endswith("final_report_agent")), None)
    if fr and (fr / "stream.txt").exists():
        m = re.search(r'"index_of_optimization"\s*:\s*(\d+)', (fr / "stream.txt").read_text())
        pick = int(m.group(1)) if m else None
    return out, pick


def material(step):
    st = json.loads((step / "state.json").read_text())
    printed = st.get("docker_full_log") or st.get("docker_output") or ""
    parts = [f"=== What the program printed (end of the log) ===\n{printed[-MAX_TEXT:]}"]
    for f in sorted((step / "outputs").rglob("*")) if (step / "outputs").exists() else []:
        if f.is_file():
            parts.append(f"=== File written by the program: {f.relative_to(step / 'outputs')} ===\n{file_as_text(f)}")
    if len(parts) == 1:
        parts.append("=== The program wrote no files ===")
    return "\n\n".join(parts)


def score(dataset, js):
    """Score the extracted roster with the dataset's checker. -> dict"""
    if js["format"] == "daily_shifts" and js["daily_shifts"]:
        rows = [r for r in js["daily_shifts"] if all(r.get(k) for k in ("employee", "day", "start", "end", "group"))]
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        w = csv.writer(tmp); w.writerow(["employee", "day", "start", "end", "group"])
        for r in rows:
            w.writerow([r["employee"], str(r["day"])[:3].title(), r["start"], r["end"], r["group"]])
        tmp.close()
        if dataset != "C":
            return {"score": None, "note": "daily shifts for a weekly-rotation dataset"}
        r = cs.check(tmp.name, CX)
        return {"score": sum(r["rules_satisfied"].values()), "failed": " ".join(k for k, v in r["rules_satisfied"].items() if not v),
                "understaffed_min": r["R2_R6_ratio"]["group_minutes_understaffed"], "rows_used": len(rows),
                "rows_incomplete": len(js["daily_shifts"]) - len(rows)}
    if js["format"] == "weekly_rotation" and js["weekly_rotation"] and any(w.get("day") for w in js["weekly_rotation"]):
        daily = {}
        for wk in js["weekly_rotation"]:
            if wk.get("week") is None or not wk.get("day") or not 18 <= int(wk["week"]) <= 21:
                continue
            by = {str(s["slot"]).strip(): (s.get("employee") or "").strip() for s in wk["slots"]}
            daily[(int(wk["week"]), str(wk["day"]).strip()[:3].title())] = [(i, by[lab]) for i, lab in enumerate(SLOT_LABELS) if by.get(lab)]
        if not daily:
            return {"score": None, "note": "no weeks 18-21"}
        names = {n for v in daily.values() for _, n in v}
        out = {"weeks": len({w for w, _ in daily}), "empty": sum(11 - len(v) for v in daily.values()), "staff08": "Staff08" in names,
               "unknown_names": " ".join(sorted(names - CURRENT - {"Staff08", "loma"})), "form": "per weekday"}
        if dataset == "D":
            dd = sdd.score_daily(daily)
            out |= {"score": dd["ratio"]["missing_staff_hours_per_week"], "conflicts": dd["assigned_on_day_off"]}
        else:
            out["score"] = None
        return out
    if js["format"] == "weekly_rotation" and js["weekly_rotation"]:
        table = {}
        for wk in js["weekly_rotation"]:
            if wk.get("week") is None:
                continue
            by = {str(s["slot"]).strip(): (s.get("employee") or "").strip() for s in wk["slots"]}
            table[int(wk["week"])] = [by.get(lab, "") for lab in SLOT_LABELS]
        table = {w: v for w, v in table.items() if 18 <= w <= 21}
        if not table:
            return {"score": None, "note": "no weeks 18-21"}
        names = {c for v in table.values() for c in v if c}
        out = {"weeks": len(table), "empty": sum(1 for v in table.values() for c in v if not c),
               "staff08": "Staff08" in names, "unknown_names": " ".join(sorted(names - CURRENT - {"Staff08", "loma"}))}
        if dataset == "D":
            r = sd.score(table)
            out |= {"score": r["ratio"]["missing_staff_hours_per_week"], "conflicts": r["vacation_or_offday_conflicts"],
                    "repeats": r["rotation"]["same_slot_two_weeks_running"]}
        else:
            out["score"] = None
        return out
    return {"score": None, "note": "no roster extracted"}


def extract(client, model, run, step, rnd, dataset):
    prompt = (f"{task_hint(dataset)}\n\nBelow is everything the program printed and wrote in this round. "
              f"Extract the roster into the JSON schema.\n\n{material(step)}")
    t0 = time.time()
    r = client.chat.completions.create(
        model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        response_format={"type": "json_schema", "json_schema": {"name": "roster", "strict": True, "schema": SCHEMA}},
        **{"max_tokens" if "openrouter" in (os.getenv("OPENAI_API_BASE") or "") else "max_completion_tokens": 16384})
    js = json.loads(r.choices[0].message.content)
    u = r.usage.model_dump() if r.usage else {}
    usage = {"model": r.model, "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
             "cached_prompt_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
             "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
             "seconds": round(time.time() - t0, 1), "finish_reason": r.choices[0].finish_reason}
    sc = score(dataset, js)
    out = run / "llm_extract"; out.mkdir(exist_ok=True)
    (out / f"round{rnd}.json").write_text(json.dumps({"round": rnd, "program_step": step.name, "extraction": js,
                                                       "score": sc, "usage": usage}, indent=1, ensure_ascii=False), encoding="utf-8")
    return js, sc, usage


def dataset_of(run):
    m = re.search(r"_([ABCD])_", run.name)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--all-rounds", action="store_true", help="every analysed round, not only the one the final report picked")
    ap.add_argument("--model", default="gpt-6.1-terra")
    ap.add_argument("--summary", type=Path, help="write a CSV with one row per processed round")
    a = ap.parse_args()
    load_dotenv(REPO / ".env")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_API_BASE"), timeout=600)
    rows = []
    for run in a.runs:
        if not (run / "summary.json").exists():
            continue
        ds = dataset_of(run)
        rs, pick = rounds_of(run)
        chosen = list(enumerate(rs, 1)) if a.all_rounds else [(pick or len(rs), rs[(pick or len(rs)) - 1])] if rs else []
        for rnd, step in chosen:
            try:
                js, sc, us = extract(client, a.model, run, step, rnd, ds)
            except Exception as e:
                print(f"{run.name} round {rnd}: FAILED {type(e).__name__}: {str(e)[:200]}", flush=True)
                continue
            row = {"run": run.name, "dataset": ds, "round": rnd, "picked": rnd == pick, "roster_found": js["roster_found"],
                   "format": js["format"], "source": js["source"], **{k: v for k, v in sc.items()},
                   "program_status": js["program_report"]["status"], "notes": js["notes"][:300],
                   "input_tokens": us["prompt_tokens"], "output_tokens": us["completion_tokens"], "seconds": us["seconds"]}
            rows.append(row)
            print(f"{run.name} round {rnd}{' (picked)' if rnd == pick else ''}: {js['format']} from {js['source'][:60]!r} -> "
                  f"score {sc.get('score')} {sc.get('failed') or sc.get('note') or ''} | {us['prompt_tokens']} in, "
                  f"{us['completion_tokens']} out, {us['seconds']} s", flush=True)
    if a.summary and rows:
        keys = []
        for r in rows:
            keys += [k for k in r if k not in keys]
        with open(a.summary, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
