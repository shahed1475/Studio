"""The gateway between an MCP client and the studios on this server.

It runs on the SERVER HOST (outside the studio containers), as the same user that runs Docker. For every tool call it does exactly one thing: run
`docker exec -i <studio's worker container> python -m controls` and send the request as JSON on standard input. What the caller sends is never turned into
code, a shell command or a file path: the studio name must be one of the running studios, and `controls.py` (inside the container) checks the call name,
the argument names and the video name again.

Studios are found from the running containers: `studio-worker` is the owner's ("owner"), `studio-<name>-worker` is a user studio ("<name>")."""
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

OWNER = "owner"
TENANT = re.compile(r"studio-([a-z0-9]{2,15})-worker")
MAX_REPLY = 24_000  # characters returned to the model; longer answers are cut and say so
TIMEOUT = 150       # seconds: a pass or a backup can take a while


class GatewayError(Exception):
    pass


def _docker(args: list[str], stdin: str | None = None, timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], input=stdin, capture_output=True, text=True, timeout=timeout)


class Gateway:
    def __init__(self, runner=_docker, audit: Path | None = None, now=lambda: dt.datetime.now(dt.timezone.utc)):
        self.run, self.audit, self.now = runner, audit, now

    def studios(self) -> dict[str, str]:
        """{studio name: worker container name} for every running studio."""
        r = self.run(["ps", "--format", "{{.Names}}"], None, 20)
        if r.returncode != 0:
            raise GatewayError("docker is not reachable")
        found = {}
        for name in r.stdout.split():
            if name == "studio-worker":
                found[OWNER] = name
            elif (m := TENANT.fullmatch(name)):
                found[m.group(1)] = name
        return found

    def call(self, studio: str, call: str, args: dict | None = None):
        studios = self.studios()
        if studio not in studios:
            raise GatewayError(f"no running studio named {studio!r}; running: {', '.join(sorted(studios)) or 'none'}")
        req = json.dumps({"call": call, "args": args or {}})
        ok = False
        try:
            r = self.run(["exec", "-i", studios[studio], "python", "-m", "controls"], req, TIMEOUT)
            try:
                out = json.loads(r.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                raise GatewayError(f"the studio gave no answer ({r.stderr.strip()[-160:] or 'empty'})")
            if not out.get("ok"):
                raise GatewayError(out.get("error", "failed"))
            ok = True
            return out["result"]
        finally:
            self._log(studio, call, args, ok)

    def _log(self, studio: str, call: str, args, ok: bool) -> None:
        if self.audit:
            try:
                with self.audit.open("a") as f:
                    f.write(json.dumps({"at": self.now().strftime("%Y-%m-%dT%H:%M:%SZ"), "studio": studio, "call": call, "args": args or {}, "ok": ok}) + "\n")
            except OSError:
                pass  # a full disk must not stop a read

    @staticmethod
    def text(result) -> str:
        s = json.dumps(result, indent=1, ensure_ascii=False)
        return s if len(s) <= MAX_REPLY else s[:MAX_REPLY] + f"\n... cut: {len(s) - MAX_REPLY} more characters"
