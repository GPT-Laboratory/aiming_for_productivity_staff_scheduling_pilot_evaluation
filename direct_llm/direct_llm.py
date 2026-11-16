#!/usr/bin/env python
"""Direct-LLM experiment: no multi-agent system, no code execution, no tools.

The model gets the task description and the data and must reason its way to a schedule.
A minimal loop gives it feedback from a RUDIMENTARY structural validity check only
(parseable, known names, no double assignments ...), at most MAX_TURNS answers. The rule
checkers (synthetic_daycare.score / check_schedule.check) are used afterwards to evaluate the
outcome; their results are never shown to the model.

Usage: direct_llm.py <case: D|C> <n-runs> [--model openai/gpt-6.1-terra-pro] [--max-turns 4]
"""
import argparse, csv, datetime as dt, io, json, os, re, sys, time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

REPO = Path(__file__).resolve().parent.parent
CASES = REPO / "datasets"
sys.path.insert(0, str(CASES / "D_synthetic"))
sys.path.insert(0, str(CASES / "C_reconstructed"))
import synthetic_daycare as ln   # noqa: E402
import check_schedule as cs      # noqa: E402

SYSTEM = ("You are solving a staff scheduling task by reasoning alone. You have no tools: you cannot run code, "
          "call a solver or look anything up. Do not write a program. Think the problem through carefully and "
          "then give the finished schedule yourself.")


def sheets_as_text(xlsx):
    """Same serialisation the multi-agent system uses for uploaded Excel files."""
    parts = []
    for name, df in pd.read_excel(xlsx, sheet_name=None).items():
        parts.append(f"File: {xlsx.name}, Sheet: {name}\nData:\n{df.to_json(orient='records', force_ascii=False, indent=2)}")
    return "\n\n".join(parts)


def last_csv_block(text):
    blocks = re.findall(r"```(?:csv)?\s*\n(.*?)```", text, flags=re.S)
    return blocks[-1].strip() if blocks else None


# ----------------------------------------------------------------- case D
def d_task():
    xlsx = CASES / "D_synthetic" / "synthetic_daycare.xlsx"
    prompt = (CASES / "D_synthetic" / "prompt.txt").read_text(encoding="utf-8")
    fmt = ("\n\nProduce the schedule for weeks 18, 19, 20 and 21.\n"
           "Answer format: after your reasoning, give the final schedule as ONE fenced csv block with the header\n"
           "Vko," + ",".join(ln.SLOT_NAMES) + "\nand one row per week. Each cell holds one staff name exactly as in the "
           "Staff sheet, 'loma', or is empty. A person placed in a shift column works that shift on every day of that "
           "week on which they are available (their working days minus vacation and closed days).")
    return prompt + fmt + "\n\nAttached data:\n" + sheets_as_text(xlsx)


def d_validate(text):
    block = last_csv_block(text)
    if not block:
        return None, ["No fenced csv block found in the answer."]
    rows = list(csv.reader(io.StringIO(block)))
    staff = {s["Name"] for s in ln.load()[1]}
    errs, table = [], {}
    for r in rows[1:]:
        if not r or not r[0].strip().isdigit():
            continue
        cells = [c.strip() for c in r[1:]]
        if len(cells) != 11:
            errs.append(f"Week {r[0]}: expected 11 shift columns, found {len(cells)}.")
        cells = (cells + [""] * 11)[:11]
        names = [c for c in cells if c and c.lower() != "loma"]
        errs += [f"Week {r[0]}: unknown name '{n}'." for n in names if n not in staff]
        errs += [f"Week {r[0]}: '{n}' appears in more than one shift." for n in sorted(set(names)) if names.count(n) > 1]
        table[int(r[0])] = cells
    missing = [w for w in ln.NEW_WEEKS if w not in table]
    if missing:
        errs.append(f"Missing weeks: {missing}.")
    table = {w: c for w, c in table.items() if w in ln.NEW_WEEKS}
    return table, errs


def d_score(table, out):
    ln.write_table(table, out / "final_table.csv")
    return ln.score(table)


# ----------------------------------------------------------------- case C
def c_task():
    xlsx = CASES / "C_reconstructed" / "daycare_structure_example.xlsx"
    prompt = (CASES / "C_reconstructed" / "prompt.txt").read_text(encoding="utf-8")
    fmt = ("\n\nAnswer format: after your reasoning, give the final schedule as ONE fenced csv block with the header\n"
           "employee,day,start,end,group\nand one row per employee per working day (day = Mon..Fri, times HH:MM, "
           "group = the group the employee works in during that shift).")
    return prompt + fmt + "\n\nAttached data:\n" + sheets_as_text(xlsx)


