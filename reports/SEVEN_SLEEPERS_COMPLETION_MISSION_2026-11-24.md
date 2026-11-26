# Seven Sleepers completion mission (24-25 Nov 2026)

Owner's order of 24 Nov 2026 (~15:45 UTC): research Kaggle properly, reuse the owner's downloaded models where lawful, and finish the Seven Sleepers documentary (20-23 minutes, fixed pictures, two-family fact-check, 48 kHz, held for the owner). Work only in ~/studio; the Desktop workshop was never read. Nothing committed, pushed, deployed, uploaded, scheduled or published. Times UTC.

## Checkpoint log (newest last; resume from the first unticked line)
- [x] 15:47 Skills loaded from ~/studio/.claude/skills (video finish, fact-check, quality gate, QA, Kaggle, inventory, compatibility, routing, licence, checkpoint).
- [x] 15:50 **Stale approval withdrawn.** Record: approved false, approved_by removed, hold true with reason; the old approval is kept in `approval_history` (review 601729f7b15a, video sha256 f16337c67b2eaca8..., the never-run picture check). visual_check corrected to ok false / ran false. Backup of the record before the change: session scratchpad `ss_meta_before_withdraw.json`. Autopilot's own planner, run dry: no action for this film, with pause_scheduling on AND with it off.
- [x] Kaggle research (section 1), permission request drafted (NOT sent): reports/KAGGLE_COMMERCIAL_USE_PERMISSION_REQUEST.md
- [x] Model inventory: reports/DOWNLOADED_MODEL_INVENTORY_2026-11-24.md (118 entries; three Z-Image route files verified Apache-2.0 by SHA-256)
- [x] Compute options: reports/COMPLIANT_GPU_COMPUTE_OPTIONS_2026-11-24.md (chosen route: Cloudflare free day for the film's pictures, this PC for the rest; Z-Image on this PC for the Short's fix)
- [x] Actual MP4 inspected (section 3): every finding of the last report confirmed, plus scenes 74-77 (coins) and the exact replay pattern.
- [x] Script version 2 written: data/rescript/ss_script2.py (ss_script.py untouched): 109 lines, 16 chapters, 3,572 words (+532), max 43 words a line, estimated ~1,290 s (21.5 min).
- [x] Code: per-film drawing limit `art_limit` (run._art_limit, ceiling 64), tests/test_art_limit.py (3), agenteval case + 2 mutation checks.
- [x] Full suite 16:30 UTC: 3,090 passed, 11 skipped, 0 failed (308 s).
- [x] Render script data/rescript/ss_redo2.py (refuses unless the checked hash, a clean fact-check and an open Cloudflare day; state file data/rescript/ss_redo2_state.json).
- [x] Two-family fact-check of version 2 (data/rescript/ss_factcheck2_24nov_run1..4): run 1 flagged 6 (3 fair, fixed; 3 refuted by exact passages), run 2 flagged 5 (1 fair, line 5 fixed; 0,1 "no claim", 41 and 91 refuted), run 3 BLOCKED (only nvidia answered: not a pass), **run 4 PASSED: 0 flagged of 109 lines, lines_sha 912837e164f4**, every part two families (nvidia+google x3, nvidia+particle x1), served names match the asked models, each judge returned an explicit empty list. Backups: ss_script2.py.bak-before-run1-fixes.
- [x] Backups: output_old/doc-did-seven-sleepers-before-redo2-24nov (+ .inventory.sha256, video f16337c6...), output_old/mary-celeste-ugc-short-before-p01-fix-24nov (+ .sha256).
- [x] ss_redo2.py tested in the worker at 16:18: passed the hash and fact-check gates, refused on the spent Cloudflare day (as designed).
- [x] **Render scheduled: user timer ss-redo2-render.timer at 2026-11-25 00:02 UTC** (`systemctl --user list-timers`). If the PC rebooted before then (the timer is transient), run by hand after 00:00 UTC:
  `docker --context default exec -d -w /app studio-worker sh -c 'PYTHONPATH=/app python data/rescript/ss_redo2.py 912837e164f4 >> logs/seven-sleepers-redo2.log 2>&1'`
  Progress: data/rescript/ss_redo2_state.json and logs/seven-sleepers-redo2.log. A cut mid-render: run the same command again (voice and pictures cached).
