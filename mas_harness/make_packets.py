"""Builds an evaluator packet (Markdown) per run: for every analysed round the executed
code, the program output and the pipeline's own verdict. Usage: make_packets.py <run-dir>..."""
import json, re, sys
from pathlib import Path

NOISE = re.compile(r"^(Cgl|Cbc|Coin|Clp|At line|Probing|Gomory|Knapsack|Clique|MixedInteger|FlowCover|TwoMir|ZeroHalf|Option for|command line|Welcome to|Version:|Build Date|#\d+ | Network | Container |time=)")

def program_output(docker_output, head=120, tail=40):
    i = docker_output.find("Attaching to")
    lines = [l.rstrip() for l in (docker_output[i:] if i >= 0 else docker_output).splitlines()]
    lines = [l[:220] + (" …" if len(l) > 220 else "") for l in lines if l.strip() and not NOISE.match(l)]
    if len(lines) > head + tail:
        lines = lines[:head] + [f"… [{len(lines) - head - tail} lines omitted] …"] + lines[-tail:]
    return "\n".join(lines)

for run in (map(Path, sys.argv[1:]) if __name__ == "__main__" else []):
    steps = sorted((run / "steps").iterdir())
    summ = json.loads((run / "summary.json").read_text())
    out = [f"# Evaluator packet: {run.name}", "",
           f"Outcome: **{summ['outcome']}** {summ.get('error') or ''}  ",
           f"Container executions: {summ['n_docker_executions']} (failed {summ['n_docker_failures']}), "
           f"code-fixer calls: {summ['n_code_fixer_calls']}, analysed rounds: {summ['n_results']}", ""]
    rnd = 0
    for k, st in enumerate(steps):
        if not st.name.endswith("code_output_analyzer_agent"):
            continue
        rnd += 1
        state = json.loads((st / "state.json").read_text()) if (st / "state.json").exists() else {}
        res = state.get("result") or {}
        prev = steps[k - 1]
        code = (prev / "generated.py").read_text() if (prev / "generated.py").exists() else ""
        out += [f"## Round {rnd}", "", "### Code executed", "```python", code, "```", "",
                "### Program output (solver log lines removed, long output truncated)", "```",
                program_output(state.get("docker_output", "")), "```", "",
                "### Pipeline's own verdict",
                f"- objective_value: {res.get('objective_value')}",
                f"- is_goal_achieved: {res.get('is_goal_achieved')}", ""]
    if rnd == 0:
        last = [s for s in steps if s.name.endswith("start_docker_container_agent")]
        if last:
            state = json.loads((last[-1] / "state.json").read_text())
            out += ["## No round reached analysis", "", "Last code executed:", "```python",
                    (last[-1] / "generated.py").read_text(), "```", "Last error:", "```",
                    state.get("docker_output", "")[-2500:], "```"]
    (run / "evaluator_packet.md").write_text("\n".join(out), encoding="utf-8")
    print(run.name, "rounds:", rnd)
