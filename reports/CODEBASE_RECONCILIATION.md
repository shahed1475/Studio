# Codebase reconciliation (2026-11-20)

## The three versions
| Version | Where | State (observed 20 Nov) |
|---|---|---|
| GitHub `shahed1475/Studio` main | `origin/main` | `8e060dc`, fetched today. The live HEAD equals it: 0 ahead and 0 behind. |
| **Live (authoritative)** | `/home/fahad/studio` | `8e060dc` plus 32 modified tracked files and 39 untracked entries, none committed. |
| Workshop | `/home/fahad/Desktop/Youtube-automation` | Branch `feature/footage-tool` with commit `3790d00` (not pushed) plus about 80 uncommitted files. **Not opened for this report** (owner's rule). The facts in this row come from the 20 Nov session that worked in that folder. |

So GitHub is only the base. All real divergence lives in two uncommitted working trees.

## 20 Nov changes made in live: verified in the files, by test, today
| Change | File(s) | Status | Evidence |
|---|---|---|---|
| Competitor page removed (routes, approve endpoint, News-queue gate) | `dashboard.py` | **Present and verified** | `dashboard.py` now equals HEAD (no diff). `grep competitor dashboard.py` finds nothing. `/competitor` behind login answers 303 (login). |
| Competitor files moved out | `competitor.py`, `competitor_dashboard.html`, `competitor_topics.json`, `tests/test_competitor.py`, `data/competitor_channels.json`, `data/competitor_intelligence.json` | **Present and verified** | Files are gone from their places and present as `.bak` in `backups/removed-competitor-20nov/` (10 files, sizes 353 B to 67.9 KB). |
| Competitor route tests removed | `tests/test_dashboard_routes.py` | **Present and verified** | The file still holds `+20` lines versus HEAD: the owner's `post()` helper and the ordinary News-queue test, which is kept. |
| `run._animate` takes `durations` and passes them on | `run.py` | **Present and verified** | `tests/test_animation.py` 20 of 20 pass. |
| Free mode refuses paid video clips (no fake key) | `animate.py` | **Present and verified** | New test plus a mutation check: the test fails when the refusal is removed. |
| Real-ffmpeg concat and music test | `tests/test_render_concat.py` (untracked) | **Present and verified** | 3 of 3 pass. The live `render.py` is HEAD's and was never affected by the music bug. |

## Other live edits (author: the owner or another session; reviewed, not reverted)
| Change | Status | Note |
|---|---|---|
| `reviewer.relevant_source`: IDF weighting, sentence windows, page-furniture filter, biography key terms; `REVIEW_TEXT_CHARS` 12,000 to 20,000 | Present, covered by `tests/test_reviewer.py` (passes) | Written for the 21-minute Ronaldo film. |
| `llm.parse_json` rewritten as a brace-depth scan | **Present, defect found** | It ignores braces inside JSON strings, and it dropped the old "outermost braces" fallback. Repaired in Phase 4 (see `FREE_MODEL_OPTIMIZATION.md`). |
| `agentbus`: a closed task keeps its outcome on a late retry | Present, tests pass | |
| `channelwatch`: digest files only `????-W??.json` (craft.json had emptied the ideas) | Present, `tests/test_channelwatch.py` passes | |
| `upload.py`: a record without title or tags is no KeyError | Present, `tests/test_upload_guard.py` passes | |
| `video_packaging_rules.py` (untracked), imported as `packaging` by autopilot, fixer, guardian, writerbench | **Incomplete rename** | `packaging.py` still exists and is byte-identical. Harmless now. Deleting the old file is left for the commit step. |
| `animate.py` free-mode parallax in `animate_scenes`; `tools/footage/clipgen.py` +21 lines | Present, tests pass | |
| `requirements.txt` adds PyYAML (deploy test) | Present | |
| `tests/test_free_mode_real.py` (untracked) | Present, part of the suite | |
| `=1.18` (0-byte file in the project root) | Stray | It is what a shell does with `pip install x>=1.18` typed without quotes. Safe to delete; left for the owner. |
| `*.bak*` copies of `autopilot.json`, `llm.json`, `token.json`, `topics.json` | Owner backups | Never commit (`token.json.bak-21oct` holds a login token). |

## What only the workshop has (from the 20 Nov session; not re-read)
- `llm.MODE_FLAGS`, `mode()`, `set_mode()`, `paid_allowed()`, `free_allowed()`: one Free/Paid switch.
- An Autopilot `lease` lock (an O_EXCL file with a heartbeat) and skipping of `skipped` results.
- 20 to 25 minute documentaries:
  - `scriptgen`: 80 to 100 lines, 3,500 words.
  - `rules.json`: `long_min/max` 20/25.
  - `reviewer`: 2,000-word floor.
- `render.py` concat rewrite (re-encode at CRF 16, music mix fixed in that session).
- `run.py`: `format="short"` for Shorts and line-buffered stdout.

## Classification summary
- **Verified present:** all six 20 Nov live changes.
- **Defect found in live:** `llm.parse_json` (repaired in Phase 4).
- **Incomplete:** the `packaging` rename (two identical files).
- **Missing in live, present in the workshop:** one Free/Paid mode switch, the Autopilot lease lock, the 20 to 25 minute documentary settings. Phase 3 handles the documentary length in live directly, from the owner's 20 to 26 minute requirement, without copying the workshop code.
- **Conflicting:** none found in live. A merge of the workshop into live is not attempted (owner's rule). It needs its own reviewed step.
