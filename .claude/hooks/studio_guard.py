#!/usr/bin/env python3
"""PreToolUse hook for Bash commands in this project: two deterministic guards that replace the model-judged plugin hooks (which gave a different answer on
the same command from one run to the next, and refused harmless commands that only quoted a dangerous one).

1. Destructive commands are refused: a recursive rm of the filesystem root, the home folder, a wildcard or a top-level system folder; DROP DATABASE;
   TRUNCATE TABLE; DELETE FROM without WHERE; a fork bomb. Removing a named folder (a temp or scratch folder) is allowed. Quoted text and the bodies of
   here-documents are not commands and are not checked.
2. A production deploy must preview first: deploy/deploy.sh only with the mode dry-run-first, safe or dry (or `first` for a new server); kubectl or terraform
   apply, docker push and npm publish only with a dry-run flag, plan or diff.
Input: the hook JSON on stdin. Exit 2 with a plain reason on stderr refuses the command; exit 0 lets it run. A command this script cannot read is let through."""
import json
import re
import shlex
import sys

TOP_LEVEL = {"/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "${HOME}", "${HOME}/", "$HOME/*", "*", ".", "..", "./*", "../*"}
SYSTEM_DIRS = {"bin", "boot", "dev", "etc", "home", "lib", "lib64", "opt", "proc", "root", "run", "sbin", "srv", "sys", "usr", "var"}
WRAPPERS = ("sudo", "command", "env", "time", "nohup", "exec")


def strip_heredocs(command: str) -> str:
    """The command without the bodies of its here-documents: text written into a file or fed to a script is not a command."""
    out, end = [], None
    for line in command.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        out.append(line)
        m = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
        if m:
            end = m.group(2)
    return "\n".join(out)


def segments(command: str) -> list[list[str]]:
    """Each simple command as a token list. Quotes are respected, so a quoted string that only mentions a dangerous command is not that command. A line that
    cannot be tokenised (an unbalanced quote across lines) is skipped."""
    out = []
    for line in strip_heredocs(command).split("\n"):
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            tokens = list(lex)
        except ValueError:
            continue
        cur: list[str] = []
        for t in tokens:
            if t and set(t) <= set(";&|()"):
                out.append(cur)
                cur = []
            else:
                cur.append(t)
        out.append(cur)
    return [c for c in out if c]


def _rm_targets(tokens: list[str]) -> list[str] | None:
    """The paths of a recursive rm, or None when this is not a recursive rm."""
    if not tokens or tokens[0].split("/")[-1] != "rm":
        return None
    short = "".join(t.lstrip("-") for t in tokens[1:] if t.startswith("-") and not t.startswith("--"))
    if not ("r" in short.lower() or "--recursive" in tokens):
        return None
    return [t for t in tokens[1:] if not t.startswith("-")]


def _dangerous_path(p: str) -> bool:
    if p in TOP_LEVEL:
        return True
    if not p.startswith("/"):
        return False
    parts = [x for x in p.split("/") if x]
    if len(parts) == 1:
        return parts[0].rstrip("*") in SYSTEM_DIRS                                # a top-level system folder
    return len(parts) == 2 and parts[1] == "*" and parts[0] in SYSTEM_DIRS        # everything inside one


def destructive(command: str) -> str | None:
    body = strip_heredocs(command)
    if re.search(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", body):
        return "a fork bomb"
    if re.search(r"\bDROP\s+(DATABASE|SCHEMA)\b", body, re.I):
        return "DROP DATABASE"
    if re.search(r"\bTRUNCATE\s+TABLE\b", body, re.I):
        return "TRUNCATE TABLE"
    if re.search(r"\bDELETE\s+FROM\s+\w+\s*(;|\"|'|$)", body, re.I):
        return "DELETE FROM without WHERE"
    for tokens in segments(command):
        while tokens and tokens[0] in WRAPPERS:
            tokens = tokens[1:]
        targets = _rm_targets(tokens)
        if targets and any(_dangerous_path(t) for t in targets):
            return f"a recursive delete of {', '.join(t for t in targets if _dangerous_path(t))}"
    return None


PREVIEW_MODES = {"dry-run-first", "safe", "dry", "first"}


def _deploy_run(tokens: list[str]) -> tuple[bool, str | None]:
    """(runs the deploy script, its mode). Environment assignments, timeout and sudo in front are skipped; a script that is only read, staged or syntax-checked
    (cat, grep, git add, bash -n) does not run."""
    t = list(tokens)
    while t and (re.match(r"^[A-Za-z_]\w*=", t[0]) or t[0] in WRAPPERS):
        t = t[1:]
    if t and t[0] == "timeout":
        t = t[1:]
        while t and (t[0].startswith("-") or re.match(r"^\d+[smhd]?$", t[0])):
            t = t[1:]
    if t and t[0] in ("bash", "sh") and len(t) > 1 and not t[1].startswith("-"):
        t = t[1:]
    if t and re.search(r"(^|/)deploy\.sh$", t[0]):
        return True, (t[1] if len(t) > 1 else None)
    return False, None


def deploy_without_preview(command: str) -> str | None:
    body = strip_heredocs(command)
    previewed = False
    for tokens in segments(command):
        runs, mode = _deploy_run(tokens)
        if runs and mode in PREVIEW_MODES:
            previewed = previewed or mode != "first"
        elif runs and not previewed:
            return "deploy/deploy.sh must run in a preview mode first: `deploy/deploy.sh dry-run-first` previews, then deploys only if the preview is clean"
    if re.search(r"\b(kubectl\s+apply|terraform\s+apply|docker\s+push|npm\s+publish|aws\s+deploy|gcloud\s+\S*\s*deploy)\b", body):
        if not re.search(r"--dry-run|-dry-run|--server-dry-run|\bplan\b|\bdiff\b", body):
            return "a production command needs a dry run first (--dry-run, plan or diff)"
    return None


def check(command: str) -> str | None:
    bad = destructive(command)
    if bad:
        return f"Refused: {bad}. If this is really intended, run it yourself or name the exact folder to remove."
    nodry = deploy_without_preview(command)
    return f"Refused: {nodry}." if nodry else None


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        command = str((data.get("tool_input") or {}).get("command", ""))
    except (ValueError, AttributeError):
        return 0  # unreadable input: never block on a guess
    why = check(command) if command else None
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
