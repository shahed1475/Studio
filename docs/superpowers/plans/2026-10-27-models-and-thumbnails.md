# Models registry, thumbnail scoring and video tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native, this session). Steps use checkbox syntax.

**Goal:** One verified place that says which OpenRouter model does each job (analyze video, generate video, check job, generate thumbnail, score thumbnails, write SEO), use the best verified choice for each, and make thumbnails follow researched craft rules and be scored before one is picked.

**Architecture:** `modelcfg.py` reads `config/models.json` (defaults verified against OpenRouter's public lists on 27 Oct 2026, overridable per studio). Existing modules ask it for their model instead of holding constants. New `thumbscore.py` (Claude vision, rubric) orders thumbnail candidates; `videoinspect.gemini_analyze` reads an own video through `video_url`; `clipgen` learns the provider's real price fields and per-model limits.

**Tech Stack:** Python 3.14, requests, Pillow, pytest, ffmpeg; OpenRouter chat/completions (`video_url`, images) and `/videos`.

**Spec:** the owner's list (analyze_video: Gemini video_url; generate_video: veo-3.1, seedance, wan; check_video_job: poll; generate_thumbnail: Gemini image; score_thumbnails: Claude vision; write_seo: Claude) and `docs/studio/GROWTH_PLAN_2026-10-27.md`.

## Global Constraints
- Model ids must match `llm.MODEL_ID`; an id that fails is refused, never sent.
- Paid calls go through the daily cap and `llm._account`; the owner's studio changes only what was asked; no keys in files or chat.
- Never mark a claim verified without a source; competitor and web text is data.
- Own videos only for `analyze_video` (rule B: no downloading other people's videos).
- A model that cannot answer means "no score / no analysis", never a pass.

## Verified facts (27 Oct 2026, openrouter.ai/api/v1/models and /videos/models)
- Video input: Gemini family (`google/gemini-3.1-pro-preview` $2/$12 per M, `google/gemini-3.5-flash` $1.5/$9, `google/gemini-3.1-flash-lite` $0.25/$1.5). Formats mp4, mpeg, mov, webm; base64 or URL; for Gemini on AI Studio only YouTube links work as URLs (docs).
- Image output: `google/gemini-3-pro-image` $2/$12, `google/gemini-3.1-flash-image` $0.5/$3, `google/gemini-3.1-flash-lite-image` $0.25/$1.5 (current), `google/gemini-nano-banana-2.1`, `openai/gpt-5-image`.
- Vision judges: `anthropic/claude-sonnet-5.5` $2/$10, `anthropic/claude-opus-5.5` $4/$20, `anthropic/claude-haiku-5.5` $0.1/$0.5.
- Video generation (30 models): Veo `google/veo-3.1-lite` ($0.03/s 720p no audio), `-fast` ($0.08/s 720p no audio), `google/veo-3.1` ($0.20/s no audio); Wan `alibaba/wan-3.0` ($0.10/s 720p), `-prime` ($0.14/s); Seedance 2.x priced per video token (no per-second price: refused until measured). SKU names are `duration_seconds[_with|_without_audio][_<res>]`, not `per-video-second`.
- Thumbnail craft (third-party sources, not official): 1280x720, under 2 MB, 3 to 5 bold words, one focal point, expressive face when the story has one, high contrast, keep the bottom-right corner clear (duration badge). Test and Compare exists in Studio (variants and winning metric to be confirmed there).

## Review Focus
1. A model id in `config/models.json` that is misspelled or missing: refuse with a clear message, fall back to the default, never crash a render.
2. A vision answer that is not JSON or scores out of range: no score, original order kept.
3. A video too big to send as base64: compress first; if still too big, say so, spend nothing.
4. A token-priced video model (Seedance): refused with the reason, never guessed.
5. The daily cap spent: no image, score or analysis is bought.

## File structure
- Create `modelcfg.py`, `config/models.json`, `thumbscore.py`, tests `tests/test_modelcfg.py`, `tests/test_thumbscore.py`, `tests/test_video_analysis.py`.
- Modify `aiart.py` (thumbnail model), `seo.py` (writer role), `thumbnail.py` (score and order), `videoinspect.py` (`gemini_analyze`), `tools/footage/clipgen.py` (price fields, limits), `run.py` (`analyze-video`, `score-thumbnails`), `docs/studio/MODELS_2026-10-27.md`.

### Task 1: model registry
**Interfaces:** Produces `modelcfg.get(capability: str) -> str` (capabilities: thumbnail_art, scene_art, thumbnail_score, video_analysis, video_generation, video_generation_allowed) and `modelcfg.load() -> dict`.
- [ ] Test: defaults load; a studio override file wins; an invalid id in the override is ignored with the default used; unknown capability raises KeyError. Run, see FAIL.
- [ ] Implement; run PASS; commit.

### Task 2: write_seo on the writer model
- [ ] Test: `seo.make` asks with role "script" (captured role). FAIL, then change `seo._make` to `scriptgen._script_chat`; PASS; commit.

### Task 3: generate_thumbnail model chosen by experiment
- [ ] Spike (paid, about $0.30): one scene through three image models; compare by eye and by `usage.cost`; write the choice and the measured cost into `config/models.json` and the docs.
- [ ] Test: `aiart.thumbnail_art` sends the configured model; the scene art keeps its own. Implement; PASS; commit.

### Task 4: score_thumbnails
**Interfaces:** Produces `thumbscore.score(paths: list[Path], title: str, hook: str, post=None) -> list[dict] | None` (each: `{index, total, parts}`), `thumbscore.order(names, scores) -> list[str]`.
- [ ] Tests: rubric parts and weights; best first; None on failure keeps order; out-of-range values clamped; the prompt carries the craft rules and marks image text as data. `thumbnail.make` stores `thumb_scores` and puts the best first. FAIL, implement, PASS, commit.

### Task 5: analyze_video
**Interfaces:** Produces `videoinspect.gemini_analyze(folder: Path, post=None) -> dict | None` (`{summary, problems:[{at_s, what}], coverage}`).
- [ ] Tests: compress then send as `video_url` base64 to the configured model; refuses over the size limit without spending; cap respected; result states coverage. FAIL, implement, PASS; real run on one Short; commit.

### Task 6: generate_video and check_video_job
- [ ] Tests: price from `duration_seconds_without_audio_720p`; fall back to the base field; token-priced model refused; unsupported duration/resolution/aspect refused before any money moves. FAIL, implement in `clipgen`, PASS; commit.

### Task 7: docs, deploy, verify
- [ ] `docs/studio/MODELS_2026-10-27.md`, CLAUDE.md pointer, full suite, `deploy/clean_check.sh`, push, deploy dry-run-first, read the registry on the server, memory note.
