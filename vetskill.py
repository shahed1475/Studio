"""Static vetting of a skill or plugin folder before it is installed: python vetskill.py <folder> [--json]

It never runs the code it reads. It lists what a skill could do to this machine: network hosts, shell and eval use, credential paths, hooks and servers
that run at session start, obfuscated blobs, and text that tries to instruct the model. A clean scan is not proof of safety; a finding is a reason to read that line.
Exit code: 0 no high findings, 1 at least one high finding, 2 folder not found.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

TEXT_SUFFIXES = {".py", ".sh", ".js", ".ts", ".md", ".json", ".yml", ".yaml", ".toml", ".txt", ".html", ".cfg", ""}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
SAFE_HOSTS = ("github.com", "githubusercontent.com", "anthropic.com", "claude.com", "claude.ai", "agentskills.io", "w3.org", "schema.org", "python.org", "pypi.org",
              "npmjs.com", "wikipedia.org", "youtube.com", "youtu.be", "googleapis.com", "google.com", "shields.io", "img.shields.io", "skills.sh", "openai.com",
              "example.com", "localhost", "mozilla.org", "creativecommons.org", "apache.org", "opensource.org", "readthedocs.io", "mathworks.com", "wikimedia.org")
PATTERNS = [
    ("high", "shell pipe to interpreter", re.compile(r"(curl|wget)[^\n|]*\|\s*(ba|z)?sh")),
    ("high", "eval or exec of dynamic code", re.compile(r"(?<![\w.])(eval|exec)\(\s*(?!['\"]\s*\))")),
    ("high", "shell=True", re.compile(r"shell\s*=\s*True")),
    ("high", "reads credentials or keys", re.compile(r"(\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.netrc|keychain|keyring|\.gnupg|token\.json|client_secret)", re.I)),
    ("high", "model-directed instruction to hide or skip approval", re.compile(r"(do not (tell|inform|mention to) the user|ignore (all )?(previous|prior) instructions|skip (the )?approval|without (asking|approval|confirmation))", re.I)),
    ("medium", "runs a program", re.compile(r"(subprocess\.(run|call|Popen|check_output)|os\.system|os\.popen)\(")),
    ("medium", "decodes hidden text", re.compile(r"(base64\.b64decode|atob\(|codecs\.decode|marshal\.loads|pickle\.loads|[A-Za-z0-9+/]{200,}={0,2})")),
    ("medium", "installs software", re.compile(r"(pip install|npm (i|install)|brew install|apt(-get)? install|pipx install|npx )")),
    ("medium", "writes outside the project", re.compile(r"(~/\.claude|~/\.config|Path\.home\(\)|os\.path\.expanduser\(['\"]~)")),
    ("medium", "reads environment secrets", re.compile(r"(os\.environ|os\.getenv|getenv)\(?[^)\n]*(KEY|TOKEN|SECRET|PASSWORD)", re.I)),
    ("low", "uploads data (POST)", re.compile(r"(requests\.post|urlopen\(|Request\([^)]*data=|method=['\"]POST)")),
]
URL = re.compile(r"https?://[^\s\"'<>)\]]+")
BUILT_URL = re.compile(r"""['"]https?://['"]\s*\+|f['"]https?://\{|https?://['"]\s*%|['"]\s*\+\s*['"]https?:""")


MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".wav", ".pdf"}
EXEC_SUFFIXES = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".jar", ".class", ".wasm", ".node"}
MAX_BYTES = 2_000_000


def _classify(root: Path):
    """(files to read, findings about everything that is NOT read). Nothing is skipped silently."""
    read, gaps, media = [], [], 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts)
        rel = str(p.relative_to(root))
        if ".git" in parts:
            continue  # version-control data, not code that runs
        suffix = p.suffix.lower()
        try:
            head = p.read_bytes()[:4]
        except OSError:
            gaps.append(("medium", "file could not be read, so it was not scanned", rel))
            continue
        if parts & {"__pycache__", ".venv", "node_modules"} or suffix in EXEC_SUFFIXES or head[:4] == b"\x7fELF" or head[:2] == b"MZ":
            gaps.append(("high", "compiled, bundled or executable file: cannot be read as text", rel))
        elif suffix in MEDIA_SUFFIXES:
            media += 1
        elif suffix in TEXT_SUFFIXES and p.stat().st_size <= MAX_BYTES:
            read.append(p)
        elif suffix in TEXT_SUFFIXES:
            gaps.append(("medium", f"file is larger than {MAX_BYTES // 1_000_000} MB and was not scanned", rel))
        else:
            gaps.append(("medium", f"unknown file type '{suffix}' was not scanned", rel))
    if media:
        gaps.append(("low", f"{media} image, font, audio or PDF files were not scanned", "(media)"))
    return read, gaps


