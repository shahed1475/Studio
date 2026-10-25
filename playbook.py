"""Agent playbooks: what each agent is for, when it acts, how, with which tools, what it must never do and when it hands over.

A playbook is a short Markdown file in `playbooks/` (one per agent). `brief` returns the part that goes into the agent's prompts, so an agent always works
from the same written rules. The owner reads and edits these files; an agent never edits them (the trainer agent only proposes a change)."""
import contextlib
import contextvars
import re
from pathlib import Path

import config

DIR = config.ROOT / "playbooks"
SECTIONS = ("Role", "Goal", "When", "How", "Tools", "Never", "Escalate")
MODEL_ROLES = ("script", "review", "cheap")  # the roles llm.py can route


def agents(directory: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (directory or DIR).glob("*.md"))


def load(agent: str, directory: Path | None = None) -> dict | None:
    f = (directory or DIR) / f"{agent}.md"
    try:
        text = f.read_text()
    except OSError:
        return None
    out = {"agent": agent, "model_role": "cheap"}
    m = re.match(r"\s*model_role:\s*(\w+)", text)
    if m:
        out["model_role"] = m.group(1)
    parts = re.split(r"^## (\w+)[ \t]*$", text, flags=re.M)
    for name, body in zip(parts[1::2], parts[2::2]):
        out[name] = body.strip()
    return out


def problems(agent: str, directory: Path | None = None) -> list[str]:
    pb = load(agent, directory)
    if pb is None:
        return [f"no playbook for {agent}"]
    out = [f"{agent}: section {s} is missing or empty" for s in SECTIONS if not pb.get(s)]
    if pb["model_role"] not in MODEL_ROLES:
        out.append(f"{agent}: model_role {pb['model_role']} is not one of {', '.join(MODEL_ROLES)}")
    return out


def model_role(agent: str, directory: Path | None = None) -> str:
    pb = load(agent, directory)
    return pb["model_role"] if pb else "cheap"


def brief(agent: str, sections=("Role", "Goal", "How", "Never"), max_chars: int = 1500, directory: Path | None = None) -> str:
    """The playbook text for a prompt, cut at a line end under max_chars (prompts cost money). Empty when the agent has no playbook."""
    pb = load(agent, directory)
    if not pb:
        return ""
    lines = [f"Playbook of the {agent} agent (your standing rules):"]
    for s in sections:
        if pb.get(s):
            lines.append(f"{s}: " + pb[s].replace("\n", " "))
    out = ""
    for line in lines:
        if len(out) + len(line) + 1 > max_chars:
            out += line[: max(0, max_chars - len(out) - 1)].rsplit(" ", 1)[0]
            break
        out += line + "\n"
    return out.strip()


_ACTING = contextvars.ContextVar("acting_agent", default=None)
INJECT_CHARS = 650  # every model call under a scope carries this much of the playbook: enough to keep the role and the limits, cheap per call


def set_agent(agent: str | None) -> None:
    """For a command line run: the whole process works under this agent's playbook."""
    _ACTING.set(agent)


def current() -> str | None:
    return _ACTING.get()


@contextlib.contextmanager
def acting_as(agent: str | None):
    token = _ACTING.set(agent)
    try:
        yield
    finally:
        _ACTING.reset(token)


def inject(prompt: str) -> str:
    """The prompt with the acting agent's role and limits in front. Unchanged outside a scope, for an agent without a playbook, or when the prompt already
    carries a playbook (an agent that put its own in)."""
    agent = _ACTING.get()
    if not agent or "Playbook of the" in prompt:
        return prompt
    b = brief(agent, ("Role", "Never"), INJECT_CHARS)
    return f"{b}\n\n{prompt}" if b else prompt
