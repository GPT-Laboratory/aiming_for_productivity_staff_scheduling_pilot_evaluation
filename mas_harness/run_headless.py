#!/usr/bin/env python
"""Headless runner for the GPT-Lab multi-agent system (evaluation harness).

The multi-agent system is not part of this repository. Point MAS_DIR at a checkout of it
(default: ./mas2024). The harness does not modify its code (main.py, agents/, prompts/, schemas.py).
Instead a stand-in `chainlit` module is injected before the pipeline is
imported, so that:

  * `@cl.step`, `cl.context.current_step`, `cl.Message` are recorded to disk
    instead of being rendered in the web UI;
  * the two human decisions (`cl.AskActionMessage`) are answered by a fixed,
    logged policy:
       - Problem Analyzer  "Sounds good, proceed?"       -> continue
       - Output Analyzer   "new optimization round?"     -> continue for the
         first N rounds (--optimization-rounds), then done;
  * the original `main.main(message)` handler is called with a fake message, so
    file ingestion, prompt-file formatting and the LangGraph workflow are the
    original code paths.

Every run writes a self-contained directory under runs/.

Usage (MAS_DIR = checkout of the multi-agent system, default ./mas2024):
  mas_harness/run.sh \
      --prompt-file datasets/D_synthetic/prompt.txt \
      --file datasets/D_synthetic/synthetic_daycare.xlsx \
      --optimization-rounds 2 --name D_mas
"""
import argparse
import asyncio
import contextvars
import datetime as dt
import functools
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = Path(os.environ.get("MAS_DIR", ROOT / "mas2024")).resolve()   # the multi-agent system checkout
GENERATED = REPO / "generated"
SNAPSHOT_FILES = ["generated.py", "requirements.txt", "Dockerfile", "compose.yaml"]


def to_jsonable(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, (tuple, list)):
        return "\n\n".join(str(v) for v in value)
    return str(value)


class Recorder:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.t0 = time.time()
        self.step_count = 0
        self.steps = []
        self.messages = []
        self.decisions = []
        self.last_program_output = ""
        self.shown_upto = 0  # messages already shown to the simulated user
        (run_dir / "steps").mkdir(parents=True, exist_ok=True)
        self._events = open(run_dir / "events.jsonl", "a", encoding="utf-8")

    def event(self, kind, **payload):
        rec = {"t": round(time.time() - self.t0, 3), "event": kind, **payload}
        self._events.write(json.dumps(rec, ensure_ascii=False, default=to_jsonable) + "\n")
        self._events.flush()

    def step_start(self, name):
        self.step_count += 1
        self.event("step_start", index=self.step_count, name=name)
        print(f"\n[headless] >>> step {self.step_count}: {name}", flush=True)
        return self.step_count

    def step_end(self, index, step, duration, state, error):
        slug = step.name.lower().replace(" ", "_")
        d = self.run_dir / "steps" / f"{index:02d}_{slug}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "input.txt").write_text(as_text(step.input), encoding="utf-8")
        (d / "output.txt").write_text(as_text(step.output), encoding="utf-8")
        (d / "stream.txt").write_text("".join(step.tokens), encoding="utf-8")
        if isinstance(state, dict):
            self.last_state = state
            (d / "state.json").write_text(
                json.dumps(state, ensure_ascii=False, indent=2, default=to_jsonable),
                encoding="utf-8",
            )
        for fname in SNAPSHOT_FILES:
            src = GENERATED / fname
            if src.exists():
                shutil.copy2(src, d / fname)
        if step.name == "Start Docker Container Agent" and "Attaching to" in "".join(step.tokens):
            from sim_user.sim_user import program_output
            self.last_program_output = program_output("".join(step.tokens))
        proceed = state.get("proceed") if isinstance(state, dict) else None
        info = {
            "index": index,
            "name": step.name,
            "duration_s": round(duration, 2),
            "proceed_after": proceed,
            "error": error,
        }
        self.steps.append(info)
        self.event("step_end", **info)
        print(
            f"[headless] <<< step {index}: {step.name} "
            f"({duration:.1f}s, proceed={proceed}, error={error})",
            flush=True,
        )


