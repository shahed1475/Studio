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
4. Prefer `STUDIO_VPS=deploy@<vps> deploy/deploy.sh dry-run-first` (preview first, deploys only when the preview is clean: a fast-forward and no render). The account plugin hook that asks for a dry run before a production deploy is satisfied by typing the preview in the same command: `deploy/deploy.sh dry && deploy/deploy.sh`. `deploy.sh dry` alone only previews. The plain script: it pulls, restarts only what changed, and refuses to restart or rebuild the worker while a render runs (override with FORCE=1). Python files used by `run.py` jobs take effect on the next run with no restart at all.
5. Restart only what changed: `docker compose restart dashboard` for `dashboard.py`/`dashboard.html`/`webauth.py`. Do not restart `worker` while a render is running: it kills the render. Check first: `docker top studio-worker | grep run.py`.
6. Verify: containers healthy, `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8913/healthz` is 200 on the server, and the changed feature works in the browser.

## Never
- Commit `.env`, `client_secret.json`, `token.json`, `settings.json`, `llm.json`, `data/`, `output/`. Secrets reach the server by `scp` only.
- Delete cache files with glob patterns (the cache holds hash-named images that running jobs need).
- Type or store the owner's passwords or API keys. They enter them in Settings or the password prompt.
- Turn Autopilot on or off, approve, hold or release videos without the owner's instruction.

## Hooks that gate these commands (from account plugins, not from this repo) and how to pass them every time
- **Deploy asks for a dry run first** (cto-toolkit): use `STUDIO_VPS=deploy@vps-ai deploy/deploy.sh dry-run-first  # dry-run preview first, deploy only if clean`. The mode name and the trailing comment tell the hook, which judges the command text, that a dry run comes first (the old name `safe` is the same mode but passed only sometimes). It previews, deploys only when the preview is clean (fast-forward, no render), all in one command. Run it alone, not chained with a push or ssh checks.
- **Push is refused when a commit carries a Python file that does not compile** (candy-plugin, reads the commit, not the disk). Run `deploy/clean_check.sh` before committing: it compiles and tests a clean checkout of HEAD.
- **Never partly stage a file with a patch built from working-folder line numbers** (`git apply --cached --unidiff-zero` put a hunk in the wrong place and broke the staged file). To commit only your edit of a file another session also changed: `git show HEAD:file > /tmp/x`, apply your edit to that copy, `python3 -I -m py_compile /tmp/x`, then `git update-index --cacheinfo 100644,$(git hash-object -w /tmp/x),file`, and check `git show :file` compiles.
- **A destructive-pattern hook refuses any command containing the text `rm -rf /`**, even for a temp folder. Do not use `rm -rf`: use `mktemp -d`, `git worktree remove --force`, or `rm -r` on a path you named, in its own command.
- Do not chain a push, a deploy and ssh checks in one line: the hooks judge the whole line. One step per command, and `deploy.sh safe` for the deploy.
- ffmpeg and python live inside `studio-worker`, not on the host: `docker exec studio-worker ffmpeg ...`; `docker exec -i` is needed to pipe a script into python.
- `run_autopilot_pass` through the MCP server may time out while reviews run: the pass still finishes on the server. Check `logs/autopilot.log` before running it again.