def c_validate(text):
    block = last_csv_block(text)
    if not block:
        return None, ["No fenced csv block found in the answer."]
    staff = set(pd.read_excel(CASES / "C_reconstructed" / "daycare_structure_example.xlsx", sheet_name="Staff")["Employee ID"])
    errs, seen, rows = [], set(), []
    for i, r in enumerate(csv.DictReader(io.StringIO(block)), 2):
        try:
            e, d, g = r["employee"].strip(), r["day"].strip()[:3].title(), r["group"].strip()
            s, en = cs.mins(r["start"]), cs.mins(r["end"])
        except Exception:
            errs.append(f"Line {i}: cannot parse."); continue
        if e not in staff: errs.append(f"Line {i}: unknown employee '{e}'.")
        if d not in cs.DAYS: errs.append(f"Line {i}: unknown day '{d}'.")
        if g not in ("Nuput", "Tenavat", "Eskarit"): errs.append(f"Line {i}: unknown group '{g}'.")
        if en <= s: errs.append(f"Line {i}: end is not after start.")
        if (e, d) in seen: errs.append(f"Line {i}: '{e}' has more than one shift on {d}.")
        seen.add((e, d)); rows.append(r)
    if not rows:
        errs.append("The csv block has no schedule rows.")
    return block, errs[:25]


def c_score(block, out):
    p = out / "final_schedule.csv"
    p.write_text(block + "\n", encoding="utf-8")
    return cs.check(p, CASES / "C_reconstructed" / "daycare_structure_example.xlsx")


CASE = {"D": (d_task, d_validate, d_score), "C": (c_task, c_validate, c_score)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", choices=CASE); ap.add_argument("runs", type=int)
    ap.add_argument("--model", default="openai/gpt-6.1-terra-pro"); ap.add_argument("--max-turns", type=int, default=4)
    a = ap.parse_args()
    load_dotenv(REPO / ".env")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_API_BASE"), timeout=900)
    task, validate, score = CASE[a.case]
    for n in range(1, a.runs + 1):
        out = REPO / "runs" / f"{dt.datetime.now():%Y%m%d-%H%M%S}_direct{a.case}_r{n:02d}"
        out.mkdir(parents=True)
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task()}]
        log = {"case": a.case, "model": a.model, "max_turns": a.max_turns, "turns": [], "started": dt.datetime.now().isoformat(timespec="seconds")}
        parsed, errs, t0 = None, ["no answer"], time.time()
        for turn in range(1, a.max_turns + 1):          # hard cap prevents endless revision loops
            try:
                r = client.chat.completions.create(model=a.model, messages=msgs, max_tokens=30000)
                text = r.choices[0].message.content or ""
                usage = r.usage.model_dump() if r.usage else {}
            except Exception as exc:
                log["turns"].append({"turn": turn, "api_error": repr(exc)[:300]}); break
            (out / f"answer_turn{turn}.md").write_text(text, encoding="utf-8")
            parsed, errs = validate(text)
            log["turns"].append({"turn": turn, "validity_errors": errs, "answer_chars": len(text),
                                 "completion_tokens": usage.get("completion_tokens"), "prompt_tokens": usage.get("prompt_tokens")})
            print(f"[direct {a.case} r{n}] turn {turn}: {len(errs)} validity errors", flush=True)
            if not errs:
                break
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "A basic format check found these problems:\n- " + "\n- ".join(errs) +
                      "\nPlease correct the schedule and give the complete final csv block again."}]
        log.update(valid=not errs, n_turns=len(log["turns"]), duration_s=round(time.time() - t0, 1))
        if parsed is not None and (not errs or a.case == "D"):
            try:
                log["checker"] = score(parsed, out)
            except Exception as exc:
                log["checker_error"] = repr(exc)[:300]
        (out / "prompt.txt").write_text(msgs[1]["content"], encoding="utf-8")
        (out / "result.json").write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        c = log.get("checker", {})
        print(f"[direct {a.case} r{n}] valid={log['valid']} turns={log['n_turns']} {log['duration_s']}s | "
              f"{json.dumps(c.get('ratio') or c.get('rules_satisfied') or {}, ensure_ascii=False)}", flush=True)


if __name__ == "__main__":
    main()
