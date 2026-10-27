#!/usr/bin/env python3
"""Audit of the commits that are about to be pushed: the same checks the model-judged Stop review asked for, as a repeatable script.

    python deploy/audit.py [base]        base defaults to origin/main (audits origin/main..HEAD)

1. Secrets: key, token, password and private-key patterns in every added line (tests included); files that must never be committed.
2. I/O: every file, network or process call ADDED in a Python file (tests excluded) must be inside a try with a handler, or be reached only through callers that are,
   or call something that catches OSError itself (agentbus, lessons, agentlog). Anything else is listed for review.
Exit code 1 for a secret or a forbidden file (always) or an unresolved I/O call (with --strict). Prints a short summary."""
import ast
import glob
import re
import subprocess
import sys

SECRETS = re.compile(r"sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|ya29\.|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|"
                     r"[Bb]earer [A-Za-z0-9._-]{20,}|://[^/ :@]+:[^/ @]{4,}@|(api[_-]?key|secret|passw(or)?d|token|auth)[A-Za-z_]*\s*[:=]\s*['\"][A-Za-z0-9/+_=.-]{16,}['\"]")
FORBIDDEN = re.compile(r"(^|/)(\.env|token\.json|client_secret\.json|settings\.json|llm\.json|agent\.json|autopilot\.json)$|^(data|output|output_old|backups)/")
IO_ATTRS = {"write_text", "write_bytes", "read_text", "read_bytes", "mkdir", "unlink", "rename", "touch", "symlink_to", "glob", "rglob", "iterdir", "urlopen", "write_atomic",
            "execute", "check_output", "Popen", "rmtree", "makedirs", "chmod"}
SELF_CATCH = {"agentbus", "lessons", "agentlog"}  # these catch OSError themselves (each has a failure-mode test)
NOT_IO_FORBIDDEN_FILES_OK = {"settings.json": ".claude/settings.json"}  # the project's own Claude Code settings are not the studio's secret settings file


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, errors="ignore")


def added_lines(base: str, path: str | None = None) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    cur = None
    for line in git("diff", "-U0", f"{base}..HEAD", *(["--", path] if path else [])).splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            out.setdefault(cur, set())
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m and cur:
            start, n = int(m.group(1)), int(m.group(2) or 1)
            out[cur] |= set(range(start, start + n))
    return out


def scan_secrets(base: str) -> list[str]:
    found = []
    for line in git("diff", f"{base}..HEAD").splitlines():
        if line.startswith("+") and not line.startswith("+++") and SECRETS.search(line):
            found.append(line[:100])
    for f in git("diff", "--name-only", f"{base}..HEAD").split():
        if FORBIDDEN.search(f) and f not in NOT_IO_FORBIDDEN_FILES_OK.values():
            found.append(f"forbidden file committed: {f}")
    return found


def io_audit(base: str) -> tuple[int, list[str]]:
    mods = {f[:-3]: ast.parse(open(f).read()) for f in glob.glob("*.py")}
    parents = {}
    for t in mods.values():
        for p in ast.walk(t):
            for c in ast.iter_child_nodes(p):
                parents[c] = p

    def in_try(node):
        while node in parents:
            p = parents[node]
            if isinstance(p, ast.Try) and p.handlers and any(node is x or node in ast.walk(x) for x in p.body):
                return True
            node = p
        return False

    def func_of(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, ast.FunctionDef):
                return node
        return None

    def callers(mod, fn):
        for m, t in mods.items():
            for n in ast.walk(t):
                if isinstance(n, ast.Call) and ((m == mod and isinstance(n.func, ast.Name) and n.func.id == fn)
                                                or (isinstance(n.func, ast.Attribute) and n.func.attr == fn and isinstance(n.func.value, ast.Name) and n.func.value.id == mod)):
                    f = func_of(n)
                    if not (m == mod and f and f.name == fn):
                        yield n, f, m

    def guarded(mod, fn, depth=0, seen=()):
        if (mod, fn) in {("run", "main"), ("agenteval", "run")} or (mod == "autopilot" and fn.startswith("do_")):
            return True  # the command line (guarded_main), Autopilot's executors (inside tick's try), the evaluation (per-case try)
        if depth > 5 or (mod, fn) in seen:
            return False
        cs = list(callers(mod, fn))
        if not cs:
            return None
        return all(in_try(n) or (f is not None and guarded(m, f.name, depth + 1, seen + ((mod, fn),))) for n, f, m in cs)

    total, open_ = 0, []
    for path, lines in added_lines(base).items():
        if not path.endswith(".py") or path.startswith("tests/") or "/" in path or path[:-3] not in mods:
            continue
        tree = mods[path[:-3]]
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and n.lineno in lines):
                continue
            name = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
            owner = ast.unparse(n.func.value) if isinstance(n.func, ast.Attribute) else ""
            real = name == "open" or name in IO_ATTRS or (name in {"update", "save", "merge"} and owner == "records")
            if not real:
                continue
            total += 1
            f = func_of(n)
            if in_try(n) or owner in SELF_CATCH or (f and guarded(path[:-3], f.name)):
                continue
            open_.append(f"{path}:{n.lineno} in {f.name if f else '<module>'}(): {ast.unparse(n)[:70]}")
    return total, open_


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    base = args[0] if args else "origin/main"
    try:
        commits = git("rev-list", "--count", f"{base}..HEAD").strip()
    except subprocess.CalledProcessError:
        print(f"audit: cannot read {base}")
        return 2
    if commits == "0":
        print(f"audit: nothing to audit, HEAD has no commits beyond {base}")
        return 0
    secrets = scan_secrets(base)
    total, open_ = io_audit(base)
    print(f"audit {base}..HEAD ({commits} commit(s)): secrets/forbidden files: {len(secrets)} | I/O calls added: {total}, not provably guarded: {len(open_)}")
    for s in secrets:
        print("  SECRET/FILE:", s)
    for o in open_:
        print("  REVIEW I/O:", o)
    return 1 if secrets or (strict and open_) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
