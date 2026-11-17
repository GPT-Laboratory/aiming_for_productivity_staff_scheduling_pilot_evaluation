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
# Same output cap as the code model in the multi-agent runs (see mas_harness/run_headless.py).
LIMIT = ("Each of your replies is limited to {n} output tokens, counting any reasoning as well; anything "
         "beyond that is cut off. Use the tokens sparingly: keep the reasoning short and make sure the complete "
         "final csv block fits.")


def cap_param(n):
    """Output cap. OpenAI and Azure reasoning models accept only max_completion_tokens;
    OpenRouter documents max_tokens (and translates it), so keep that there."""
    return {"max_tokens" if "openrouter" in (os.getenv("OPENAI_API_BASE") or "") else "max_completion_tokens": n}


def load_skill(path):
    """A SKILL.md as the model would see it once loaded: frontmatter and HTML comments removed."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)
    return "\n\nThe following skill is loaded for this task:\n\n" + text.strip()


def sheets_as_text(xlsx):
    """Same serialisation the multi-agent system uses for uploaded Excel files."""
    parts = []
    for name, df in pd.read_excel(xlsx, sheet_name=None).items():
        parts.append(f"File: {xlsx.name}, Sheet: {name}\nData:\n{df.to_json(orient='records', force_ascii=False, indent=2)}")
    return "\n\n".join(parts)


def last_csv_block(text):
    blocks = re.findall(r"```(?:csv)?\s*\n(.*?)```", text, flags=re.S)
    return blocks[-1].strip() if blocks else None


# Task text file in the dataset folder (--prompt): prompt.txt, the pilot text, or prompt_revised.txt.
PROMPT_NAME = "prompt.txt"


# ----------------------------------------------------------------- case D
def d_task():
    xlsx = CASES / "D_synthetic" / "synthetic_daycare.xlsx"
    prompt = (CASES / "D_synthetic" / PROMPT_NAME).read_text(encoding="utf-8")
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
    prompt = (CASES / "C_reconstructed" / PROMPT_NAME).read_text(encoding="utf-8")
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
    ap.add_argument("--model", help="default: DIRECT_LLM_MODEL, else openai/gpt-6.1-terra-pro"); ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=16384); ap.add_argument("--tag", default="")
    ap.add_argument("--sim-user", action="store_true",
                    help="After each format-valid answer the simulated manager accepts it or asks for a revision (max 3).")
    ap.add_argument("--max-reviews", type=int, default=3)
    ap.add_argument("--prompt", default="prompt.txt", help="task text file in the dataset folder, e.g. prompt_revised.txt")
    ap.add_argument("--skill", help="SKILL.md appended to the system prompt, "
                    "e.g. direct_llm/skills/finnish-daycare-scheduling/SKILL.md")
    load_dotenv(REPO / ".env")
    ap.set_defaults(model=os.getenv("DIRECT_LLM_MODEL", "openai/gpt-6.1-terra-pro"))
    a = ap.parse_args()
    global PROMPT_NAME
    PROMPT_NAME = a.prompt
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_API_BASE"), timeout=900)
    task, validate, score = CASE[a.case]
    if a.sim_user:
        sys.path.insert(0, str(REPO / "mas_harness"))
        from sim_user.sim_user import SimManager
        case_dir = CASES / ("D_synthetic" if a.case == "D" else "C_reconstructed")
    for n in range(1, a.runs + 1):
        out = REPO / "runs" / f"{dt.datetime.now():%Y%m%d-%H%M%S}_direct{a.case}{a.tag}_r{n:02d}"
        out.mkdir(parents=True)
        system = SYSTEM + " " + LIMIT.format(n=a.max_tokens) + (load_skill(a.skill) if a.skill else "")
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": task()}]
        log = {"case": a.case, "model": a.model, "max_turns": a.max_turns, "max_tokens": a.max_tokens, "skill": a.skill, "prompt_file": a.prompt,
               "api_base": os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1 (default)", "turns": [], "started": dt.datetime.now().isoformat(timespec="seconds")}
        parsed, errs, t0 = None, ["no answer"], time.time()
        sim, reviews, fmt_fails, last_valid = None, 0, 0, None
        if a.sim_user:
            sim = SimManager(out / "sim_user.json", request=(case_dir / PROMPT_NAME).read_text(encoding="utf-8"),
                             files=[x.name for x in sorted(case_dir.glob("*.xlsx"))])
        turn_cap = a.max_turns + (a.max_reviews if sim else 0)
        for turn in range(1, turn_cap + 1):          # hard cap prevents endless revision loops
            try:
                r = client.chat.completions.create(model=a.model, messages=msgs, **cap_param(a.max_tokens))
                text = r.choices[0].message.content or ""
                finish = r.choices[0].finish_reason
                usage = r.usage.model_dump() if r.usage else {}
            except Exception as exc:
                log["turns"].append({"turn": turn, "api_error": repr(exc)[:300]}); break
            (out / f"answer_turn{turn}.md").write_text(text, encoding="utf-8")
            parsed, errs = validate(text)
            log["turns"].append({"turn": turn, "validity_errors": errs, "answer_chars": len(text), "finish_reason": finish,
                                 "completion_tokens": usage.get("completion_tokens"), "prompt_tokens": usage.get("prompt_tokens")})
            print(f"[direct {a.case} r{n}] turn {turn}: {len(errs)} validity errors"
                  + (" (cut off at the output cap)" if finish == "length" else ""), flush=True)
            if not errs:
                last_valid = parsed
                if sim is None or reviews >= a.max_reviews:
                    break
                v = sim.ask("the assistant's answer", text, "Is this what you need?",
                            {"revise": "ask for changes; type what should change",
                             "accept": "use this schedule"})
                log["turns"][-1]["manager"] = v["decision"]
                if v["decision"] != "revise":
                    break
                reviews += 1
                msgs += [{"role": "assistant", "content": text}, {"role": "user", "content": v["message"] or "Please improve it."}]
                continue
            fmt_fails += 1
            if fmt_fails >= a.max_turns:
                break
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "A basic format check found these problems:\n- " + "\n- ".join(errs) +
                      "\nPlease correct the schedule and give the complete final csv block again."}]
        if errs and last_valid is not None:   # a revision broke the format: keep the last valid schedule
            parsed, errs = last_valid, []
            log["used_earlier_valid_answer"] = True
        log.update(valid=not errs, n_turns=len(log["turns"]), duration_s=round(time.time() - t0, 1),
                   manager_reviews=reviews if sim else None)
        if parsed is not None and (not errs or a.case == "D"):
            try:
                log["checker"] = score(parsed, out)
            except Exception as exc:
                log["checker_error"] = repr(exc)[:300]
        (out / "system.txt").write_text(msgs[0]["content"], encoding="utf-8")
        (out / "prompt.txt").write_text(msgs[1]["content"], encoding="utf-8")
        (out / "result.json").write_text(json.dumps(log, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        c = log.get("checker", {})
        print(f"[direct {a.case} r{n}] valid={log['valid']} turns={log['n_turns']} {log['duration_s']}s | "
              f"{json.dumps(c.get('ratio') or c.get('rules_satisfied') or {}, ensure_ascii=False)}", flush=True)


if __name__ == "__main__":
    main()
