# Claude Code session start: hook failure and path-boundary review (25 Nov 2026), investigation only; nothing changed

## 1. `SessionStart:compact hook failed`: cause (VERIFIED by reading plugin files)
- **Plugin:** `aws-startup-advisor` 2.0.1 ("Amazon Web Services"), a **synced** plugin from the owner's claude.ai account. It is not listed in `~/.claude/plugins/installed_plugins.json`.
- **Copy:** `~/.claude/plugins/synced/afa2bfd8-…/3268d6cd-…/`.
- **Hook** (`hooks/hooks.json`, "Ambient startup context"): `SessionStart`, `matcher: "*"`, command `cat ${CLAUDE_PLUGIN_ROOT}/scripts/startup-context.txt`, timeout 5 s.
- **The file is missing.** `scripts/` in the synced copy holds only `validate-heroku-migration-report.py`, `validate-migration-report.py` and `validate-startup-program-artifacts.py`, and no `startup-context.txt` exists anywhere in the copy. So `cat` exits 1 on every SessionStart source: startup, resume, clear and **compact**, which is why it appears after each context compaction.
- **Effect:** the hook only adds optional "startup lens" text to context. Claude Code's hooks documentation (code.claude.com/docs/en/hooks, read 25 Nov) treats a non-zero exit of a non-blocking hook as an error shown to the user while the session continues.
  - Startup and compaction themselves work; this session compacted and continued.
  - It affects **every** Claude Code session of this account (synced plugin, user level), not only the studio.
- **Other SessionStart hooks found (files present, not the cause):**
  - `superpowers` 7.0.2: `startup|clear|compact`, `hooks/run-hook.cmd session-start`; both files exist.
  - `security-guidance` 2.0.21: no matcher, `hooks/sg-python.sh … ensure_agent_sdk.py`; both files exist.
  - User `~/.claude/settings.json`: no hooks.
- **Blind spot:** hooks defined in the forbidden folder's own `.claude/settings*.json` were **not** inspected, by rule. A session started in `~/studio` does not load them.
- **Diagnostics (official, no change needed):** `/hooks` lists configured hooks; starting a session with `claude --debug` logs each hook's command and exit code.

## 2. Smallest reversible resolutions (none applied; each needs the owner's yes)
1. **Studio project only:** `/plugin disable aws-startup-advisor --scope local` in a session started in `~/studio`. It writes `~/studio/.claude/settings.local.json`; undo with `/plugin enable`.
2. **Update the synced plugin** (`/plugin update` or re-sync from claude.ai) and check whether the new copy contains the file.
3. **Do nothing:** the error is cosmetic and costs nothing.

Not proposed:
- editing the plugin's files (synced copies are overwritten);
- creating the missing file (that would be writing inside a vendor's plugin);
- changing global settings.

## 3. Path-boundary review: the pasted log
**What the log showed:** `../../.claude/projects/-home-fahad-Desktop-Youtube-automation/memory/kaggle-remote-worker-24nov.md`.

**What can be concluded without opening it:**
- The path is shown **relative to the session's primary working directory**, which is `/home/fahad/Desktop/Youtube-automation`: two levels up is `/home/fahad`. So the absolute file is `~/.claude/projects/-home-fahad-Desktop-Youtube-automation/memory/…`.
- That is Claude Code's per-project auto-memory folder. It sits **outside** the forbidden folder, but its name is derived from it, because this session was started there.
- The log is evidence that the session itself is rooted in the forbidden folder.

**Other effects of that root, verified this session:**
- every shell command starts with its working directory in the forbidden folder (the harness resets it after each command);
- the harness reads the forbidden folder's `CLAUDE.md` into context every turn;
- the Skill tool would load project skills from there;
- the sandbox injects `GIT_CONFIG_KEY_0/1 = safe.directory` with the forbidden path. `tools/claude-studio.sh --check` therefore **refused** today ("these environment variables still point at the forbidden folder: GIT_CONFIG_VALUE_1 GIT_CONFIG_VALUE_0"). With those two unset, every other check passed.

**This session's mitigations (all held):**
- every command starts with `cd /home/fahad/studio` and runs absolute studio interpreters;
- the two injected git variables were unset, and no git command ran after the refusal;
- no Skill tool for project skills; skills were read directly from `~/studio/.claude/skills` and `~/.claude/plugins`;
- the memory file was not reopened, and no memory was written this session.

**Incident (later the same day):**
- When a code-review subagent was requested (the owner asked for a code reviewer), the Review Council plugin's PreToolUse hook on `Agent` inspected the git checkout of the session's working directory, the forbidden folder.
- It refused to dispatch, naming that folder's changed files (`CLAUDE.md`, `.claude/agents`, …).
- So a plugin hook read the forbidden folder's git state as a side effect of an assistant action.
- After that: no bypass variable, no worktree, and no further subagents from this session. The review was done inline.

**Prevention for the next session:**
- Any subagent or plugin hook inherits the session root, so agents must only be used from a session started in `~/studio`.
- Start Claude Code **from a normal terminal** (not from inside this session) with `bash /home/fahad/studio/tools/claude-studio.sh`. The session root becomes `~/studio`, with memory under `~/.claude/projects/-home-fahad-studio/`, `CLAUDE.md` and skills from `~/studio`, and `safe.directory` for `~/studio`.
- The launcher's refusal inside this session is correct and should stay.
