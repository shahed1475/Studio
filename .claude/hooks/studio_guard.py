#!/usr/bin/env python3
"""PreToolUse hook for Bash commands in this project: two deterministic guards that replace the model-judged plugin hooks (which gave a different answer on
the same command from one run to the next, and refused harmless commands that only quoted a dangerous one).

1. Destructive commands are refused: a recursive rm of the filesystem root, the home folder, a wildcard or a top-level system folder; DROP DATABASE;
   TRUNCATE TABLE; DELETE FROM without WHERE; a fork bomb. Removing a named folder (a temp or scratch folder) is allowed.
2. A production deploy must preview first: deploy/deploy.sh only with the mode dry-run-first, safe or dry (or `first` for a new server); kubectl or terraform
   apply, docker push, npm publish, aws or gcloud deploy only with a dry-run flag in the same command.

Quoted text and the bodies of here-documents are not commands and are not checked, EXCEPT where a command is run from them: the text of `bash -c`, `eval`, an
ssh remote command, the command after xargs, `find -delete` / `-exec rm`, `$(...)` and backticks, and a here-document fed to a shell or ssh are all checked as
commands, to a depth of 5. A command this script cannot read (an unbalanced quote, too deeply nested) is refused when it mentions rm, deploy.sh or a production
tool, and let through otherwise. Not covered: `source`/`.` of a file, `python -c`, `perl -e` and the like, aliases, scripts written then run. This is a guard
against my own mistakes on this PC, not a security boundary.
Input: the hook JSON on stdin. Exit 2 with a plain reason on stderr refuses the command; exit 0 lets it run. Unreadable hook input is let through."""
import json
import posixpath
import re
import shlex
import sys

