# 00 — Startup root cause

Date: 2026-11-26. Session: Claude Code 2.1.332, started in `/home/fahad/studio` (verified: `pwd` and `pwd -P` both `/home/fahad/studio`).
Status: COMPLETE (diagnosis). Evidence labels: VERIFIED (seen in this session), DOCUMENTED (official Claude Code docs), INFERRED (follows from both, not observed directly).

## Summary

The earlier failed session was, in all likelihood, **started with its working directory set to the forbidden folder** (`/home/fahad/Desktop/Youtube-automation`), not through the approved launcher. Claude Code takes three things from the directory it starts in:

1. **Project instructions**: CLAUDE.md is loaded from the working directory and every parent (DOCUMENTED, code.claude.com/docs/en/memory).
2. **Project skills**: `.claude/skills/` in the working directory, plus parents up to the repository root (DOCUMENTED, code.claude.com/docs/en/agent-sdk/skills).
3. **Write scope**: sandboxed commands may write only to the working directory, the temp directory and added directories (DOCUMENTED, code.claude.com/docs/en/settings-reference, sandbox section). VERIFIED in this session: the sandbox write allow-list is `.` (the working directory), `$TMPDIR` and a few device and log paths. `/home/fahad/studio` is writable here only because it *is* the working directory.

So a session started in the forbidden folder gets the wrong folder's instructions and skills, and cannot write to Studio. These are exactly the two symptoms reported.

## Was the launcher defective?

No. `tools/claude-studio.sh` runs `cd /home/fahad/studio` before anything else and `exec`s `claude` from there (VERIFIED by reading the source; `--check` passed in this session). The launcher cannot help a session that is started without it, with a bare `claude` typed in another folder. Its own header (25 Nov 2026) records that this already happened once.

## What could not be verified

- How the earlier session was actually started. Its transcript, and the forbidden folder's instructions and skills, were deliberately not opened (mission rule 0.1). Classification: **likely cause, strongly supported**, not proven.

See 01 to 05 for the evidence and the proposed repairs.