- [x] **Mary Celeste Short fixed (held, unapproved).** Opening picture drawn on this PC's GTX 1050 Ti with Z-Image Turbo (files verified Apache-2.0): seed 11 (839 s) had two masts but gold pseudo-letters on the hull and figure-like shapes on deck, rejected; seed 23 with a stricter prompt (849 s, cache/cc/z-833de3f6aa0e7551.png, kept untouched) had two masts and an empty deck but gold pseudo-numbers on the stern, painted out with ffmpeg delogo into cache/cc/z-833de3f6aa0e7551-retouched.png. Rebuilt 16:22-16:27 UTC in the worker from data/specs/staging/mary-celeste-ugc-short-v2 (ccbuild --replace; only line 1's picture and the credit line differ from the inbox spec; 11 pictures and the voice from cache). Result: 60.43 s, 1080x1920, 30 fps, AAC **48,000 Hz**, 13/13 studio checks ok, video sha256 dc3ebe5d31ae116c...; frames at 0.5, 2 and 4 s looked at: two-masted ship, no lettering, hook text intact. The inbox spec still names p01 (specrun keeps its "built" state and does not rebuild).
- [ ] Render at 00:02 UTC 25 Nov (after the free picture day resets), inspect the new MP4, review, keep held

## 1. Kaggle: what was read (24 Nov 2026, owner's Chrome, signed out, read only)
| Source | What it says |
|---|---|
| kaggle.com/terms (version June 22, 2025, active) | "You will only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party"; one account only; no scraping |
| kaggle.com/aup (June 22, 2025) | no use of resources for "server farming", "activity unrelated to ML data science"; no circumventing the Services |
| kaggle.com/docs/notebooks | 12 h execution for CPU/GPU sessions, 9 h TPU; 20 GB saved in /kaggle/working; 4 CPU cores, 30 GB RAM; extra 15/30 GPU h a week only for linked Colab Pro/Pro+ (experimental); the page still describes a P100 |
| kaggle.com/docs/efficient-gpu-usage | weekly GPU quota "30 hours or sometimes higher depending on demand and resources"; interactive sessions idle out after 60 min |
| discussions/product-announcements/735239 (Kaggle staff) | P100 retired 15 Sep 2026; T4 x2 = two GPUs, 16 GB each; L4 only in a small set of competitions |
| kaggle.com/contact | no category for commercial-use permission |
| kaggle.com/notebooks | public code listing; the account's own quota is not visible signed out |

| Question | Answer from the sources |
|---|---|
| 1. What Kaggle technically permits | GPU notebooks (T4 x2), 12 h sessions, ~30 h a week, 20 GB output, uploads as private datasets/models |
| 2. What the current terms permit | internal, personal, non-commercial use for ML data science |
| 3. What needs written permission | any commercial use, including assets for a monetised channel (the terms allow only non-commercial use; nothing offers a commercial exception) |
| 4. What is clearly prohibited | more than one account, scraping, crypto-mining, server farming, activity unrelated to ML data science, circumventing limits |
| 5. Uncertain, ask Kaggle | whether a one-person creator's inference counts as "internal"; whether media generation counts as ML data science; rights in outputs; uploading model weights |
| Can the owner run downloaded models on Kaggle for monetised videos? | **No, not without Kaggle's written permission.** The terms do not distinguish training from inference; the "non-commercial" and "ML data science" limits decide it. Personal benchmarking or evaluation of a model fits; producing deliverables for the channel does not. |

## 3. The MP4 as found (inspected, not assumed)
- output/doc-did-seven-sleepers-hide-in-a-cave-and-awaken-/video.mp4: 1,095.1 s, 1920x1080 H.264, AAC 44,100 Hz, sha256 f16337c67b2eaca8..., unchanged since 02:13 UTC 24 Nov.
- One frame from the middle of each of the 93 scenes looked at (93 frames; nothing else watched):
  - scene 52: AI drawing with garbled English-looking lettering carved on stone (visual note "carved inscription on wall");
  - scene 54: AI drawing of invented Arabic-style script (note "Arabic calligraphy");
  - scene 67: an Openverse photo "Israel-06731 - Damascus Gate", i.e. Jerusalem, for a line about a gate of the old town of Damascus;
  - from scene 59 on, the pictures of scenes 9 to 32 play again in order (e.g. 70=10, 75=15, 92=32), so scenes 74 to 77 show Greek coins for lines about Susan Cooper, Camilleri, Buchan and Norwegian idioms.