def install_chainlit_shim(rec: Recorder, optimization_rounds: int, sim=None):
    """Register a minimal fake `chainlit` module in sys.modules.

    With `sim` (a SimManager) the user's questions are answered by the simulated manager
    instead of the fixed policy."""
    current = contextvars.ContextVar("current_step", default=None)
    counters = {"continue_given": 0}
    pending = {"message": ""}

    def new_messages():
        from sim_user.sim_user import visible_messages
        text = visible_messages(rec.messages[rec.shown_upto:])
        rec.shown_upto = len(rec.messages)
        return text

    async def ask_sim(values, question):
        from sim_user.sim_user import clip
        if "done" in values:
            shown = new_messages()
            if rec.last_program_output:
                shown += "\n\n=== Output printed by the tool's program ===\n" + clip(rec.last_program_output)
            options = {"continue": "run another round; you may type what it should take into account",
                       "done": "this is enough; the tool writes its final report and the chat ends"}
            where = "after an optimisation round"
        else:
            shown = new_messages()
            options = {"new": "ask for a new plan; type what should be different",
                       "cancel": "stop this chat",
                       "continue": "go ahead with this plan"}
            where = "the tool's plan"
        ans = await asyncio.to_thread(sim.ask, where, shown, question, options)
        pending["message"] = ans.get("message", "")
        return ans["decision"]

    class Step:
        def __init__(self, name):
            self.name = name
            self.input = None
            self.output = None
            self.tokens = []

        async def stream_token(self, token):
            self.tokens.append(str(token))

    class Context:
        @property
        def current_step(self):
            return current.get()

    def step(name=None, **_kwargs):
        def decorator(fn):
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                s = Step(name or fn.__name__)
                token = current.set(s)
                index = rec.step_start(s.name)
                started = time.time()
                state, error = None, None
                try:
                    state = await fn(*args, **kwargs)
                    return state
                except BaseException as exc:  # recorded, then re-raised unchanged
                    error = repr(exc)
                    raise
                finally:
                    current.reset(token)
                    rec.step_end(index, s, time.time() - started, state, error)

            return wrapper

        return decorator

    class Message:
        def __init__(self, content="", **kwargs):
            self.content = content
            self.kwargs = kwargs

        async def send(self):
            s = current.get()
            entry = {"step": s.name if s else None, "content": as_text(self.content)}
            rec.messages.append(entry)
            rec.event("message", **entry)
            print(f"[headless] message: {entry['content'][:300]}", flush=True)
            return self

    class Action:
        def __init__(self, name=None, value=None, label=None, payload=None, **kwargs):
            # Chainlit 1.x passes value=..., Chainlit 2.x payload={"value": ...}
            self.name, self.label = name, label
            self.value = value if value is not None else (payload or {}).get("value", name)

    class AskActionMessage:
        def __init__(self, content="", actions=None, **kwargs):
            self.content = content
            self.actions = actions or []

        async def send(self):
            values = [a.value for a in self.actions]
            if sim is not None:
                choice = await ask_sim(values, self.content)
            elif "done" in values:  # output analyzer: another optimization round?
                if counters["continue_given"] < optimization_rounds:
                    counters["continue_given"] += 1
                    choice = "continue"
                else:
                    choice = "done"
            else:  # problem analyzer: accept the plan
                choice = "continue"
            s = current.get()
            entry = {
                "step": s.name if s else None,
                "question": self.content,
                "options": values,
                "choice": choice,
            }
            rec.decisions.append(entry)
            rec.event("decision", **entry)
            print(f"[headless] decision: {self.content!r} -> {choice}", flush=True)
            return {"name": choice, "value": choice, "payload": {"value": choice}}

    class AskUserMessage:
        """Free-text question (added by mas_eval_patches.diff). Fixed policy: no feedback."""
        def __init__(self, content="", **kwargs):
            self.content = content

        async def send(self):
            s = current.get()
            text = pending["message"] if sim is not None else ""  # the simulated user typed it with its decision
            pending["message"] = ""
            entry = {"step": s.name if s else None, "question": self.content, "options": ["<free text>"], "choice": text}
            rec.decisions.append(entry)
            rec.event("decision", **entry)
            print(f"[headless] free-text question: {self.content!r} -> {text[:200]!r}", flush=True)
            return {"output": text, "content": text}

    class File:
        def __init__(self, name, path):
            self.name, self.path = name, path

    def passthrough(fn):
        return fn

    mod = types.ModuleType("chainlit")
    mod.step = step
    mod.context = Context()
    mod.Message = Message
    mod.Action = Action
    mod.AskActionMessage = AskActionMessage
    mod.AskUserMessage = AskUserMessage
    mod.File = File
    mod.on_chat_start = passthrough
    mod.on_message = passthrough
    mod.__headless_shim__ = True
    sys.modules["chainlit"] = mod
    return mod


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
        return len(data)

    def flush(self):
        for s in self.streams:
            s.flush()

    def isatty(self):
        return False


