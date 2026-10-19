# SDD ledger — plan: docs/superpowers/plans/2026-10-19-subtitles.md
Pre-flight: Task 2 consumes Task 1 (build_cues/to_srt/to_ass); Task 3 consumes tts.timings (Task 2) and subtitles.burn; Task 4 consumes meta['subtitles'] (Task 2). Names match. Clean.
Ruling: no soft YouTube caption upload (needs new OAuth scope + re-consent, doubles text with burned-in) — cost if wrong: SRT is saved, upload can be added later.
Task 1: complete (tests: pytest tests/test_subtitles.py -> 8 pass)
Task 2: complete (tests: pytest -> 104 pass; sample frame checked, outline thickened to 4)
Task 3: complete (tests: pytest -> 109 pass)
Task 4: complete (tests: pytest -> 111 pass; Subtitles panel renders, 0 console errors)
Task 5: complete (README). Pending real-world check: Delphi doc finish_video + burn running in background.