- Cause of the replay: the film drew its standard 16 pictures; at 65% variety it was over the 55% floor that unlocks 12 more drawings, so everything after the reserve was used up replayed (footage.scene_images "least recently used").
- Cause of 44.1 kHz: sfx.apply resampled the finished soundtrack (fixed earlier today, tests/test_sfx.py).

## After the render (next session or the owner)
1. `cat data/rescript/ss_redo2_state.json` (last stage "rendered") and `tail logs/seven-sleepers-redo2.log`. "refused" or no state: read the reason, run the command above.
2. ffprobe the new video.mp4: duration (expected about 1,250-1,330 s), 1920x1080, 48,000 Hz audio, sha256 different from f16337c6...
3. `.venv/bin/python studiochecks.py video doc-did-seven-sleepers-hide-in-a-cave-and-awaken-` (full decode, captions, dead air, frozen pictures).
4. One frame per scene (109) as contact sheets: scenes 57-58 (old 52/54) without lettering, old 67 (now 75) Mount Qasioun not Jerusalem, no run of replayed pictures in the last third, record `footage` unique/drawn.
5. `run.py review` with the two-family AI review; a missing second family is BLOCKED, never a pass. The film stays held (hold true, approved false) for the owner.

## 19:20 UTC: pre-render checks and the inspection tool (no Kaggle used)
- Pre-flight for the 00:02 UTC render: RAM 12 GB available, /home 233 GB free, Autopilot idle, both containers healthy, timer ss-redo2-render armed with lines hash 912837e164f4, free_art on (cap 9,000), Cloudflare keys present (names only).
- ss_redo2.py now waits up to 20 minutes for an Autopilot pass that holds the lock at the start (before: it would have died with Busy before rendering); backup ss_redo2.py.bak-before-lock-wait; dry-run 19:12 still refuses only on the spent Cloudflare day.
- After the render, one command: `.venv/bin/python data/rescript/ss_inspect2.py` (state, ffprobe incl. 48 kHz, new sha256, studiochecks, record: 109 lines / hold / approved false / footage, contact sheets of every scene). Tested on the old film: 18.25 min, 44,100 Hz, old sha, all studio checks ok, sheets written. An automatic replay detector was tried and dropped: calibrated on the old film's known replays it could not separate them from different pictures; replays are judged by eye on the sheets.
- Kaggle is not part of this route: config commercial_use_permitted false; gate refuses production data, voice and unlisted tasks; only run.py compute kaggle-* calls the worker.

## 25 Nov 2026, 03:41-04:30 UTC: the rendered film, inspected (held, NOT approved)
Evidence folder: data/rescript/inspect2/20261125T034203Z/ (summary.json, contact sheets; deep/deep.json, deep/mid_*.png at 480x270; closeups/grid_*.png at 960x540). Tools: data/rescript/ss_inspect2.py and data/rescript/ss_inspect2_deep.py (new; read-only on output/).

**Render status (checked first, not assumed).** ss_redo2 started 00:02:01 UTC in the real worker (`docker --context default`, /app = ~/studio), wrote the record 00:02:01, finished 01:47:22 UTC (state "rendered"; 4,376 of the 10,000 free Cloudflare Neurons; no paid picture). At 03:5x UTC the real worker ran only `worker.py`: no render, no ffmpeg, nothing started twice, nothing restarted or stopped.

**File.** output/doc-did-seven-sleepers-hide-in-a-cave-and-awaken-/video.mp4, 498,922,626 bytes, sha256 `d885501e6a77deac0b019974d0f96f577ab6ceba88810cfac37b2dfb4bbda597`. The old film (sha256 `f16337c6...`) is kept in output_old/doc-did-seven-sleepers-before-redo2-24nov; its hash was re-checked today and matches its inventory file and the record's approval_history.

