#!/usr/bin/env python3
"""Analyse the run–fix loops of recorded MAS runs: what failed, what the code fixer was shown,
and whether the fixer could have repaired it. Works from the recording alone; nothing is rerun
unless --replay is given.

For every failed "Start Docker Container" step the script records
  * what the MAS passed on to the code fixer (state.docker_output),
  * a static triage of the step's saved Dockerfile and compose.yaml: required ${VAR:?} variables
    in compose.yaml (the MAS sets none), and whether the run's input files are reachable inside
    the container (the MAS puts them in the project folder; they are reachable only if the
    Dockerfile copies them or compose mounts the project folder),
  * whether the program reports errors itself (argparse parser.error, print("Error ...") and
    sys.exit), which the MAS's output filter drops, leaving the fixer only an exit code,
  * the cause class, and whether it lies in a file the code fixer can edit,
  * whether Dockerfile / compose.yaml changed before the next run (the fixer cannot change them),
  * with --replay only: the real error, by rebuilding the step's saved files and running them the
    way the MAS does (docker compose build; up). Use it when the static triage leaves causes open.
Steps are grouped into fix cycles: a new program (Heuristic, Code Generator or New Loop agent),
its runs and fix attempts, ending in a successful run or in a new program.

Cause classes (from what the fixer saw, the static triage, or the replayed output):
  compose-variable   compose.yaml needs an environment variable the MAS never sets
  docker-build       the image build failed (Dockerfile, requirements)
  input-path         the program cannot find an input file (mount / working-directory layout)
  program            an error in the program itself
  unknown            only an exit code, and the static triage finds no configuration cause
"compose-variable", "docker-build" and "input-path" are fixed in Dockerfile / compose.yaml (or
in the file layout the MAS creates), which the code fixer neither sees nor edits; "input-path"
can sometimes be worked around in code.

Usage: mas_harness/fix_loop_analysis.py <run-dir> [<run-dir> ...] [--replay] [--out report.json]
--replay builds Docker images under separate compose project names, so it can run next to the MAS,
and writes its work files to <run>/fix_loop_replay/.
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

NEW_PROGRAM = ("heuristic_agent", "code_generator_agent", "new_loop_agent")
DOCKER_FILES = ("Dockerfile", "compose.yaml")
FIXER_CAN_EDIT = {"program": "yes", "input-path": "partly", "compose-variable": "no", "docker-build": "partly",
                  "unknown": "?"}


def visible_error(docker_output: str) -> str:
    """The informative part of what the fixer saw: drop the MAS's own header and exit-code lines."""
    lines = [re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", l).strip() for l in docker_output.splitlines()]
    keep = [l for l in lines if l and not l.startswith(("Docker container execution failed", "Docker image build failed"))
            and not re.search(r"exited with code \d+$", l)]
    return "\n".join(keep)


def classify(text: str, inputs) -> str:
    t = text or ""
    if re.search(r"required variable \w+ is missing|error while interpolating", t):
        return "compose-variable"
    if re.search(r"failed to solve|Docker image build failed\n\S|ERROR \[|pip.*(No matching distribution|error)", t):
        return "docker-build"
    names = [re.escape(n) for n in inputs]
    if names and re.search(r"(No such file or directory|not found|does not exist|FileNotFoundError).{0,200}(" + "|".join(names) + ")", t, re.S | re.I):
        return "input-path"
    if re.search(r"(Error|error|Exception|Traceback)", t):
        return "program"
    return "unknown"


def static_triage(step: Path, inputs) -> dict:
    """Configuration problems that can be read off the saved Docker files, without running anything."""
    compose = (step / "compose.yaml").read_text(errors="replace") if (step / "compose.yaml").exists() else ""
    docker = (step / "Dockerfile").read_text(errors="replace") if (step / "Dockerfile").exists() else ""
    code = (step / "generated.py").read_text(errors="replace") if (step / "generated.py").exists() else ""
    strip = lambda t: "\n".join(l.split("#", 1)[0] for l in t.splitlines())
    compose_c, docker_c = strip(compose), strip(docker)
    required = sorted(set(re.findall(r"\$\{(\w+):\?", compose_c)))
    copies = re.findall(r"^\s*(?:COPY|ADD)\s+(?:--\S+\s+)*(.+)$", docker_c, re.M)
    copied = " ".join(c.rsplit(None, 1)[0] if len(c.split()) > 1 else c for c in copies)
    mounts = re.findall(r"^\s*-\s*['\"]?(\.{1,2}[^:'\"]*):", compose_c, re.M)
    project_mounted = any(m.rstrip("/") in (".", "") for m in mounts)
    copied_all = bool(re.search(r"(^|\s)\.(/)?(\s|$)|\*", copied))
    reachable = {f: project_mounted or copied_all or f in copied for f in inputs}
    reports_itself = bool(re.search(r"parser\.error\(|print\(\s*f?['\"]\s*Error|sys\.exit\(\s*[1-9]|raise SystemExit\(\s*[1-9]", code))
    return {"compose_required_vars": required, "volume_mounts": mounts, "inputs_reachable_in_container": reachable,
            "program_reports_errors_itself": reports_itself}


def last_error_line(text: str) -> str:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    errs = [l for l in lines if re.search(r"(Error|error|Exception|required variable|failed)", l)
            and "exited with code" not in l and not l.startswith(("Container ", "Network "))]
    return (errs[-1] if errs else (lines[-1] if lines else ""))[:220]


def replay(step: Path, inputs, work: Path, timeout: int) -> str:
    w = work / step.name
    shutil.rmtree(w, ignore_errors=True); w.mkdir(parents=True)
    for f in ("generated.py", "requirements.txt", *DOCKER_FILES):
        if (step / f).exists():
            shutil.copy2(step / f, w / f)
    for f in inputs:
        shutil.copy2(f, w / f.name)
    proj = re.sub(r"[^a-z0-9]", "", f"fla{step.parent.parent.name[-12:]}{step.name[:2]}".lower())
    b = subprocess.run(["docker", "compose", "-p", proj, "build"], cwd=w, capture_output=True, text=True)
    text = b.stdout + b.stderr
    if b.returncode == 0:
        try:
            u = subprocess.run(["docker", "compose", "-p", proj, "up", "--abort-on-container-exit", "--no-log-prefix"],
                               cwd=w, capture_output=True, text=True, timeout=timeout)
            text += "\n" + u.stdout + u.stderr
        except subprocess.TimeoutExpired:
            text += "\n[replay timeout]"
    else:
        text = "Docker image build failed\n" + text
    subprocess.run(["docker", "compose", "-p", proj, "down", "--rmi", "local"], cwd=w, capture_output=True)
    # the container may have written root-owned files; make them removable
    subprocess.run(["docker", "run", "--rm", "-v", f"{w.resolve()}:/w", "python:3.9-slim", "chmod", "-R", "a+rwX", "/w"],
                   capture_output=True)
    (w / "replay_output.txt").write_text(text, encoding="utf-8")
    return text


def analyse(run: Path, do_replay: bool, timeout: int) -> dict:
    inputs = [f for f in (run / "inputs").iterdir() if f.name != "prompt.txt"]
    summary = json.load(open(run / "summary.json")) if (run / "summary.json").exists() else {}
    steps = sorted(p for p in (run / "steps").iterdir() if p.is_dir())
    cycles, cur, prev_run = [], None, None
    for s in steps:
        kind = s.name.split("_", 1)[1]
        if kind in NEW_PROGRAM:
            cur = {"program_step": s.name, "runs": [], "fix_attempts": 0, "ended": "open"}
            cycles.append(cur)
        elif kind == "code_fixer_agent" and cur:
            cur["fix_attempts"] += 1
        elif kind == "start_docker_container_agent" and cur:
            st = json.load(open(s / "state.json"))
            ok = st.get("proceed") != "fix"
            r = {"step": s.name, "ok": ok}
            if not ok:
                saw = st.get("docker_output") or ""
                vis = visible_error(saw)
                r["fixer_saw"] = last_error_line(vis) or "(only an exit code)"
                names = [f.name for f in inputs]
                tri = static_triage(s, names)
                r["static"] = tri
                real = replay(s, inputs, run / "fix_loop_replay", timeout) if do_replay else ""
                r["cause"] = classify(real if real else saw, names)
                r["cause_from"] = "replay" if real else "fixer's view"
                if not real and r["cause"] in ("unknown", "program", "input-path"):
                    if tri["compose_required_vars"]:
                        r["cause"], r["cause_from"] = "compose-variable", "static triage"
                    elif not all(tri["inputs_reachable_in_container"].values()):
                        r["cause"], r["cause_from"] = "input-path", "static triage"
                if do_replay:
                    r["real_error"] = last_error_line(real)
                    r["shown_to_fixer"] = bool(vis) and classify(saw, [f.name for f in inputs]) == r["cause"]
                r["fixer_can_edit_cause"] = FIXER_CAN_EDIT[r["cause"]]
            if prev_run is not None and cycles and any(x["step"] == prev_run.name for x in cur["runs"]):
                r["docker_files_changed_since_previous_run"] = any(
                    (s / f).exists() != (prev_run / f).exists() or
                    ((s / f).exists() and (s / f).read_bytes() != (prev_run / f).read_bytes()) for f in DOCKER_FILES)
            cur["runs"].append(r)
            prev_run = s
            if ok:
                cur["ended"] = "program ran"
    for c in cycles:
        if c["ended"] == "open":
            if not c["runs"]:
                c["ended"] = "run ended before this program ran"
            else:
                c["ended"] = "new program after failed fixes" if c is not cycles[-1] else "run ended (step limit / timeout)"
        fails = [r for r in c["runs"] if not r["ok"]]
        c["failed_runs"] = len(fails)
        c["causes"] = sorted({r["cause"] for r in fails})
        c["retries_with_same_docker_files"] = sum(1 for r in c["runs"] if r.get("docker_files_changed_since_previous_run") is False)
    fails = [r for c in cycles for r in c["runs"] if not r["ok"]]
    count = lambda pred: sum(1 for r in fails if pred(r))
    return {
        "run": run.name, "outcome": summary.get("outcome"), "error": str(summary.get("error") or "")[:80],
        "steps": summary.get("n_steps"), "replayed": do_replay,
        "executions": sum(len(c["runs"]) for c in cycles), "failed": len(fails),
        "by_cause": {k: count(lambda r, k=k: r["cause"] == k) for k in FIXER_CAN_EDIT if count(lambda r, k=k: r["cause"] == k)},
        "fixer_saw_only_exit_code": count(lambda r: r["fixer_saw"] == "(only an exit code)"),
        "of_which_program_reports_errors_itself": count(lambda r: r["fixer_saw"] == "(only an exit code)"
                                                        and r["static"]["program_reports_errors_itself"]),
        "cause_in_docker_files_or_layout": count(lambda r: r["cause"] in ("compose-variable", "docker-build", "input-path")),
        "cause_shown_and_fixable_in_code": count(lambda r: r.get("shown_to_fixer", r["fixer_saw"] != "(only an exit code)")
                                                 and r["fixer_can_edit_cause"] == "yes"),
        "retries_with_same_docker_files": sum(c["retries_with_same_docker_files"] for c in cycles),
        "cycles": cycles,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--replay", action="store_true", help="rebuild and rerun each failed step to recover the real error")
    ap.add_argument("--timeout", type=int, default=180, help="seconds per replayed run")
    ap.add_argument("--out", type=Path, help="write the full report as JSON")
    a = ap.parse_args()
    reports = []
    for run in a.runs:
        if not (run / "summary.json").exists():
            print(f"{run.name}: no summary.json (still running?), skipped", file=sys.stderr)
            continue
        rep = analyse(run, a.replay, a.timeout)
        reports.append(rep)
        print(f"\n== {rep['run']}: {rep['outcome']} {rep['error']} | steps {rep['steps']} | "
              f"failed {rep['failed']}/{rep['executions']} | causes {rep['by_cause']} | "
              f"fixer saw only an exit code {rep['fixer_saw_only_exit_code']} "
              f"(program reports errors itself in {rep['of_which_program_reports_errors_itself']}) | "
              f"cause in Docker files / layout {rep['cause_in_docker_files_or_layout']} | "
              f"shown and fixable in code {rep['cause_shown_and_fixable_in_code']} | "
              f"retries with unchanged Docker files {rep['retries_with_same_docker_files']}", flush=True)
        for c in rep["cycles"]:
            print(f"   {c['program_step']:<28} runs {len(c['runs'])}, failed {c['failed_runs']}, fixes {c['fix_attempts']}, "
                  f"causes {c['causes']} -> {c['ended']}")
            for r in c["runs"]:
                if not r["ok"]:
                    real = f" | real: {r['real_error'][:90]}" if r.get("real_error") else ""
                    how = "" if r["cause_from"] == "fixer's view" else f" [{r['cause_from']}]"
                    print(f"      {r['step'][:2]} {r['cause']:<16}{how} saw: {r['fixer_saw'][:70]}{real}")
    if a.out:
        a.out.write_text(json.dumps(reports, indent=1), encoding="utf-8")
    if len(reports) > 1:
        tot = lambda k: sum(r[k] for r in reports)
        causes = {}
        for r in reports:
            for k, v in r["by_cause"].items():
                causes[k] = causes.get(k, 0) + v
        print(f"\n== total over {len(reports)} runs: failed {tot('failed')}/{tot('executions')} | causes {causes} | "
              f"fixer saw only an exit code {tot('fixer_saw_only_exit_code')} | cause in Docker files / layout "
              f"{tot('cause_in_docker_files_or_layout')} | shown and fixable in code "
              f"{tot('cause_shown_and_fixable_in_code')} | retries with unchanged Docker files {tot('retries_with_same_docker_files')}")


if __name__ == "__main__":
    sys.exit(main())
