#!/usr/bin/env python
"""One simulated-user trial of the MAS: a first chat and at most one retry.

The simulated manager answers the MAS's questions during each chat (run_headless.py --sim-user)
and, after the chat ends, decides whether to accept the result, give up, or retry once in a
new chat with a rewritten request and the same files. The persona's whole conversation is
kept in <trial dir>/sim_user.json.

Usage: mas_harness/sim_trial.py datasets/<dataset> <name> [--timeout 5400]
MAS_DIR selects the MAS checkout, as for run.sh.
Models for the MAS come from HEADLESS_LLM_MODEL / HEADLESS_LLM_CODE_MODEL as usual.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from sim_user.sim_user import SimManager, clip, visible_messages  # noqa: E402


def run_chat(prompt_file, files, name, state, timeout):
    cmd = [str(HERE / "run.sh"), "--prompt-file", str(prompt_file), "--name", name,
           "--timeout", str(timeout), "--sim-user", str(state)]
    for f in files:
        cmd += ["--file", str(f)]
    run_dir = None
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=ROOT) as p:
        for line in p.stdout:
            if line.startswith("[headless]") and re.match(r"\[headless\] (<<<|outcome|run directory|decision|free-text)", line):
                print(line.rstrip()[:220], flush=True)
            m = re.match(r"\[headless\] run directory: (.+)", line)
            if m:
                run_dir = Path(m.group(1).strip())
    return run_dir


def end_of_chat_view(run_dir):
    s = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    msgs = s.get("messages", [])
    tail = visible_messages(msgs[s.get("sim_shown_upto", 0):])  # what the manager has not seen yet
    status = {"completed": "The chat ended normally.",
              "timeout": "The tool stopped responding and the chat was closed."}.get(
        s["outcome"], "The tool stopped with an error: " + str(s.get("error"))[:300])
    text = f"{status}\n\nLast things the tool showed:\n{clip(tail, 12000, 3000)}"
    if s.get("last_program_output"):
        text += "\n\n=== Last output printed by the tool's program ===\n" + clip(s["last_program_output"], 10000, 3000)
    return s, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir")
    ap.add_argument("name")
    ap.add_argument("--timeout", type=int, default=5400)
    a = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    case = Path(a.case_dir).resolve()
    files = sorted(case.glob("*.xlsx"))
    request = (case / "prompt.txt").read_text(encoding="utf-8")

    tdir = ROOT / "runs" / f"{dt.datetime.now():%Y%m%d-%H%M%S}_{a.name}_trial"
    tdir.mkdir(parents=True)
    state = tdir / "sim_user.json"
    sim = SimManager(state, request=request, files=[f.name for f in files])
    trial = {"case": case.name, "name": a.name, "models": {k: os.getenv(k) for k in ("HEADLESS_LLM_MODEL", "HEADLESS_LLM_CODE_MODEL")},
             "sim_model": sim.model, "mas_dir": os.getenv("MAS_DIR", str(ROOT / "mas2024")), "chats": []}

    prompt_file = case / "prompt.txt"
    for attempt in (1, 2):
        run_dir = run_chat(prompt_file, files, f"{a.name}_c{attempt}", state, a.timeout)
        if run_dir is None or not (run_dir / "summary.json").exists():
            trial["chats"].append({"chat": attempt, "run_dir": str(run_dir), "error": "no summary"})
            break
        s, view = end_of_chat_view(run_dir)
        sim = SimManager(state)  # reload: the chat process appended to the conversation
        options = {"accept": "use this result", "give_up": "the result is not usable and you stop here"}
        if attempt == 1:
            options = {"accept": "use this result",
                       "retry": "open a new chat once more; type the whole new request (the same files are attached again)",
                       "give_up": "the result is not usable and you do not try again"}
        verdict = sim.ask("the chat has ended", view, "What do you do now?", options)
        trial["chats"].append({"chat": attempt, "run_dir": str(run_dir), "outcome": s["outcome"],
                               "n_steps": s.get("n_steps"), "verdict": verdict["decision"]})
        print(f"[trial] chat {attempt}: {s['outcome']} -> manager: {verdict['decision']}", flush=True)
        if verdict["decision"] != "retry":
            break
        prompt_file = tdir / "request_chat2.txt"
        prompt_file.write_text(verdict["message"].strip() or request, encoding="utf-8")

    trial["final_chat"] = trial["chats"][-1]
    (tdir / "trial.json").write_text(json.dumps(trial, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[trial] done: {tdir}", flush=True)


if __name__ == "__main__":
    main()