| Check (measured on the real MP4) | Result |
|---|---|
| Length | 1,295.4 s = 21.6 min: over 15 min, inside the 20-23 min target |
| Picture | 1920x1080, 30 fps |
| Sound | AAC, 48,000 Hz, stereo (the old film was 44,100) |
| studiochecks (full decode) | 12/12 ok: decodes cleanly, 0% black, longest still 0.9 s, 448 captions in order and inside the video, 100% of script words in the captions, speech ends 0.9 s before the end, mean -17.4 dB |
| Black stretches (blackdetect, 0.3 s+) | none |
| Frozen picture (freezedetect, 2 s+) | none |
| Hard cuts | 108, every one on a line boundary (109 scenes); none inside a scene, so no jump or replay mid-scene |
| Narration gaps over 1.5 s | none; one 1.07 s full silence at 9:39.7, the ordinary pause between lines 48 and 49 with nothing under it |
| Voice against captions | voice 40 ms after the caption timing over the whole film, and 40-50 ms at the start, middle, final third and end: no drift (speech-band loudness cross-correlated with words.json, r = 0.74; timing only, not pronunciation) |
| Every line in the mix | each of the 109 lines is at least 15.6 dB above the pause before it (median 25.6 dB): no line missing |
| Ending | the film ends 0.88 s after its last word ("...where did they really sleep?"), no fade or hold: may feel abrupt |

**Looked at:** one frame from the middle of every scene (109) at 192x108 and 480x270, 24 suspect scenes at 960x540, and the first and last 12 s every 2 s. Not a viewing: `whole_video_watched` false.

**The owner's three picture fixes and the replay:**
- old 52 -> now scene 60 (11:56.9): new grotto with candles and niches; a small carved inscription of garbled letters is still there, top right (see C).
- old 54 -> now scene 62 (12:19.8): rocky hillside above a village at dusk, no lettering: fixed.
- old 67 -> now scene 75 (14:58.5): Damascus under Mount Qasioun (domes, minarets), no longer Jerusalem: fixed.
- the old last-third replay of scenes 9-32: gone; scenes 73-108 are new drawings in story order.

