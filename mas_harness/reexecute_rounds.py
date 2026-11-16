#!/usr/bin/env python3
"""Re-execute the program behind every analysed round of a finished MAS run, keeping its output files.

Runs made before the harness kept output files lost what the generated programs wrote (for example
an Excel roster). For each Code Output Analyzer step, this takes the program of the preceding
successful Start Docker step (the snapshot of generated.py, requirements.txt and Dockerfile),
puts it in a fresh folder with the run's input files, and runs it the way the MAS does: the
generated Dockerfile, with the folder mounted at /app. Output goes to <run>/reexecuted/roundN/.

The programs are often randomised, so a re-execution can differ from the original run: compare
reexecuted/roundN/stdout.txt with the original output before relying on it.

Usage: mas_harness/reexecute_rounds.py <run-dir> [<run-dir> ...] [--timeout 900]
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

PROGRAM_FILES = ["generated.py", "requirements.txt", "Dockerfile"]


def rounds(run: Path):
    steps = sorted(p for p in (run / "steps").iterdir() if p.is_dir())
    last_run = None
    for s in steps:
        if s.name.endswith("start_docker_container_agent"):
            last_run = s
        elif s.name.endswith("code_output_analyzer_agent") and last_run is not None:
            yield s, last_run


def reexecute(run: Path, timeout: int):
    out = []
    for n, (analysed, program) in enumerate(rounds(run), 1):
        d = run / "reexecuted" / f"round{n}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for f in PROGRAM_FILES:
            shutil.copy2(program / f, d / f)
        inputs = [f for f in (run / "inputs").iterdir() if f.name != "prompt.txt"]
        for f in inputs:
            shutil.copy2(f, d / f.name)
        before = {p.name for p in d.iterdir()}
        tag = f"mas-reexec-{run.name.lower()}-r{n}"
        rec = {"round": n, "program_step": program.name, "analysed_step": analysed.name}
        b = subprocess.run(["docker", "build", "-q", "-t", tag, "."], cwd=d, capture_output=True, text=True)
        if b.returncode:
            rec["build_error"] = b.stderr[-2000:]
        else:
            try:
                # run as the invoking user so that the output files are not owned by root
                user = ["--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp"]
                r = subprocess.run(["docker", "run", "--rm", "--name", tag, *user, "-v", f"{d.resolve()}:/app", tag,
                                    "python", "/app/generated.py"], capture_output=True, text=True, timeout=timeout)
                rec["exit_code"] = r.returncode
                (d / "stdout.txt").write_text(r.stdout, encoding="utf-8")
                (d / "stderr.txt").write_text(r.stderr, encoding="utf-8")
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "kill", tag], capture_output=True)
                rec["timeout_s"] = timeout
            subprocess.run(["docker", "image", "rm", "-f", tag], capture_output=True)
        rec["new_files"] = sorted({p.name for p in d.iterdir()} - before - {"stdout.txt", "stderr.txt"})
        (d / "reexecution.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        out.append(rec)
        print(f"{run.name} round {n}: exit={rec.get('exit_code', rec.get('timeout_s') and 'timeout' or 'build-error')} "
              f"new files={rec['new_files']}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    for run in a.runs:
        reexecute(run, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
