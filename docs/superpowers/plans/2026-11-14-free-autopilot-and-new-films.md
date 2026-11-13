# Free Autopilot, Kappa rebuild and two new films: plan (14 Nov 2026)

> **For agentic workers:** use superpowers:executing-plans. Steps are checkboxes. Owner orders of 14 Nov 2026 are the spec.

**Goal:** the channel posts steadily without paid credit, Kappa gets real plus AI pictures and a long film, Ronaldo gets a 20 minute film, and each step is proved by a real check.

**Architecture:** reuse what exists (Autopilot, `llm.free_only`, `ccbuild.py`, `ccdoc`, `studiochecks`, gate). Change code only where a measured fault is found, each change with a test, an `agenteval` case and a mutation check.

**Spec:** the owner's messages of 14 Nov 2026 (Kappa Short rebuilt with real and AI pictures; a Kappa long film; a 20 minute Ronaldo film; free tools only; first push one video and check Autopilot; free options without questions when OpenRouter is empty).

## Global constraints
- Never publish publicly without the owner's word; uploads stay private with a scheduled time. Kappa and Ronaldo stay held drafts until the owner has looked.
- Facts only from fetched passages (claim ledger). A living person (Ronaldo): neutral, sourced, no invented quotes, no AI face of him, no match footage; real photos only under a free licence with credit.
- Free tools only: edge-tts voice, Cloudflare free pictures (FLUX.2 klein, Apache-2.0), Commons photos, code-drawn data cards, Blender and ffmpeg on this PC. CapCut has no automation hook and is not used. The Adobe connector makes still designs only and is not needed.
- A change to the deployed studio needs a passing test run first and the owner's yes before deploy.

## Findings so far (evidence)
- Autopilot: `pace_guard` held every Short from 9 Nov ("Held: schedule"). Owner told me to switch it off; done 14 Nov (backup `autopilot.json.bak-before-paceguard-off-14nov`). Kitsune then took the 14 Nov 18:00Z Short slot (status ready).
- Free mode already exists and is ON (`llm.json`: enabled false, free true, free_review true, ai_art false, free_art true). Credit floors do not apply in it.
- But on 13 Nov the review role made 97 calls (375k output tokens), several free models "did not return JSON", videos ended `unreviewed`, and the balance still fell $0.28 to $0.06 (some "free" models are billed or a paid path ran). Free mode is unreliable at that call volume.
- The VPS Ollama holds gemma4, dolphin3, deepseek-r1:8b and qwen2.5vl:3b (vision): free and unlimited, but untested for review quality and CPU speed.
- No Google API key is used by the studio (YouTube uses OAuth in production mode, 23 days old, check passed 13 Nov). The "expired key" notice has not been found in the dashboard or logs.

## Tasks
- [x] A1 Kitsune and Tortoise trimmed to 55 s and 53 s, "Subscribe", dead air gone; gate PASS; approved and released.
- [x] A2 Kappa and Ronaldo put on hold at the owner's request.
- [ ] A3 Prove Autopilot: Kitsune upload should appear about 2 h before 14 Nov 18:00Z (`upload_check` in its record, `list_videos` shows video_id). Report the real API read-back; if nothing happens by 17:00Z, read the tick log and fix the cause.
- [ ] B1 Measure free mode: count calls per video by role, JSON failures per model, and find where dollars are still charged (`data/llm_usage.json` per model, OpenRouter pricing of each free model used).
- [ ] B2 Design the chain OpenRouter free, then VPS Ollama (`format: json`), then rules only, with a per-video call budget and a stop when a model fails JSON twice. Test with fakes that refuse what real models refuse; `agenteval` case and mutation check. Owner's yes before deploy.
- [x] C1 Kappa Short: spec uses Cloudflare AI set plus two real Commons photos (golden kappa statue, Kappabashi mascot), credits in the description (`ccbuild.pictures_line`, 2 new tests, 19 pass). Build runs; stays held.
- [ ] C2 Kappa long film (8 to 10 min): research (Wikipedia Kappa, Britannica, Toriyama Sekien plate, Kyosai), script from passages, chapters, pictures from Cloudflare free plus Commons, build, gate, held draft.
- [ ] D1 Ronaldo film research: fetch Wikipedia, FIFA and press passages into `docs/studio/ronaldo/src`, chapters and stats table with a passage for every number.
- [ ] D2 Ronaldo film script (about 3,000 words for 20 minutes), code-drawn charts, Commons photos with credits, Cloudflare art only for places and objects. Build, gate with listen check, held draft. The studio's reviewer warns above 10 minutes (`doc_length`); this is the owner's choice.
- [ ] E1 Growth check with real numbers (`growthdata`, `diagnose`): uploads per week, sameness, packaging, views per video. No promise of growth.

## Review focus
- A free model that returns text instead of JSON must never count as a pass (it is `unreviewed`).
- A real photo must carry author, licence and link in the description or it is not used.
- Two renders of one folder at once corrupt the audio (happened 14 Nov): one render per folder, exit code logged.

## Needs the owner
Deploy of any code change; whether a 20 minute film is wanted given the 8 to 10 minute rule; a Gemini free key from Google AI Studio only if a fourth free tier is wanted; looking at Kappa and the Ronaldo film before any release.

## Added 14 Nov (owner: footage rights, free review, no waiting, A2A)
Research record: docs/studio/COPYRIGHT_AND_REVIEW_RESEARCH_2026-11-14.md (sources, passages, labels).
- [x] F1 Research done: YouTube fair use and licence pages read in Chrome; Content ID, OpenRouter limits, structured outputs, NASA, Library of Congress, A2A from official pages (search or fetch summaries marked PARTIALLY_VERIFIED).
- [ ] F2 Footage ladder in the playbooks: own art and 3D, public domain and CC0, CC BY with credit, US government works with credit, nothing else; fair use is never chosen by Autopilot. `agenteval` case: a credit with an unknown or YouTube-downloaded source is refused; mutation check. No detection-evasion edits, ever.
- [ ] G1 Free review chain in `llm.py`: deterministic gate, then Ollama JSON-schema opinion, then free OpenRouter with `require_parameters`; bad JSON is `unreviewed`; one retry; call budget per video. Tests with fakes that refuse what real endpoints refuse; `agenteval` case; mutation check.
- [ ] G2 Autopilot approves alone when every rule passes and no model raises a blocker (`approved_by: autopilot-free`); never records the owner's name; `facts_open` and duplicate rules unchanged.
- [ ] H1 A2A adapter over `agentbus.py` (Agent Cards for the agents, `message/send` posts a task, `tasks/get` reads it); reuse `hub/a2a.py` from `feature/hub` after a security review; loopback only.
- [ ] H2 Deploy of F2, G1, G2, H1: tests green, `deploy/deploy.sh dry-run-first`, `deploy/clean_check.sh`, no restart during a render. The branch is 170 commits ahead of main: the dry run must list what would change before anything ships.
- Mistake log: on 14 Nov I overwrote the existing `grade.py` (used by `ccdoc.py`) and its tests without reading them; restored from git, my looks moved to `filmgrade.py`; 57 tests pass.
