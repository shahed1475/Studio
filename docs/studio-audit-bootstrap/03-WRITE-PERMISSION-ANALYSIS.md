# 03 — Write-permission analysis

Status: COMPLETE.

## Facts checked (VERIFIED)

| Possible cause | Result |
|---|---|
| Unix ownership and mode | `/home/fahad/studio`, `tools/`, `.claude/` are `fahad:fahad 775`; the session user is fahad. **Not the cause.** |
| Symlinks | Studio, `docs/` and the launcher resolve to themselves. Not the cause. |
| Managed settings | none (`/etc/claude-code/` absent). Not the cause. |
| Project settings | Studio has no `.claude/settings.json` or `settings.local.json`. Not the cause. |
| Sandbox write scope | allow-list = working directory + temp. **Cause, when the working directory is not Studio.** |
| File tools (Write and Edit) | limited to working directories (DOCUMENTED). Same cause. |
| Additional directories | `additional_directories` in user settings is misspelled and not applied, so it does not add Studio (or anything else). |
| The launcher | does not block writes; it only refuses to start. Not the cause. |

## Conclusion

When a session starts in the forbidden folder, `/home/fahad/studio` is outside every working directory. Sandboxed Bash cannot write there, and Write and Edit refuse it or ask for permission. This is the sandbox doing its job, not a defect. **Classification: likely cause (strongly supported)**; the earlier session itself was not inspected.

## Write test in this session

The bootstrap folder was created (`mkdir -p`; the physical path was re-checked). One file named `.write-test-<epoch>-<pid>` was written, read back ("ok") and removed by its exact name. The folder was empty afterwards. Result: **PASS**, with no permission or sandbox change.

## Proposed correction

None to permissions. Start in Studio (see 02, "Safe startup design").
