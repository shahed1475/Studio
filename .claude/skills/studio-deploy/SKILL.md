---
name: studio-deploy
description: "Use to ship code changes to the VPS safely: test, commit, rebase on the other session's work, push, pull on the server, restart only what changed. Protects renders that are in progress."
---

# Deploy the studio

The studio runs in two containers on the VPS (`studio-dashboard`, `studio-worker`) from a bind-mounted checkout in `~/studio`. Another Claude session also pushes to this repo.

## Steps
1. `.venv/bin/python -m pytest -q` must pass. Never push a failing suite.
2. `git add -A && git commit` (end with the Co-Authored-By line given by the session).
3. `git pull --rebase origin main` before `git push origin main`.
4. Prefer `STUDIO_VPS=deploy@<vps> deploy/deploy.sh`: it pulls, restarts only what changed, and refuses to restart or rebuild the worker while a render runs (override with FORCE=1). Python files used by `run.py` jobs take effect on the next run with no restart at all.
5. Restart only what changed: `docker compose restart dashboard` for `dashboard.py`/`dashboard.html`/`webauth.py`. Do not restart `worker` while a render is running: it kills the render. Check first: `docker top studio-worker | grep run.py`.
6. Verify: containers healthy, `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8913/healthz` is 200 on the server, and the changed feature works in the browser.

## Never
- Commit `.env`, `client_secret.json`, `token.json`, `settings.json`, `llm.json`, `data/`, `output/`. Secrets reach the server by `scp` only.
- Delete cache files with glob patterns (the cache holds hash-named images that running jobs need).
- Type or store the owner's passwords or API keys. They enter them in Settings or the password prompt.
- Turn Autopilot on or off, approve, hold or release videos without the owner's instruction.
