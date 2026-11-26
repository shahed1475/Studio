# 02 — Claude startup context

Status: COMPLETE. Sources: official docs, searched on 2026-11-26 (code.claude.com: memory, settings-reference, permissions, permission-modes, agent-sdk/skills, large-codebases).

## Documented behaviour (DOCUMENTED)

- **CLAUDE.md**: loaded from the working directory and every parent at launch, concatenated root-first; subdirectory files load on demand. `/context all` lists the files that loaded (memory page).
- **Skills**: `~/.claude/skills/` (user), `<cwd>/.claude/skills/` and `.claude/skills/` in parents up to the repository root (project). Skills load on demand; CLAUDE.md loads every session (agent-sdk/skills page; the SDK reads the same files as the CLI).
- **Settings precedence**: managed > command line > local project > project > user. Project settings live in `<cwd>/.claude/settings.json`.
- **Working directories**: the launch directory, plus `--add-dir`, `/add-dir` or `permissions.additionalDirectories`. A directory added only in repository settings does not load configuration (instructions, skills) from that directory.
- **Sandbox writes**: working directory, temp directory, added directories. Reads: the whole filesystem by default.
- **Permission modes**: `permissions.defaultMode` takes default, acceptEdits, plan, auto, dontAsk or bypassPermissions.

## Verified in this installed version (2.1.332)

- The sandbox write allow-list is `.` (cwd = `/home/fahad/studio`), `$TMPDIR`, `/tmp/claude` and a few device and log paths; Studio's `.claude/settings*.json`, `.claude/skills` and `.claude/hooks` are explicitly write-denied, even inside the working directory.
- The loaded project instructions are `/home/fahad/studio/CLAUDE.md` (the "YouTube automation (Story Studio)" text). No CLAUDE.md from the forbidden folder appears in context.
- The `.claude/skills/` folder holds 51 Studio skills (listed in 04). They show in the skill list and none was loaded during this bootstrap.

## Global versus project configuration

| Global (applies in any folder) | Project (only when started in Studio) |
|---|---|
| `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.claude/skills`, `~/.claude/rules`, plugins and their SessionStart hooks | `/home/fahad/studio/CLAUDE.md`, `/home/fahad/studio/.claude/skills/*`, `.claude/hooks/studio_guard.py` (present but not registered, see 04) |

## Findings in user settings (`~/.claude/settings.json`, read for these keys only)

| Key as written | Documented key | Effect in 2.1.332 |
|---|---|---|
| `permissions.additional_directories: ["/home/fahad"]` | `permissions.additionalDirectories` | **Not applied** (VERIFIED: `/home/fahad` is not in the sandbox write list). **Latent risk:** if anyone "fixes" the spelling, the whole home folder, forbidden folder included, becomes a working directory. |
| `permissions.default: "allow"` | `permissions.defaultMode` | undocumented key, presumably ignored (INFERRED) |
| `blockReadsOutsideWorkingDirectories: true` (top level) | the docs describe `permissions.blockWritesOutsideWorkingDirectories` and a read block | placement and effect UNVERIFIED |
| `sandbox: {enabled: true, allowUnsandboxedCommands: true}` | as documented | active |

No managed settings exist (`/etc/claude-code/` is absent).

## Safe startup design

1. Always start Studio sessions with `bash /home/fahad/studio/tools/claude-studio.sh` from a terminal. Never type a bare `claude` in another folder and then `/add-dir` or `cd` to Studio: the wrong instructions and skills are already loaded by then.
2. The first command in every new session is `pwd -P`; stop unless it prints `/home/fahad/studio`.
3. Optional, owner decision: a shell alias such as `alias studio='bash /home/fahad/studio/tools/claude-studio.sh'` in the owner's own shell profile (not changed by this task).
4. Never add `/home/fahad` (or any parent of the forbidden folder) as an additional directory.
