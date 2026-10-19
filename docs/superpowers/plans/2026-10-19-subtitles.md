# Subtitles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Every video gets readable subtitles: documentaries get burned-in captions at render time, Shorts keep theirs, existing videos can be given subtitles without re-voicing, and an `.srt` file is saved for each.

**Architecture:** `tts.narrate` already receives word timings from edge-tts; it now also writes `words.json` (`{s, e, w, i}` per word, `i` = narration line index). A new pure module `subtitles.py` turns those words into cues, SRT text and a 16:9 ASS style. `run.py` writes the files, passes the ASS to `render.render` for documentaries, and gets a `subtitles NAME [--burn]` command for finished videos.

**Tech Stack:** Python stdlib, ffmpeg `subtitles` filter (libass), existing edge-tts, pytest.

**Spec:** Conversation of 2026-10-19 ("also add subtitle with the video, it will help more to understand"). No written spec; builder calls are marked below.

## Global Constraints

- Burned-in subtitles for documentaries, white text, black outline, bottom centre, at most 2 lines of at most 42 characters, sentence case (Shorts keep their existing 3-word ALL CAPS style).
- Builder call: no YouTube caption-track upload (needs a new OAuth scope and re-consent, and would double the text next to burned-in subtitles). The `.srt` is saved in the video folder for later use.
- Never re-encode an uploaded video's file; `subtitles --burn` refuses when `meta["video_id"]` is set.
- No em-dashes in dashboard text. No git repo: "commit" = run the whole suite.

## Review Focus

- Existing video with no `words.json`: timings are regenerated from the saved script; if their total differs from the video's duration by more than 1.5 s the command aborts and changes nothing.
- A very long narration line or a line with no punctuation never yields a cue over 2 lines or over 6 s.
- Cues never overlap and never have zero or negative length.
- `--burn` never leaves a half-written `video.mp4` (write to a temp file, then replace).
- The reviewer never blocks on missing subtitles (warn only), so old videos are not stranded.

---

### Task 1: Cue builder and formats (`subtitles.py`)

**Files:** Create `subtitles.py`; Test `tests/test_subtitles.py`

**Interfaces:**
- Produces: `Cue = dict` (`start: float`, `end: float`, `text: str` with `\n` for the line break); `build_cues(words: list[dict], max_chars: int = 42) -> list[Cue]`; `to_srt(cues) -> str`; `to_ass(cues, size: tuple[int, int] = (1920, 1080)) -> str`; `timings_match(words: list[dict], video_seconds: float, tol: float = 1.5) -> bool`.

- [ ] **Step 1: Failing tests:** `test_cues_break_at_line_boundaries` (words with `i` 0 then 1 never share a cue); `test_long_line_split_into_two_line_cues` (30 words → every cue ≤ 2 lines, each line ≤ 42 chars); `test_cue_never_longer_than_six_seconds`; `test_cues_ordered_and_not_overlapping`; `test_minimum_duration_one_second`; `test_srt_format` (`"1\n00:00:00,000 --> 00:00:01,500\nHello there\n\n"` for one cue); `test_ass_has_playres_and_dialogue`; `test_timings_match`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest tests/test_subtitles.py -q`; expect FAIL (module missing).
- [ ] **Step 3:** Implement. Greedy fill: add words until the text would exceed `2 * max_chars` characters, the cue would exceed 6 s, or the line index changes; wrap into two balanced lines at the word boundary nearest the middle; end = last word end + 0.15, extended to at least start + 1.0 and capped at the next cue's start.
- [ ] **Step 4:** Run; expect all PASS.

### Task 2: Word timings saved by the voice step, files written at render

**Files:** Modify `tts.py`, `run.py` (`cmd_make`, `_produce_doc`), `config.py` (`DOC_SUBTITLES = os.getenv("YT_DOC_SUBS", "1") == "1"`); Test `tests/test_subtitle_files.py`

**Interfaces:**
- Consumes: `subtitles.build_cues/to_srt/to_ass`.
- Produces: `tts.narrate` also writes `work/words.json`; `tts.timings(lines: list[str], work: Path) -> list[dict]` (voice synthesis only, writes `words.json`, no concatenation); `subtitles.write_files(folder: Path, words: list[dict], size: tuple[int, int]) -> Path` writes `folder/captions.srt` and returns the path, and sets nothing else.

- [ ] **Step 1: Failing tests:** `test_write_files_creates_srt` (words → `captions.srt` exists, starts with `1\n`); `test_words_json_shape_roundtrip` using `subtitles.load_words(path)`.
- [ ] **Step 2:** Run; expect FAIL. **Step 3:** Implement; in `_produce_doc` build a doc ASS from the words, write it to `work/doc_captions.ass`, pass it as the `ass` argument of `render.render` when `config.DOC_SUBTITLES`, copy `words.json` to the folder before `shutil.rmtree(work)`, write `captions.srt`, and set `meta["subtitles"] = "burned"`. Same copy and SRT in `cmd_make` with `meta["subtitles"] = "burned"` (Shorts already burn theirs).
- [ ] **Step 4:** Run the suite; expect PASS. Then render a 6-second sample with the doc ASS style and look at a frame.

### Task 3: Subtitles for finished videos (`run.py subtitles NAME [--burn]`)

**Files:** Modify `subtitles.py` (`burn(video: Path, ass: Path, out: Path) -> None`, `ensure_words(folder: Path) -> list[dict]`), `run.py`; Test `tests/test_subtitle_cli.py`

**Interfaces:** `ensure_words(folder)` returns saved words or regenerates them with `tts.timings` from `meta["lines"]`, raising `SystemExit` when `timings_match` fails; `burn` encodes to `video.tmp.mp4` and replaces `video.mp4` only on success.

- [ ] **Step 1: Failing tests:** `test_ensure_words_uses_saved_file`, `test_ensure_words_rejects_mismatched_duration` (monkeypatch `tts.timings` and a fake probe), `test_burn_refuses_uploaded_video`.
- [ ] **Step 2:** Run; expect FAIL. **Step 3:** Implement. **Step 4:** Run; expect PASS. Then run the command on the real documentary and check a frame.

### Task 4: Reviewer check and dashboard

**Files:** Modify `reviewer.py` (check `subtitles`, warn), `dashboard.py` (`/captions/<slug>.srt`, `subtitles` field in the video entry, job `subtitles` allowed), `dashboard.html` (Subtitles panel); Test `tests/test_reviewer.py`

- [ ] **Step 1: Failing tests:** `test_warns_without_subtitles` (meta without `subtitles` → warn failure named `subtitles`), `test_subtitles_ok_when_burned`.
- [ ] **Step 2-4:** Implement and run; panel shows "Burned in" or "None", a "Add subtitles" button (disabled when uploaded or a job runs), and a link to download the `.srt`. Verify in the browser.

### Task 5: Docs

- [ ] README section; run the full suite and `systemd`-independent checks.
