"""Simulated daycare manager (LLM persona) for headless evaluation runs.

The persona's instructions are SKILL.md, used unchanged, plus the SCENARIO block below,
which fixes the facts of this experiment and the answer format. The persona sees only
what a non-technical user of the tool would read: the tool's chat messages (code removed)
and the printed program output. It never sees code or the evaluation checkers.

The whole conversation with the persona is kept in a JSON file, so that the same persona
remembers the first chat when it decides on a retry in a second process.
"""
import json
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCENARIO = """\
# This session

You are using a scheduling tool, a chat assistant, for your daycare. You sent it the request
below with these attached Excel files: {files}.

--- your request, as you sent it ---
{request}
--- end of request ---

Rules for this session (they take precedence over the general guidance above):
- The facts are those in your request and in the attached files. You may explain what you
  meant and say which issues matter most to you, but do not add new requirements (such as
  breaks, SAK time, qualifications, rest periods or collective-agreement rules) that are not
  in the request or the files, and do not invent new facts.
- Do not introduce new complications (sick staff, changed care times, cancelled substitutes).
- You do not understand the technology. You cannot read program code, and you do not know
  what solvers, integer programming or heuristics are, nor other technical terms. You react to what
  the tool's answers mean for your daycare. If you see technical text you do not understand,
  you can say so.
- A usable result is one you could publish after small manual edits: named staff in shifts,
  for the days or weeks you asked for, with shift times and groups. You look at it as a
  manager would; you do not check every time interval.
- You use this tool in one chat. If the chat does not give you something usable, you may
  try once more in a new chat with a rewritten request and the same files. You will not
  give the tool a third chance.

How to answer: the tool will show you what it displays and ask you something. Reply with
ONE JSON object and nothing else:
{{"what_i_see": "<1-3 sentences, in your own words, about what you see>",
  "decision": "<exactly one of the offered options>",
  "message": "<what you type to the tool, or an empty string>"}}
The "message" is written in your own voice as the manager.
"""

CODE_FENCE = re.compile(r"```.*?```", re.S)


def strip_code(text: str) -> str:
    """Remove code blocks and messages that are just code."""
    text = CODE_FENCE.sub("[code shown here]", text or "")
    head = text.lstrip()[:200]
    if re.match(r"(import |from \S+ import |def |class |#!)", head):
        return "[code shown here]"
    return text


def visible_messages(messages) -> str:
    out = []
    for m in messages:
        c = m["content"] if isinstance(m, dict) else str(m)
        if c.startswith(("New Generated Code:", "New Requirements:")):
            continue
        c = strip_code(c).strip()
        if c and c != "[code shown here]":
            out.append(c)
    return "\n\n---\n\n".join(out)


def program_output(stream_text: str) -> str:
    """The program's own printed output from a Docker step (build log removed)."""
    if "Attaching to" not in (stream_text or ""):
        return ""
    body = stream_text.split("Attaching to", 1)[1].split("\n", 1)[-1]
    lines = [l for l in body.splitlines() if not re.match(r"\s*(\[\w*)?\S+ exited with code \d+", l)]
    return "\n".join(lines).strip()


def clip(text: str, head: int = 14000, tail: int = 3000) -> str:
    text = text or ""
    if len(text) <= head + tail:
        return text
    return text[:head] + f"\n\n[... {len(text) - head - tail} characters not shown ...]\n\n" + text[-tail:]


class SimManager:
    def __init__(self, state_path, request=None, files=(), model=None):
        from openai import OpenAI

        self.path = Path(state_path)
        self.model = model or os.getenv("SIM_USER_MODEL", "openai/gpt-6.1-terra-pro")
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.getenv("OPENAI_API_BASE"), timeout=900)
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            skill = (HERE / "SKILL.md").read_text(encoding="utf-8")
            system = skill + "\n\n" + SCENARIO.format(request=request.strip(), files=", ".join(files) or "none")
            self.state = {"model": self.model, "messages": [{"role": "system", "content": system}], "log": []}
            self.save()

    def save(self):
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    def ask(self, where: str, shown: str, question: str, options: dict) -> dict:
        """options: {value: explanation}. Returns {"decision", "message", "what_i_see"}."""
        opts = "\n".join(f'- "{k}": {v}' for k, v in options.items())
        prompt = f"[{where}]\n\n{shown.strip() or '(nothing new is shown)'}\n\nThe tool asks: {question}\nOptions:\n{opts}"
        msgs = self.state["messages"] + [{"role": "user", "content": prompt}]
        reply, parsed = "", None
        for attempt in range(3):
            try:
                r = self.client.chat.completions.create(model=self.model, messages=msgs,
                    **{"max_tokens" if "openrouter" in (os.getenv("OPENAI_API_BASE") or "") else "max_completion_tokens": 6000})
                reply = r.choices[0].message.content or ""
                u = r.usage.model_dump() if r.usage else {}  # token usage of the simulated manager, for costing
                self.state.setdefault("usage", []).append({
                    "model": getattr(r, "model", None), "prompt_tokens": u.get("prompt_tokens"),
                    "completion_tokens": u.get("completion_tokens"),
                    "cached_prompt_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                    "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")})
            except Exception as exc:  # network etc.: wait and retry
                reply = f"(api error {exc!r})"
                time.sleep(10)
                continue
            m = re.search(r"\{.*\}", reply, re.S)
            try:
                parsed = json.loads(m.group(0)) if m else None
            except json.JSONDecodeError:
                parsed = None
            if parsed and parsed.get("decision") in options:
                break
            msgs = msgs + [{"role": "assistant", "content": reply},
                           {"role": "user", "content": "Please answer with one JSON object; decision must be one of: "
                                                       + ", ".join(options) + "."}]
            parsed = None
        if not parsed:  # persona could not answer: the most passive option
            parsed = {"decision": list(options)[-1], "message": "", "what_i_see": "(no valid answer)", "fallback": True}
        parsed.setdefault("message", "")
        self.state["messages"] += [{"role": "user", "content": prompt}, {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}]
        self.state["log"].append({"where": where, "question": question, "options": list(options), **parsed})
        self.save()
        return parsed
