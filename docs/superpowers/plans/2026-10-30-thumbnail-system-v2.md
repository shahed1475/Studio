# Thumbnail system v2: unique, curious, never the same twice (plan, 30 Oct 2026)

> **For agentic workers:** TDD, one task at a time; read each test result before the next.

**Goal:** Every documentary thumbnail has a distinct composition, a concrete anchor and one honest curiosity gap, differs from the channel's recent thumbnails, passes legibility and safe-zone checks, and keeps a small brand family. Built in the repo only: **not deployed and not pushed** (the owner's instruction on 30 Oct).

**Spec:** `docs/studio/THUMBNAIL_CURIOSITY_RESEARCH_2026-10-30.md`.

**Architecture:** `thumbstyle.py` holds eight composition archetypes drawn with Pillow (foreground line, big number, legend|record split, pointer, redacted word, corner stack, plus the three classic layouts that already exist), colour families per video kind, and checks (words, title overlap, safe corner, text contrast at phone size). `thumbvariety.py`-style functions inside it pick archetypes by the curiosity device found in the words and by distance from recent thumbnails (a small signature per image). `thumbnail.make_art` uses it; the old layouts stay as archetypes. The hook prompt gets the research rules.

## Global constraints
- Pillow only, fonts already shipped in `static/fonts` (no new font, no new dependency, no network).
- Honest: a device is used only when the video supports it (a year or number in the hook, a choice only when the hook offers two answers, a pointer only on a picture the video shows); text 2 to 4 words (5 at most); never repeats the title's words; the bottom-right corner is kept clear.
- Existing tests for `thumbnail.py` keep passing; every new rule has an `agenteval` case and a mutation check; the creator playbook brief keeps its Never section.
- Nothing is deployed or pushed; the Cambyses documentary's new thumbnails are made here from cached pictures (no new picture, no cost beyond one vision scoring) and copied to its folder as data.

## Tasks
- [x] **T1** `thumbstyle.py` primitives and checks: `fit_line`, `badge`, `ring_arrow`, `signature(img)`, `distance(a, b)`, `check(img, hook, title)` (words, title overlap, safe corner, contrast) + tests.
- [x] **T2** Archetypes `foreground`, `bignumber`, `split`, `pointer`, `redacted`, `corner`, each `render(pictures, spec) -> Image` + one test each (size, safe corner, what makes it itself).
- [x] **T3** `device_for(hook)` (number or year, choice, question, plain), `choose(kind, hook, recent) -> list of 3 archetype names` that never repeats the most recent two, colour family per kind, `variants(folder, meta, pictures)` writing `thumbs/thumb-N.jpg` and `thumbs/variants.json` + tests.
- [x] **T4** `thumbnail.make_art` and `hook_for` use it (research rules in the hook prompt); old tests pass; `agenteval` case with mutation checks.
- [x] **T5** The Cambyses documentary: three variants on its cached pictures, scored and viewed at phone size, copied to the video folder; dashboard options show only the new ones.
- [~] **T6** Docs: runbook section, CLAUDE.md note, memory; commit locally, **no push, no deploy**.

## Not in this plan
Deploying; Shorts covers (YouTube picks a frame); new pictures; claiming the new thumbnails raise clicks.

## Status (30 Oct 2026, after the power cut)
- T1 to T4 done (code existed before the cut): `thumbstyle.py` with six compositions plus the three classic ones, `device_for`, `choose`, `variants`; `thumbnail.make_art` and `make` use it. Fixed now: `variants` could return one composition three times when it was the only one that could be drawn (test first); `make` offers only drawn thumbnails when art exists, so `test_thumbnail_art` was updated to that contract and a second test covers the new path; `_bignumber` takes a badge so a figure says what it counts; the hook prompt asks for three different honest devices (`thumbnail.HOOK_DEVICES`); `agenteval` case with four mutation checks; `playbooks/seo.md` names the rule.
- T5 done for Cambyses (data only, no code on the server): 1) SANDSTORM OR AMBUSH? (foreground, army picture) 8.0; 2) 525 BC NEVER SEEN AGAIN (big number, helmet picture) 7.7; 3) WAS THE SANDSTORM INVENTED? (corner stack, helmet picture) 6.8. A first set paired "THE BONES, 1,000 YEARS TOO OLD" with a helmet: the scorer rated its honest match 5 of 10, so it was replaced; a dig-scene picture was honest but the figure hid the digger.
- T6: docs written; committed locally; **not pushed, not deployed** (the owner's instruction).