TOP_LEVEL = {"/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "${HOME}", "${HOME}/", "$HOME/*", "*", ".", "..", "./*", "../*"}
RELATIVE_TOP = {"*", ".", "..", "./*", "../*"}  # fine as the start of a filtered `find`, not as a recursive rm target
SYSTEM_DIRS = {"bin", "boot", "dev", "etc", "home", "lib", "lib64", "opt", "proc", "root", "run", "sbin", "srv", "sys", "usr", "var"}
WRAPPERS = ("sudo", "command", "env", "time", "nohup", "exec", "nice", "setsid", "timeout")
WRAPPER_OPT_ARG = {"sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"}, "env": {"-u", "-C", "-S"}, "nice": {"-n"}, "timeout": {"-s", "-k"}}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SSH_OPT_ARG = {"-p", "-i", "-l", "-o", "-F", "-J", "-L", "-R", "-D", "-b", "-c", "-e", "-m", "-O", "-S", "-W", "-w", "-E", "-B", "-I", "-Q"}
XARGS_OPT_ARG = {"-I", "-n", "-P", "-d", "-s", "-E", "-L", "-a", "-J"}
PROD = {"kubectl": "apply", "terraform": "apply", "docker": "push", "npm": "publish", "aws": "deploy", "gcloud": "deploy"}
PREVIEW_MODES = {"dry-run-first", "safe", "dry", "first"}
MAX_DEPTH = 5
GUARDED_WORDS = re.compile(r"\brm\b|deploy\.sh|\b(kubectl|terraform|docker|npm|aws|gcloud)\b")
HEREDOC = re.compile(r"<<-?[ \t]*(?:(['\"])([A-Za-z_]\w*)\1|\\?([A-Za-z_]\w*))")


class Unclassifiable(Exception):
    """The command cannot be split into simple commands (unbalanced quote, nested too deeply)."""


def _match(s: str, i: int) -> int:
    """Index of the ")" that closes the "(" at s[i] (the last index when unclosed)."""
    depth = 0
    for k in range(i, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(s) - 1


def scan(command: str) -> tuple[str, str, list[tuple[str, str]], list[str]]:
    """Walk the command once with the shell's quoting rules. Returns (text to split into commands, text for the pattern checks, here-documents as
    (the command line, the body), the text of every $(...) and backtick substitution). A here-document starts only at an unquoted `<<` (not `<<<`, not inside
    $((...)) or a comment); its body is left out of both texts. A substitution is left out of the first text and checked on its own."""
    s = command.replace("\\\n", "")
    out, plain, heredocs, subs = [], [], [], []
    quote, pending, line_start, i, n = None, [], 0, 0, len(s)
    while i < n:
        c = s[i]
        if c == "\n" and quote is None:
            out.append(c)
            plain.append(c)
            i += 1
            if pending:
                line = s[line_start:i - 1]
                for delim in pending:
                    body = []
                    while i < n:
                        j = s.find("\n", i)
                        j = n if j < 0 else j
                        ln, i = s[i:j], min(j + 1, n)
                        if ln.strip() == delim:
                            break
                        body.append(ln)
                    heredocs.append((line, "\n".join(body)))
                pending = []
            line_start = i
            continue
        if quote == "'":
            quote = None if c == "'" else quote
            out.append(c)
            plain.append(c)
            i += 1
            continue
        if c == "\\":
            out.append(s[i:i + 2])
            plain.append(s[i:i + 2])
            i += 2
            continue
        if s.startswith("$((", i) and s[_match(s, i + 1) - 1:_match(s, i + 1)] == ")" and _match(s, i + 2) == _match(s, i + 1) - 1:  # arithmetic only when it closes with ))
            k = _match(s, i + 1)
            inner = s[i + 3:k - 1]  # substitutions still run inside arithmetic
            subs += [m.group(1) for m in re.finditer(r"`([^`]*)`", inner)]
            subs += [inner[m.start() + 2:_match(inner, m.start() + 1)] for m in re.finditer(r"\$\(", inner)]
            out.append(s[i:k + 1])
            plain.append(s[i:k + 1])
            i = k + 1
            continue
        if s.startswith("$(", i):
            k = _match(s, i + 1)
            subs.append(s[i + 2:k])
            out.append("$()")
            plain.append(s[i:k + 1])
            i = k + 1
            continue
        if c == "`":
            k = s.find("`", i + 1)
            k = n - 1 if k < 0 else k
            subs.append(s[i + 1:k])
            out.append("``")
            plain.append(s[i:k + 1])
            i = k + 1
            continue
        if quote == '"':
            quote = None if c == '"' else quote
        elif c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or s[i - 1] in " \t\n;&|("):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        elif s.startswith("<<<", i):
            out.append("<<<")
            plain.append("<<<")
            i += 3
            continue
        elif s.startswith("<<", i):
            m = HEREDOC.match(s, i)
            if m:
                pending.append(m.group(2) or m.group(3))
                out.append(m.group(0))
                plain.append(m.group(0))
                i = m.end()
                continue
        out.append(c)
        plain.append(c)
        i += 1
    return "".join(out), "".join(plain), heredocs, subs


def _split(text: str) -> list[list[str]]:
    """Each simple command as a token list. Quotes are respected, so a quoted string that only mentions a dangerous command is not that command."""
    lex = shlex.shlex(text, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace_split = True
    lex.whitespace = " \t\r"
    lex.commenters = ""
    try:
        tokens = list(lex)
    except ValueError as e:
        raise Unclassifiable(str(e))
    out: list[list[str]] = []
    cur: list[str] = []
    for t in tokens:
        if t and set(t) <= set(";&|()\n"):
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    out.append(cur)
    return [c for c in out if c]


def _unwrap(tokens: list[str]) -> list[str]:
    """The command itself: environment assignments, sudo, env, time, nohup, exec, nice, timeout and their options skipped."""
    t = list(tokens)
    while t:
        if re.match(r"^[A-Za-z_]\w*=", t[0]):
            t = t[1:]
            continue
        name = t[0].split("/")[-1]
        if name not in WRAPPERS:
            break
        t = t[1:]
        takes_arg = WRAPPER_OPT_ARG.get(name, set())
        while t and (t[0].startswith("-") or (name == "timeout" and re.match(r"^\d+(\.\d+)?[smhd]?$", t[0]))):
            t = t[2:] if t[0] in takes_arg and len(t) > 1 else t[1:]
        if name == "timeout" and t and re.match(r"^\d+(\.\d+)?[smhd]?$", t[0]):
            t = t[1:]
    return t


def _nested(tokens: list[str]) -> tuple[list[str], list[list[str]]]:
    """(command texts, token lists) run by this command: a shell's -c text, eval, an ssh remote command, the command after xargs, find's -delete or -exec rm."""
    t = _unwrap(tokens)
    if not t:
        return [], []
    name, texts, extra = t[0].split("/")[-1], [], []
    if name in SHELLS:
        for i, a in enumerate(t[1:], 1):  # after the first -c group (-c, -ec, -xo ... -c) every later word may be the command text, whatever options come between
            if a[:1] in "-+" and not a.startswith("--") and "c" in a[1:]:
                texts += t[i + 1:]  # no filter: after `--` the command text may itself start with - or +
                break
    elif name == "eval":
        texts.append(" ".join(t[1:]))
    elif name == "ssh":
        j = 1
        while j < len(t) and t[j].startswith("-"):
            j += 2 if t[j] in SSH_OPT_ARG else 1
        if j + 1 < len(t):
            texts.append(" ".join(t[j + 1:]))
    elif name == "xargs":
        j = 1
        while j < len(t) and t[j].startswith("-"):
            j += 2 if t[j] in XARGS_OPT_ARG else 1
        inner = t[j:]
        if inner:
            extra.append(inner + ["*"] if _rm_targets(_unwrap(inner)) is not None else inner)  # paths come from stdin: unknown, so treat as a wildcard
    elif name == "find":
        starts = []
        for a in t[1:]:
            if a.startswith("-") or a in ("(", "!", ")"):
                break
            starts.append(a)
        danger = [p for p in starts if p not in RELATIVE_TOP and _dangerous_path(p)]
        if "-delete" in t and danger:
            extra.append(["rm", "-rf"] + danger)
        # whatever -exec / -execdir / -ok runs is a command of its own, with {} standing for the start paths (a relative start is a filtered search: not the root)
        paths = [p if p not in RELATIVE_TOP else "./match" for p in starts] or ["./match"]
        for i, a in enumerate(t):
            if a in ("-exec", "-execdir", "-ok", "-okdir"):
                chunk = []
                for b in t[i + 1:]:
                    if b in ("+", ";"):
                        break
                    chunk.append(b)
                if chunk:
                    extra += [[b.replace("{}", p) for b in chunk] for p in paths]  # {} may sit inside an argument (sh -c "rm -rf {}")
    return texts, extra


def _expand(tokens: list[str], depth: int) -> list[list[str]]:
    if depth > MAX_DEPTH:
        raise Unclassifiable("nested too deeply")
    out = [tokens]
    texts, extra = _nested(tokens)
    for text in texts:
        out += segments(text, depth + 1)
    for e in extra:
        out += _expand(e, depth + 1)
    return out


def _feeds_a_shell(tokens: list[str]) -> bool:
    t = _unwrap(tokens)
    return bool(t) and t[0].split("/")[-1] in SHELLS | {"ssh"}


def segments(command: str, depth: int = 0) -> list[list[str]]:
    """Every simple command that would run, as token lists, including the ones hidden inside other commands (see the module note)."""
    if depth > MAX_DEPTH:
        raise Unclassifiable("nested too deeply")
    text, _plain, heredocs, subs = scan(command)
    out: list[list[str]] = []
    for tokens in _split(text):
        out += _expand(tokens, depth)
    for line, body in heredocs:
        if any(_feeds_a_shell(seg) for seg in segments(line, depth + 1)):
            out += segments(body, depth + 1)
    for sub in subs:
        out += segments(sub, depth + 1)
    return out


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
    p = posixpath.normpath(re.sub(r"/+", "/", p))                                 # //, /./ and /tmp/.. are the root
    if p == "/":
        return True
    parts = [x for x in p.split("/") if x]
    if len(parts) == 1:
        return parts[0].rstrip("*") in SYSTEM_DIRS                                # a top-level system folder
    return len(parts) == 2 and parts[1] == "*" and parts[0] in SYSTEM_DIRS        # everything inside one


def destructive(plain: str, segs: list[list[str]]) -> str | None:
    if re.search(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", plain):
        return "a fork bomb"
    if re.search(r"\bDROP\s+(DATABASE|SCHEMA)\b", plain, re.I):
        return "DROP DATABASE"
    if re.search(r"\bTRUNCATE\s+TABLE\b", plain, re.I):
        return "TRUNCATE TABLE"
    if re.search(r"\bDELETE\s+FROM\s+\w+\s*(;|\"|'|$)", plain, re.I):
        return "DELETE FROM without WHERE"
    for seg in segs:
        targets = _rm_targets(_unwrap(seg))
        if targets and any(_dangerous_path(t) for t in targets):
            return f"a recursive delete of {', '.join(t for t in targets if _dangerous_path(t))}"
    return None


def _deploy_run(tokens: list[str]) -> tuple[bool, str | None]:
    """(runs the deploy script, its mode). A script that is only read, staged or syntax-checked (cat, grep, git add, bash -n) does not run."""
    t = _unwrap(tokens)
    if t and t[0].split("/")[-1] in SHELLS and len(t) > 1 and not t[1].startswith("-"):
        t = t[1:]
    if t and re.search(r"(^|/)deploy\.sh$", t[0]):
        return True, (t[1] if len(t) > 1 else None)
    return False, None


def deploy_without_preview(segs: list[list[str]]) -> str | None:
    previewed = False
    for seg in segs:
        runs, mode = _deploy_run(seg)
        if runs and mode in PREVIEW_MODES:
            previewed = previewed or mode != "first"
        elif runs and not previewed:
            return "deploy/deploy.sh must run in a preview mode first: `deploy/deploy.sh dry-run-first` previews, then deploys only if the preview is clean"
    for seg in segs:  # a production command needs a dry-run flag among its own arguments (not in a comment or another command)
        t = _unwrap(seg)
        verb = PROD.get(t[0].split("/")[-1]) if t else None
        if verb and verb in t[1:] and not any(re.match(r"^(--dry-run(=(client|server|true))?|--server-dry-run|-dry-run)$", a) for a in t[1:]):
            return "a production command needs a dry run first (--dry-run in the same command)"
    return None


def check(command: str) -> str | None:
    try:
        _text, plain, _h, _s = scan(command)
        segs = segments(command)
    except Exception:  # unbalanced quote, nested too deeply, or a bug in this script: refuse only when something guarded is mentioned
        if GUARDED_WORDS.search(command):
            return ("Refused: this command could not be read safely and it mentions rm, deploy.sh or a production tool. Split it into simple commands, "
                    "or run it yourself.")
        return None
    bad = destructive(plain, segs)
    if bad:
        return f"Refused: {bad}. If this is really intended, run it yourself or name the exact folder to remove."
    nodry = deploy_without_preview(segs)
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