def git_info():
    def run(*cmd):
        try:
            return subprocess.check_output(cmd, cwd=REPO, text=True).strip()
        except Exception:
            return None

    return {
        "commit": run("git", "rev-parse", "HEAD"),
        "tracked_files_modified": bool(run("git", "status", "--porcelain", "-uno")),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", help="User task description (the chat message).")
    g.add_argument("--prompt-file", help="File containing the user task description.")
    ap.add_argument("--file", action="append", default=[], help="Attachment (.xlsx/.xls/.py). Repeatable.")
    ap.add_argument("--optimization-rounds", type=int, default=2,
                    help="How many times to answer 'continue' to 'new optimization round?' (default 2).")
    ap.add_argument("--name", default="run", help="Label used in the run directory name.")
    ap.add_argument("--out", default=str(ROOT / "runs"), help="Base output directory.")
    ap.add_argument("--timeout", type=int, default=3600, help="Wall-clock limit in seconds (default 3600).")
    ap.add_argument("--recursion-limit", type=int, default=None,
                    help="LangGraph recursion limit. Default: unchanged (LangGraph default, 25 node visits).")
    ap.add_argument("--sim-user", metavar="STATE_JSON",
                    help="Answer the user's questions with the simulated manager; its conversation is kept in this file.")
    ap.add_argument("--keep-generated", action="store_true",
                    help="Do not empty generated/ before the run.")
    args = ap.parse_args()

    prompt = args.prompt if args.prompt is not None else Path(args.prompt_file).read_text(encoding="utf-8")
    attachments = [Path(f).resolve() for f in args.file]
    for f in attachments:
        if not f.is_file():
            sys.exit(f"Attachment not found: {f}")

    os.chdir(REPO)
    sys.path.insert(0, str(REPO))
    os.environ["PATH"] = f"{ROOT / 'mas_harness' / 'bin'}{os.pathsep}{os.environ['PATH']}"

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(REPO / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set (export it or put it in .env at the repo root).")

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out).resolve() / f"{stamp}_{args.name}"
    run_dir.mkdir(parents=True)
    (run_dir / "inputs").mkdir()
    (run_dir / "inputs" / "prompt.txt").write_text(prompt, encoding="utf-8")
    for f in attachments:
        shutil.copy2(f, run_dir / "inputs" / f.name)

    if GENERATED.exists() and not args.keep_generated:
        shutil.rmtree(GENERATED)

    console = open(run_dir / "console.log", "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, console)
    sys.stderr = Tee(sys.__stderr__, console)

    rec = Recorder(run_dir)
    sim = None
    if args.sim_user:
        from sim_user.sim_user import SimManager
        sim = SimManager(args.sim_user, request=prompt, files=[f.name for f in attachments])
    cl = install_chainlit_shim(rec, args.optimization_rounds, sim)

    # The 2025 MAS builds a Claude client at import time although no agent uses it;
    # ChatAnthropic refuses to start without a key, so give it a placeholder.
    os.environ.setdefault("CLAUDE_API_KEY", "placeholder-not-used-by-any-agent")
    import main as pipeline  # original module: builds and compiles the graph
    from agents import common

    # Provider routing only (e.g. OpenRouter needs "openai/gpt-4o" instead of
    # "gpt-4o"). The agents share these two objects, so no pipeline code changes.
    if os.getenv("HEADLESS_LLM_MODEL"):
        common.llm.model_name = os.environ["HEADLESS_LLM_MODEL"]
    if os.getenv("HEADLESS_LLM_CODE_MODEL"):
        common.llm_code.model_name = os.environ["HEADLESS_LLM_CODE_MODEL"]

    summary = {
        "name": args.name,
        "started": dt.datetime.now().isoformat(timespec="seconds"),
        "git": git_info(),
        "python": platform.python_version(),
        "models": {"llm": common.llm.model_name, "llm_code": common.llm_code.model_name},
        "api_base": os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1 (default)",
        "attachments": [f.name for f in attachments],
        "optimization_rounds_requested": None if args.sim_user else args.optimization_rounds,
        "sim_user": args.sim_user,
        "recursion_limit": args.recursion_limit,
        "timeout_s": args.timeout,
        "outcome": None,
    }
    captured = {}

    def finalize(outcome, error=None):
        final_state = captured.get("state") or getattr(rec, "last_state", None)  # aborted runs: last step state
        results = (final_state or {}).get("results") or []
        names = [s["name"] for s in rec.steps]
        summary.update(
            outcome=outcome,
            error=error,
            duration_s=round(time.time() - rec.t0, 1),
            steps=rec.steps,
            n_steps=len(rec.steps),
            n_code_fixer_calls=names.count("Code Fixer Agent"),
            n_docker_executions=names.count("Start Docker Container Agent"),
            n_docker_failures=sum(
                1 for s in rec.steps
                if s["name"] == "Start Docker Container Agent" and s["proceed_after"] == "fix"
            ),
            n_results=len(results),
            decisions=rec.decisions,
            results=[
                {k: v for k, v in to_jsonable(r).items() if k != "code"} if hasattr(r, "model_dump") else str(r)
                for r in results
            ],
            messages=rec.messages,
            last_program_output=rec.last_program_output,
            sim_shown_upto=rec.shown_upto,
        )
        if final_state is not None:
            (run_dir / "final_state.json").write_text(
                json.dumps(final_state, ensure_ascii=False, indent=2, default=to_jsonable), encoding="utf-8"
            )
        (run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=to_jsonable), encoding="utf-8"
        )
        rec.event("run_end", outcome=outcome, error=error)
        print(f"\n[headless] outcome: {outcome}" + (f" ({error})" if error else ""))
        print(f"[headless] run directory: {run_dir}", flush=True)

    # The docker agent reads container output synchronously, which blocks the event
    # loop, so the wall-clock limit is enforced from a separate thread.
    def watchdog():
        finalize("timeout", f"exceeded {args.timeout}s")
        subprocess.run(["docker", "compose", "kill"], cwd=GENERATED if GENERATED.exists() else REPO)
        subprocess.run(["docker", "compose", "down"], cwd=GENERATED if GENERATED.exists() else REPO)
        os._exit(124)

    timer = threading.Timer(args.timeout, watchdog)
    timer.daemon = True
    timer.start()

    original_app = pipeline.app

    class AppProxy:
        """Same compiled graph; only captures the final state main() discards."""

        async def ainvoke(self, state, *a, **kw):
            if args.recursion_limit is not None:
                kw["config"] = {"recursion_limit": args.recursion_limit}
            captured["state"] = await original_app.ainvoke(state, *a, **kw)
            return captured["state"]

    pipeline.app = AppProxy()

    message = types.SimpleNamespace(
        content=prompt,
        elements=[cl.File(name=f.name, path=str(f)) for f in attachments],
    )

    exit_code = 0
    try:
        asyncio.run(pipeline.main(message))
        last = rec.steps[-1]["name"] if rec.steps else None
        finalize("completed" if last == "Final Report Agent" else f"ended_after:{last}")
    except BaseException as exc:
        traceback.print_exc()
        finalize("exception", repr(exc))
        exit_code = 1
    finally:
        timer.cancel()
        os.chdir(REPO)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