**Defects found (precise; scene number = line index in the record, times are the line's spoken span):**

A. Archive pictures on the wrong lines (all in the first half). The record does not store which picture went to which scene, so this list is from looking, and the cause was not traced. The render log's step "Archival images (only pictures that name the subject)" fits what is seen: pictures about the Seven Sleepers in general, not about the line.
- 14 (2:37.9) an engraving with an idol figure, for "buildings with crosses on them"
- 15 (2:47.5) an unreadable reddish close-up, for the old coins of Decius
- 16 (2:56.8) "Drachm of Ephesus, 330 B.C." coin with its printed label, for the bishop hearing the sleepers
- 17, 18, 19 (3:06.7-3:44.7) one silver coin of Magnesia (legend MAGNETON), reverse, both sides, obverse, for Jacob of Serugh, the lost Greek source and the Syriac-or-Greek debate; its meander symbol reads as a swastika at viewing size
- 20 (3:45.7) modern garden steps, for a sixth-century manuscript in the British Museum
- 23 (4:25.0) a fresco of a pope at mass under the Man of Sorrows, probably the "Mass of Saint Gregory" (Pope Gregory I), for Gregory of Tours (reading of the iconography, not verified)
- 25 (4:49.2) an almost empty sky with a branch, for Paul the Deacon
- 26 (5:00.4) a cave interior with candles, for the Golden Legend
- 27 (5:14.8) a modern mosque building and old wall, for "more than two hundred manuscripts"
- 28 (5:25.2) an Arabic manuscript, for a ninth-century Irish calendar
- 30 (5:54.5) a Persian manuscript headed "Tafsir of Surah Kahf", for Crusaders carrying relics to Marseille
- 32 (6:19.0) the green "al-Kahf" calligraphy, for the Orthodox Church's feast
- 33 (6:30.7) the opening page of Surah al-Kahf, for the Roman Martyrology and Byzantine calendar
- 34 (6:42.4) a Syriac manuscript, for "It appears in the eighteenth chapter, Al-Kahf"
- 37 (7:22.5) an Alpine village church, for "The Qur'an does not say how many of them there were"
- 39 (7:46.4) a French royal manuscript scene, for the chapter's name
- 40 (7:53.7) a Christian mosaic of two bishops, for Qur'an verse 22
- 41 (8:05.9) a Latin manuscript headed "SCI MARTINI", for the Qur'an's "My Lord knows best their exact number"
- 42, 43 (8:16.1-8:37.1) one Christian illumination of a haloed figure, two crops, for Insha'Allah and Tafsir Ibn Kathir
- 45 (8:51.9) a Russian printed page headed "Gregory of Tours", for Qitmir, the dog of the cave
- 67 (13:21.3) a Western graveyard, for the mosque built by the son of Ahmad ibn Tulun
Several of these put Christian pictures on Qur'an lines and Islamic texts on Christian lines; viewers of both faiths may object, and scene 34 visibly contradicts its narration.

B. The same picture again: 17-18-19 (one coin, three crops), 42-43 (one illumination, two crops); near-identical Blender renders: 92 and 98 (an empty pale sea; neither line is about the sea, and 98's note asks for a seer who is not there), 35 and 46 (dunes).

C. AI pseudo-lettering:
- 68 (13:35.5) a large invented Arabic-looking wall inscription, presented by the narration as "the basmala and verses of the Qur'an in Kufic script": invented sacred text, the worst lettering defect in the film
- 73 (14:32.9) an invented Arabic-looking band along the arches
- 107 (21:11.4) two open books full of invented Arabic-looking script
- 60 (redraw of old 52), 53, 104: smaller garbled Latin-looking lettering
- 65, 81, 105, 106: small glyph marks
- 91: calendar numerals partly garbled

D. Other: 87 (17:22.9) an AI drawing of a modern presenter in a suit while the narration names a real director, Farajollah Salahshoor (viewers may take it for him). The film also ends 0.88 s after its last word (above).

**Two-family AI review (`run.py review`, free models only, `free_only` true):** verdict **unreviewed** (03:55-04:1x UTC, real worker, log logs/seven-sleepers-review-v2-25nov.log). The AI review did not run: `llm_review: review unavailable: ModelUnavailable` (block), so there is NO two-family AI verdict, and that is not a pass. All other rule checks are ok: length, resolution, audio, black frames, chapters, credits, script, originality 2.9%, claims in source, overclaim, loudness -14.1 LUFS, pace 166 wpm. One warning: rehook_gap, about 210 s without a question or turn (aim 90). Its row `images: 109 different on-topic images` counts different files only; it does not see the wrong-line pictures in A.

**Record:** hold true, approved false, approved_by none, `approval_history` keeps the withdrawn 24 Nov approval with sha256 f16337c6..., review_history kept. Nothing approved, uploaded, scheduled or published.

**Owner decision:** accept as is, or repair. A repair would redraw or replace the scenes in A, B and C, with visual notes that ask for no lettering, using the free Cloudflare day (about 30 pictures x 104 Neurons, roughly 3,100 of 10,000) and re-render in place (about 1 h 45 min). Nothing started without the owner's yes.

**Process faults during this inspection (reported in full in the master report, 25 Nov):** the shell's bare `python3` was the forbidden workshop folder's interpreter, and plain `docker` reached a second studio pair under Docker Desktop whose /app is that folder. A review command run there by mistake failed and left a 159-byte log file in that folder. The measurements above come from /home/fahad/studio/.venv/bin/python, /usr/bin/ffmpeg/ffprobe on the real file and `docker --context default`; the 960x540 close-up frames and some read-only helper scripts (standard library only) were run with the workshop interpreter before this was noticed, and a first sync attempt with that folder's faster-whisper crashed and was dropped.

## 25 Nov 2026, 04:40-06:30 UTC: root cause, scene manifest and repair plan (film still HELD, nothing rendered, no Neurons spent)

**Preserved first.**
- Current film: sha256 `d885501e6a77deac0b019974d0f96f577ab6ceba88810cfac37b2dfb4bbda597`, re-verified. Byte-identical copy at `output_old/doc-did-seven-sleepers-v2-d885501e-before-repair-25nov/`, with `….inventory.sha256` beside it.
- Previous film: `f16337c6…`, re-verified in `output_old/doc-did-seven-sleepers-before-redo2-24nov/`.
- The live folder is unchanged: video, record and words were not touched.

**Scene manifest (complete).** Every scene has its narration, context, intended visual, actual file, drawing prompt, source and licence, assessment, writing, duplicates, class, correction, confidence and evidence.
- Files:
  - `reports/SEVEN_SLEEPERS_SCENE_MANIFEST_2026-11-25.md` (table);
  - `data/rescript/scene_map_v2/scene_manifest_v2.json` (full);
  - `scene_map.json` (match evidence).
- Built by `data/rescript/ss_scene_map.py` and `ss_scene_manifest.py`, both read-only on `output/` and `cache/`.
- Method: three frames of every scene were taken from the real MP4. Each was matched against 111 candidate files:
  - every line's own drawing, with its prompt rebuilt from `aiart.prompt_for` and its cache file present;
  - every credited archive picture, resolved to its cached file;
  - the Blender stills.
- Results:
  - 103 scenes HIGH (score ≥ 0.60 and ≥ 0.10 above the runner-up);
  - 4 RECORD (Blender scenes, placed by the record);
  - 2 MEDIUM: scene 36 ties between two copies of one image; scene 45 is a text page, settled by eye and its credit.
- What the scenes are: 48 archive pictures, 55 drawings and 6 Blender scenes. **All 55 drawings are the drawing made for their own line.**
- Prompts: given only for drawn scenes. They were rebuilt from code, and the matching cache file proves each one was used. Nothing was invented. An archive picture's "prompt" is UNKNOWN by nature: it was a search.

**Root cause (evidenced, not assumed).**
1. **Fallback order in `footage.scene_images`.**
   - The order is: the line's own search, then the subject's **reserve pool in pool order**, then a drawing.
   - The pool is filled by searching the topic and then each anchor in turn (Seven Sleepers, Ephesus, Cave of Seven Sleepers, Surah al-Kahf, Jacob of Serugh, Gregory of Tours, Mount Pion).
   - Scenes 0–45 show exactly that sequence:
     - legend art (0–9);
     - Ephesus items (11–19: St Paul, a Diana herm, coins);
     - the Amman cave photos (20–27);
     - Qur'an items (28–33);
     - Syriac items (34–36);
     - Gregory of Tours items (39–45).
   - Drawing started only when the pool was empty (scene 46 on).
2. **Relevance is checked against the subject, not the line.** `footage.image_relevant` only needs an anchor in a file's title or categories. The model judge (`run._image_judge`) asks whether a file "plausibly shows" *the documentary's subject*. Nothing compares a picture with its line.
3. **The mapping was never saved.** `scene_images` returns the per-scene list, but the record kept only counts and a de-duplicated credit list. That is why the 24–25 Nov report could not name the cause. It is also why the reviewer passed "109 different on-topic images", a count of files, not of fit.
4. **Side effects found:**
   - **Credits for pictures not shown.** Blender scenes replace pictures after selection (`blenderscenes.place`), but the replaced pictures' credits stay in the credit list. The Falnama picture is credited but not shown.
   - **One image counted twice.** The same Syriac picture was downloaded twice, as a Commons `.webp` and an Openverse copy, and counted as two.
   - **The same object several times.** One Magnesia coin appears in three different files, at scenes 17–19.
5. **Ruled out:**
   - Index misalignment after the script revision: drawings are keyed by text, and 55 of 55 match their own line.
   - Asynchronous generation, retries and cache collisions: no evidence for any of them.
   - Scene reordering: none happened.

   The 16 inserted lines did change *which* pool picture landed on *which* line, because the pool is handed out in order. But the mismatch exists without them: the 24 Nov film had coins on unrelated lines too.

**Pipeline fix (traceability and detection; the selection policy is unchanged and is the owner's decision).**
- `footage.scene_images(trace=)` records, per line, how its picture was chosen: forced_named, forced_drawn, line_search, art_first, **reserve**, drawn, **reuse** (a failed drawing that falls back to an earlier picture), or missing. It changes no choice; a test proves the output is identical.
- `scenemanifest.py` (new) writes `scenes.json` in the video folder, atomically. For each scene it records:
  - a stable id from the narration text (reordering keeps ids);
  - how its picture was chosen, and the query used;
  - the file and its sha256;
  - what a later step replaced (real footage, Blender, animation).

  It compares itself with the previous `scenes.json`, kept as `scenes.prev.json`, and reports:
  - **changed:** an unchanged line now shows a different picture;
  - **stale:** a revised line still shows the old line's picture;
  - **reserve runs** and **repeats**.

  The record holds the summary, the sha256 of `scenes.json` and the sha256 of the **final** video, taken after the pop-up and sound passes.
- `run._produce_doc` writes the manifest for every documentary, including the `local_pictures` route. A failure is recorded as an error, never silently skipped.
- The reviewer has a new row, `scene_sources` (warn). It names reserve runs, repeats, files shown twice, and changed or stale scenes. A film with no manifest (made before today) gets no new row. The `images` row now says it counts files, not fit. The playbook `reviewer.md` was updated.
- **Tests:**
  - `tests/test_scene_manifest.py`: 12 passed. They reproduce the root cause with the real `scene_images` (search faked), and cover reordering (a move, not a change), an inserted line (silent reassignment caught), a revision (stale), a failed drawing (reuse), stage replacement, the atomic write, and the reviewer row.
  - agenteval case `case_every_scene_is_traceable_to_its_line_and_a_reserve_run_is_never_passed_silently`, with **three mutation checks**, all caught: an untraced pick, a reviewer that passes anything, and ids based on position.
- **Not changed:** the order "real archive picture before drawing" (the owner's 10 Nov rule), Shorts (`_produce_short` is not wired yet), and anything already rendered.

**Repair plan (per scene in the manifest; nothing done yet).**
- **Classes:** KEEP 44, REUSE_WITH_JUSTIFICATION 7, REPLACE 46, REDRAW 4, REMOVE_TEXT 5, NEEDS_HUMAN_REVIEW 3 (31, 50, 65).
- **13 moves of files already verified in this film (no Neurons):**
  - Russian icons to 3, 32 and 33;
  - the Syriac Jacob of Serugh picture to 17;
  - the Gregory of Tours manuscript to 23;
  - the "Surah al-Kahf 18" roundel to 34;
  - the Persian miniature to 37;
  - the Tropenmuseum page (Q 18:1–2) to 38, only after a second reader confirms the text;
  - the real Amman photos to 61, 63, 65 (if its record places it there), 66 and 68. Scene 68 shows the cave's real wall, *not* claimed to be the Kufic inscription.
- **42 drawings at most.** All use "NO writing" notes. No drawn Arabic, Qur'anic or manuscript text, ever. 9 scenes try a verified archive picture first:
  - a coin of Trajan Decius (never an AI coin);
  - a Decian libellus papyrus;
  - a Golden Legend miniature;
  - an early Syriac manuscript;
  - a Tafsir Ibn Kathir manuscript;
  - a freely licensed photo of Farajollah Salahshoor, or else a TV set with **no person**;
  - and others listed in the manifest.

  Each needs its library record and licence checked by `licences.py`.
- **Ending:** the renderer has no closing hold or fade today. Plan: a per-film option giving a 2.5 s hold on the last picture after the last word, a 1.5 s video fade and a 2 s audio fade. It needs a small code change and a test; it is opt-in, so other films are unchanged.
- **Render route:** the `local_pictures` route gives the film exactly the approved file for each of the 109 lines, with no search and no reserve. Its manifest records "local". Before rendering, the asset records of the kept library pictures must carry over (the route sets `assets` to `[]` today): a small code change and a test. Re-render in place, after the copy above.
- **Budget** (Cloudflare price page read 25 Nov: FLUX.2 klein 4B costs 26.05 Neurons per output 512² tile, about 104.2 per 1024x576 picture; the free 10,000 a day reset at 00:00 UTC; no paid fallback, since `aiart.paid_enabled` is False and `free_only` is True):
  - about 4,376 Neurons if every drawing works first time;
  - about 6,981 with two tries for the 25 text-prone scenes;
  - high-priority scenes only: about 5,939.

  The studio's own count is not the account's: the owner's FreeLLMAPI text models use the same account, and on 24 Nov the account was spent while the studio counted 1,667. **Read the real figure in the Cloudflare dashboard before approving**, and start drawing just after 00:00 UTC. Generation manifest: `data/rescript/scene_map_v2/generation_manifest_v2.json`.
- **Independent picture review: BLOCKED (not run).** The studio's vision reading uses one model family, and today's text review could not get two judges (`ModelUnavailable`). Claude's own frame review is one reviewer, not independent. Before the render, a two-family scene review must be built and run on the new pictures: scene frame and narration go to two families, the stricter answer counts, and a missing family means BLOCKED.
- **QA after an approved render:** the full `ss_inspect2.py` and `ss_inspect2_deep.py`, `scenes.json` read scene by scene, every previously defective scene seen at 960x540, the ending fade measured, and the full test suite. The film stays HELD.
