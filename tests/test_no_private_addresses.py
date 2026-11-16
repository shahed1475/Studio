"""The repo is public: no Tailscale address (100.64.0.0/10) or tailnet name (*.ts.net) may be committed (17 Nov 2026: the PC's address was).
Boundary values the security tests need are allowed."""
import ipaddress
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
ALLOWED = {"100.64.0.0", "100.64.0.1", "100.127.255.254"}
IP = re.compile(r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
TSNET = re.compile(r"\b[a-z0-9-]+\.[a-z0-9-]+\.ts\.net\b")


def leaks(text: str) -> list[str]:
    found = []
    for m in IP.finditer(text):
        try:
            if ipaddress.ip_address(m.group()) in TAILSCALE and m.group() not in ALLOWED:
                found.append(m.group())
        except ValueError:
            continue
    return found + TSNET.findall(text)


def test_the_finder_catches_an_address_and_a_tailnet_name_but_not_test_boundaries():
    assert leaks("open http://100.66.1.2:8913 or pc.tail1234.ts.net") == ["100.66.1.2", "pc.tail1234.ts.net"]
    assert leaks("refuse 100.64.0.1 and 100.127.255.254; 10.0.0.1 is fine") == []


def test_no_tracked_file_holds_a_private_address():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    bad = []
    for f in files:
        try:
            text = (ROOT / f).read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if leaks(line):
                bad.append(f"{f}:{line_no}")
    assert bad == [], "private addresses in the public repo: " + ", ".join(bad)
