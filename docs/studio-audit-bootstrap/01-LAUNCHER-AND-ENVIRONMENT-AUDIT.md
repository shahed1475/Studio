# 01 — Launcher and environment audit

Status: COMPLETE. Everything here was VERIFIED in this session unless it is labelled otherwise.

## Session environment (sanitized)

| Item | Value |
|---|---|
| Working directory (logical / physical) | `/home/fahad/studio` / `/home/fahad/studio` |
| User / HOME / shell | fahad (uid 1000) / `/home/fahad` / `/bin/bash` |
| claude | `/home/fahad/.local/bin/claude` -> `~/.local/share/claude/versions/2.1.332` |
| git | `/usr/bin/git` 2.56.1 |
| python3 | `/home/fahad/studio/.venv/bin/python3` (-> `/usr/bin/python3.14`), `VIRTUAL_ENV=/home/fahad/studio/.venv` |
| PYTHONPATH, CLAUDE_CONFIG_DIR, DOCKER_HOST, DOCKER_CONTEXT | unset (DOCKER_CONTEXT is set by the launcher only) |
| Git variables | `GIT_CONFIG_KEY_0/1=safe.directory` with values `/home/fahad/studio` and `/home/fahad/studio/*`, plus proxy settings and `GIT_EDITOR=true`. These come from the Claude Code harness and sandbox, not from the launcher. They add trust for Studio and disable no check. |
| Forbidden folder in PATH or any variable | none |
| `.claude/settings.json`, `.claude/settings.local.json`, `.mcp.json` in Studio | do not exist (the Read tool reports "File does not exist"; the sandbox shows `/dev/null` placeholders there because it masks paths it may not write) |

PATH has junk entries ("Unknown command", "bin", "To see a list of supported npm commands, run", "npm help") and many duplicates. A shell profile appears to build PATH from the output of an `npm` subcommand that no longer exists (INFERRED; the profile was not opened, it is outside the approved scope). The launcher drops entries that do not start with `/`, so this is harmless to it.

## Launcher: `/home/fahad/studio/tools/claude-studio.sh`

Physical path: the same (not a symlink), mode 755, owner fahad. Syntax check (`bash -n`) passes. **The file is untracked in git** (`git status`: `??`).

Execution order, as written:
1. `set -euo pipefail`
2. `cd /home/fahad/studio` (an absolute path, a real directory, so logical and physical paths match)
3. `unset OLDPWD`, then unset VIRTUAL_ENV, PYTHON*, CONDA_*, DOCKER_* variables
4. Rebuild PATH: drop entries inside the forbidden folder and entries without a leading `/`, remove duplicates, put `.venv/bin` first. Export VIRTUAL_ENV and `DOCKER_CONTEXT=default`.
5. Refuse to start if any environment variable still contains the forbidden path
6. Refuse to start unless `python3` resolves to the Studio venv and `sys.prefix` (read with `-I`) is the venv
7. Refuse to start unless docker context `default` points at `unix:///var/run/docker.sock`
8. Refuse to start if the `studio-worker` container mounts something other than Studio at `/app`
9. `--check`: print the results and exit 0. Otherwise: require `claude` on PATH, then `exec claude "$@"`

Answers to mission Part 2:

| # | Question | Answer |
|---|---|---|
| 1 | Expected directory | `/home/fahad/studio`, hard-coded |
| 2 | How the root is determined | constant, not derived from `$0` or the caller's directory |
| 3 | Changes directory first | yes, step 2, before every check |
| 4 | Physical or logical path | `cd` to a non-symlink path, so both are the same; `--check` prints `pwd -P` |
| 5 | Symlinks or inherited shell state | OLDPWD, venv, Python and Docker variables are cleared; PWD is reset by `cd` |
| 6 | Git checks before or after directory validation | the launcher runs no git command. Git trust (`safe.directory`) is added by the Claude Code harness for the working directory |
| 7 | Can environment variables change its behaviour | only PATH (filtered) and the variables it clears; `CLAUDE_CONFIG_DIR` is not cleared (unset in this session) |
| 8 | Does `--check` validate startup accurately | mostly. **Defect L-1:** the worker-mount check fails open (see below) |
| 9 | Normal launch versus `--check` | the same checks; the launch path also requires `claude` on PATH, then `exec` |
| 10 | Does a hook or wrapper change directory | no Studio hook is registered (see 04); `claude` resolves straight to the versioned binary |
| 11 | Unsafe inherited state | covered for Python, Docker and PATH; arbitrary other variables are inherited, but any variable containing the forbidden path is refused |
| 12 | Is Claude launched in the intended directory | yes, `exec` from `/home/fahad/studio` |

### Defect L-1 (medium): the worker-mount check fails open

`docker ... inspect studio-worker ... 2>/dev/null || true` turns *every* error into an empty string, and an empty string passes ("not running"). VERIFIED: inside the Claude sandbox, docker returns `permission denied while trying to connect to the docker API`, yet `--check` printed `studio-worker: /app <- not running` and exited 0. From a normal terminal docker is reachable, so the check probably works there (INFERRED; not run outside the sandbox, by rule 0.3).

### `--check` result in this session

```
cwd:            /home/fahad/studio
python3:        /home/fahad/studio/.venv/bin/python3 (sys.prefix /home/fahad/studio/.venv)
docker context: default -> unix:///var/run/docker.sock
studio-worker:  /app <- not running      (really: docker was not reachable from the sandbox, see L-1)
forbidden folder on PATH: 0
exit=0
```
