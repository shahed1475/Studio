# ADR 0001: one record writer and cloud tests, files stay the truth
- **Date:** 25 Oct 2026. **Status:** accepted by the owner at Checkpoint 3.
- **Context:** about 15 modules write `meta.json` directly; a stale-write bug was found on 24 Oct; there are no cloud tests; money is limited to the OpenRouter credit.
- **Decision:** add `records.py` (atomic write under a file lock, merge semantics), move the writers over in small steps, add GitHub Actions for `pytest`, and read per-studio settings from one profile file.
- **Alternatives:** SQLite (large migration, breaks every tool that reads files, risk to the records); cloud tests and backup only (does not fix the writers).
- **Consequences:** no new cost; the file format is unchanged; one more module to maintain; a code test now forbids direct writes; the lock must be tested across containers on the server.
