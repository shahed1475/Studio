# Cambyses documentary remake: 8 to 10 minutes, same pictures, new structure, new packaging (plan, 30 Oct 2026)

> **For agentic workers:** execute task by task; each task ends with a check whose output is read before the next starts (`superpowers:verification-before-completion`).

**Goal:** Remake "The Lost Army of Cambyses" as an 8 to 10 minute documentary in the owner's structure (hook, curiosity, story, finish with value), on the same 48 pictures with the free 3D and 2D motion, with the voice fixed, a thumbnail and title that do not repeat each other and make a viewer curious, and a written method Autopilot can follow. Report the real cost at the end.

**Spec:** the owner's messages of 30 Oct (Gemini review; "title and thumbnail are the same"; more attractive, curious thumbnail; remake; same images; 8 to 10 minutes; hook, curiosity, story, finish with value; check the costing; store the method), `docs/studio/DOC_PACKAGING_AND_MOTION_RESEARCH_2026-10-29.md`, `docs/studio/FINISHING_A_VIDEO_RUNBOOK.md`. One more item was announced ("also add this") but its text never arrived: ask the owner.

## What the research found (30 Oct, measured or read, labelled)
- **Gemini 3.1 Pro watched the whole documentary** (our own video, 360p, `run.py analyze-video`, $0.108, VERIFIED as a model reading, not a frame-by-frame check): the voice says "Amonius" where the caption says "Amun" (0:13, 2:33); garbled, fake writing on a map (0:59) and on a scroll (2:27). Nothing else flagged.
- **Pronunciation test** (Gemini listened to four spellings, $0.015): "Amun" is heard as "ah-mo-nee-us", "Amoon" as "uh-moon", "Ammon" as "am-en", **"Ahmoon" as "ah-moon"**. Fix: say "Ahmoon", keep "Amun" in text.
- **Outlier thumbnails** (YouTube API, 16 recent history videos that beat their channel's size by 5 to 600 times, public thumbnails viewed; a sample, not proof): a time or number as the headline ("3100 YEARS AGO", "7,000 BC"), one cinematic scene with one focal point, 2 to 4 bold words that admit a mystery ("THEY ALL FAILED", "WE CAN'T EXPLAIN"), sometimes an arrow at the thing to wonder about. Two "history for sleep" channels, our niche, are outliers (x44) with a bold claim in the title.
- **"Title and thumbnail are the same":** the video card still lists the first, older options, whose text "LOST ARMY WESTERN DESERT?" repeats the title's words. The dashboard only lets the owner choose files named `thumb-N.jpg`, and my new files were named otherwise.
- **Length:** the documentary is 456 s (7.6 min) with 1,052 words; the writer's line cap (50 lines) is the cause. The target is 480 to 600 s: about 1,300 words, so about 255 more words.

## Global constraints
- Same 48 pictures: no new picture is drawn. A new or changed line takes an existing picture by copying its cache file to the new line's key (the key is made from the line's text, visual note, topic and style); an original is never overwritten or deleted.
- New narration may only restate facts already in the checked script and the two Wikipedia articles, or be structure (promises, turns, a how-to-weigh-it test). No new names, dates, numbers or quotes. It is checked with `scriptgen.unsupported`, the script review gate and the reviewer.
- A held draft stays held: no approval, upload or schedule.
- Credit is under $2: every paid call is counted (`llm.cost_scope`, Gemini calls through `llm`), and the total is reported.

## Tasks
- [x] **T1** Deploy the pronunciation fix (commit f6a06e4) when no render runs.
- [x] **T2** Writer: `scriptgen.doc_script` asks for hook, a curiosity bridge with a promise, story, then a closing chapter of value; line cap 50 to 58; target 8 to 10 minutes; reviewer warning `doc_length` outside 480 to 600 s; tests and an `agenteval` case with a mutation check.
- [x] **T3** This video's script: insert the bridge (2 lines), two turns and a value chapter (7 lines) with `visual` notes pointing at existing pictures; swap the two garbled-text scenes to existing pictures without writing; recompute chapters; check every new line against the sources and the script gate.
- [x] **T4** Re-render in place (backup, Autopilot lock, motion switches, voice tail, `Ahmoon`), then measure: length 480 to 600 s, `check_video.py`, frames at the new parts, Gemini watches it again.
- [x] **T5** Packaging: dashboard shows only the new thumbnail options (named `thumb-N.jpg`, old ones moved to `thumbs/old/`); three thumbnail variants that differ in one thing (the words), on a stronger picture, scored and viewed at 120 px; title variants by the title skill, checked for honesty and for not repeating the thumbnail; description hook, chapters, hashtags.
- [~] **T6** Review (`run.py review`), quality gate, copyright check; the cost report from the usage log; runbook, CLAUDE.md, memory; commit, clean check, push, deploy.

## Not in this plan
Approving, scheduling or uploading the documentary; new pictures; the item the owner has not yet said.

## Status (30 Oct 2026, after the power cut)
- **T1** done: the server runs f6a06e4 (checked by git log on the server).
- **T2** done: structure prompt, 58-line cap, `doc_length` warning, tests and an `agenteval` case with three mutation checks.
- **T3** done on the server (script 58 lines, 1,325 words, 9 chapters). Checked now: every quotation and number in the closing chapter is in the Wikipedia text; the claim ledger on the real script gives 8 VERIFIED, 0 open (after fix 2 below).
- **T4** done: 556.4 s; `check_video.py` all ok (full decode, loudness -15.0 dB, captions 100 percent, longest still picture 0.8 s); frames looked at; Gemini watched the whole video (leads only: a distorted face in the first frame is confirmed, the audio skips are not found by a waveform check).
- **T5** done: three new thumbnails (`thumbs/thumb-1..3.jpg`, old ones in `thumbs/old/`), vision scores 8.0, 7.7, 6.8; title kept (52 characters, does not repeat the thumbnail); description hook, nine chapters and tags checked.
- **T6** partly: reviewer pass; quality gate shows 1 blocking row (a correctly sourced quotation) until fix 2 is deployed; runbook section 6 and CLAUDE.md written; cost: the day's spend rose by $0.44 for everything run today (video record $2.66). **Not pushed, not deployed** (owner decides).
- Three defects found and fixed locally with tests, `agenteval` cases and mutation checks: (1) AI review cap 7,000 characters, (2) quotation matching, (3) video analysis output room and script cap.
- Open: the first-frame face (a new picture would cost about $0.05 and a re-render); the announced extra item whose text never arrived.