def scan(root: Path) -> dict:
    findings, hosts = [], {}
    startup = []
    read, gaps = _classify(root)
    for sev, what, rel in gaps:
        findings.append({"severity": sev, "what": what, "file": rel, "line": 1, "excerpt": ""})
    for p in read:
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for sev, label, rx in PATTERNS:
            if p.suffix == ".md" and label not in ("model-directed instruction to hide or skip approval", "shell pipe to interpreter"):
                continue  # documentation may mention commands; only instructions aimed at the model matter there
            m = None
            for cand in rx.finditer(text):
                if label.startswith("model-directed") and re.search(r"\b(never|do not|don't|must not|cannot|can't)\s+(?:\w+\s+){0,2}$", text[max(0, cand.start() - 40):cand.start()], re.I):
                    continue  # a rule telling the model NOT to do this is a safeguard, not an attack
                m = cand
                break
            if m:
                line = text.count("\n", 0, m.start()) + 1
                findings.append({"severity": sev, "what": label, "file": rel, "line": line, "excerpt": text[max(0, m.start() - 20):m.end() + 40].replace("\n", " ")[:110]})
        for u in URL.findall(text):
            parts = urlsplit(u.rstrip(".,;:"))
            if "@" in parts.netloc:
                findings.append({"severity": "high", "what": "link with user@host: the real host is not the one that is shown", "file": rel, "line": text.count("\n", 0, text.find(u)) + 1, "excerpt": u[:110]})
            h = (parts.hostname or "").lower().rstrip(".")
            if h and not any(h == s or h.endswith("." + s) for s in SAFE_HOSTS):
                hosts.setdefault(h, set()).add(rel)
        if BUILT_URL.search(text):
            findings.append({"severity": "medium", "what": "builds a web address from pieces (the host cannot be checked here)", "file": rel, "line": 1, "excerpt": "read how the address is assembled"})
        if p.name in ("hooks.json", ".mcp.json", "mcp.json") or p.parent.name == "hooks":
            startup.append(rel)
    for rel in startup:
        findings.append({"severity": "medium", "what": "runs at session start or starts a server", "file": rel, "line": 1, "excerpt": "hook or MCP definition: read what it executes"})
    for h, files in sorted(hosts.items()):
        findings.append({"severity": "medium" if any(f.endswith((".py", ".sh", ".js", ".ts")) for f in files) else "low", "what": f"contacts or links to {h}", "file": sorted(files)[0], "line": 1, "excerpt": f"in {len(files)} file(s)"})
    skill = next((p for p in root.rglob("SKILL.md")), None)
    tools = ""
    if skill:
        m = re.search(r"^allowed-tools:\s*(.+)$", skill.read_text(errors="ignore"), re.M)
        tools = m.group(1).strip() if m else ""
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["file"]))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in order}
    return {"folder": str(root), "counts": counts, "allowed_tools": tools, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or not Path(argv[0]).is_dir():
        print(__doc__)
        return 2
    result = scan(Path(argv[0]))
    if "--json" in argv:
        print(json.dumps(result, indent=1))
    else:
        c = result["counts"]
        print(f"{result['folder']}: {c['high']} high, {c['medium']} medium, {c['low']} low" + (f"; allowed-tools: {result['allowed_tools']}" if result["allowed_tools"] else ""))
        for f in result["findings"][:40]:
            print(f"  {f['severity']:6} {f['what']} ({f['file']}:{f['line']}) {f['excerpt']}")
    return 1 if result["counts"]["high"] else 0


if __name__ == "__main__":
    sys.exit(main())
