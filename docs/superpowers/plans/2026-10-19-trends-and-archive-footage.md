# Niche Trends and Public-Domain Footage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.

**Goal:** (1) A weekly research agent that reads what performs in the niche through the official YouTube Data API and turns it into insights and original topic ideas. (2) Real moving footage for videos from public-domain collections on the Internet Archive, used under our own script and voice.

**Explicitly not built:** downloading other creators' YouTube videos or re-publishing their footage (copyright infringement, YouTube reused-content policy, YouTube terms). Research reads public metadata only (titles, views, length); it never copies video or text.

**Architecture:** `trendwatch.py` (API search with the existing OAuth token, pure summary functions, Ollama for original topic ideas) and `archive_video.py` (curated public-domain search, pick a small mp4 derivative, cut a segment over HTTP range requests, cache, write a credit line). `footage.clip_for` becomes a chain: Pexels key, then Internet Archive video, then Wikimedia image.

**Tech Stack:** google-api-python-client (installed), requests, ffmpeg, pytest.

## Global Constraints

- Only items whose `licenseurl` is a CC0 or Public Domain Mark URL, inside the collections `silent_films`, `prelinger`, `nasa`, `feature_films`, `classic_tv`, `opensource_movies` are ever used; adult-tagged subjects excluded.
- Every footage clip gets a credit line (`Title (Internet Archive, license)`) stored beside the cached file and added to the video's `credits`.
- YouTube API cost: at most 6 searches per weekly run (about 600 of 10,000 daily units); never run more than once per day.
- No em-dashes in dashboard text. No git repo: "commit" = run the whole suite.

## Review Focus

- Archive returns nothing relevant: `fetch_clip` returns `None`, the chain falls through to a Wikimedia image, nothing raises.
- Archive item has no usable mp4 or only huge files: skipped, no download over 150 MB is ever attempted.
- ffmpeg cannot read the remote file or times out: returns `None` and removes partial output.
- YouTube quota exhausted or token missing: `trendwatch.run` records an error in the digest and exits cleanly.
- A trends digest never writes titles into the topic queue verbatim (ideas must be original wording).

---

### Task 1: Trend research (`trendwatch.py`)

**Files:** Create `trendwatch.py`; Test `tests/test_trendwatch.py`

**Interfaces:**
- Produces: `iso_seconds(duration: str) -> int`; `summarize_videos(items: list[dict]) -> dict` (`median_views: int`, `short_share: float`, `avg_minutes: float`, `patterns: dict[str, int]` with keys `question`, `real_story`, `number`, `colon`); `search_niche(queries: list[str], yt=None) -> list[dict]` (each `{id, title, channel, views, seconds, published, url}`); `run(now=None, yt=None) -> Path` writing `data/trends/YYYY-Www.json` and appending original ideas to `topics.json`.
- Consumes: `scriptgen._chat`, `upload.Credentials`.

- [ ] **Step 1: Failing tests:** `test_iso_seconds` (`PT43S`→43, `PT10M13S`→613, `PT1H2M`→3720), `test_summarize_videos_numbers_and_patterns`, `test_summarize_empty`, `test_run_writes_digest_and_original_ideas` (fake `yt`, monkeypatched `scriptgen._chat`; ideas that exactly equal a scraped title are dropped), `test_run_survives_api_failure` (fake `yt` raising → digest has `error`, topics untouched).
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement (queries: the niche seeds plus the next two queue topics, 6 maximum, `order=viewCount`, `regionCode=US`, `type=video`). **Step 4:** run, expect PASS; run once for real.

### Task 2: Public-domain video (`archive_video.py`) and the footage chain

**Files:** Create `archive_video.py`; Modify `footage.py`, `config.py` (`ARCHIVE_VIDEO`, `DOC_VIDEO_CLIPS`), `run.py` (credits for Shorts, optional video clips in documentaries); Test `tests/test_archive_video.py`

**Interfaces:**
- Produces: `build_query(keywords: str) -> str`; `relevant(doc: dict, keywords: str) -> bool`; `pick_file(files: list[dict]) -> dict | None`; `clip_offset(length: float, seconds: float, seed: str) -> float`; `fetch_clip(query: str, seconds: float = 10.0) -> Path | None`; `footage.credit_for(path: Path) -> str | None`.

- [ ] **Step 1: Failing tests:** `test_build_query_is_public_domain_only` (contains both license URLs, the collections, and the adult exclusion), `test_relevant_needs_a_keyword_in_title_or_subject`, `test_pick_file_prefers_h264_mp4_under_cap` (skips 200 MB and non-mp4), `test_pick_file_none_when_nothing_usable`, `test_clip_offset_inside_video`, `test_credit_for_reads_sibling_txt`, `test_clip_for_chain_order` (Pexels key absent: archive result wins; archive `None`: Wikimedia image).
- [ ] **Step 2:** run, expect FAIL. **Step 3:** implement; `fetch_clip` uses `ffmpeg -ss OFFSET -i https://archive.org/download/ID/FILE -t SECONDS -an -vf scale=-2:1280 out.mp4` with a 120 s timeout. **Step 4:** run, expect PASS; fetch one real clip and look at a frame.

### Task 3: Dashboard and schedule

**Files:** Modify `dashboard.py` (`/api/autopilot` includes the latest trends digest, job `trends`), `dashboard.html` (Niche trends section), `run.py` (`trends` command), `scripts/story-newswatch.service` (run trends after the news digest), `README.md`

- [ ] **Step 1:** Implement; show median views, share of Shorts, common title patterns, the top videos as links, and the original topic ideas that were added; "Check now" button.
- [ ] **Step 2:** Verify in the browser; run the whole suite.
