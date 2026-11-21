# Autopilot documentary production: "Seven Sleepers" (21 Nov 2026)

Made by Autopilot's own make step (`python run.py autopilot make doc` = `autopilot.make_one("doc")`: Autopilot's topic choice, executors, house style, weekly caps and lock, then the reviewer). Supervised; never approved, scheduled or uploaded. Folder: `output/doc-did-seven-sleepers-hide-in-a-cave-and-awaken-`.

## Timeline (UTC)
| Time | Step | Evidence |
|---|---|---|
| 20 Nov | topic "Seven Sleepers" chosen by topicrank; script written by free models (81 lines, 2,839 words, 12 chapters), fact-checked in parts; stopped at the picture checkpoint (70 of 81 drawn, free allowance spent) | MISSION_CHECKPOINT_20NOV.md |
| 21 Nov 00:08 | try 1: voice (81 lines, made again: lines from 20 Nov had no records), last 11 pictures drawn, Blender globe, 81 scenes rendered | `logs/mission-doc-21nov.log` |
| 01:0x | **failure 1**: "part 1 of 9 of the final video came out wrong (60.10 s long, 121.70 s expected)": the new part-by-part final pass. The check refused it; nothing broken was kept | same log |
| 01:23 | fix + test, try 2: 22 of 81 scenes kept (see limits), 9 parts made, overlays | `logs/mission-doc-21nov-b.log` |
| 01:5x | **failure 2**: `TypeError` in `ccdoc.source_lines` after the video was finished (every Autopilot documentary would have hit it) | same log |
| 02:06 | fix + test, try 3: **81 of 81 scenes kept, 9 of 9 parts kept**, overlays, record saved, thumbnails, review | `logs/mission-doc-21nov-c.log` |

## The film (measured)
| Check | Result |
|---|---|
| File | `video.mp4`, 397.8 MB, H.264 1920x1080 30 fps, AAC 44.1 kHz |
| Length | **1,148.7 s = 19.1 minutes**: below the owner's 20 to 25 minutes (reviewer warning `doc_length`, target 1,200 to 1,560 s). Cause and fix below |
| Full decode | 0 error lines; 34,459 frames decoded (= 1,148.6 s at 30 fps) |
| Loudness | -14.0 LUFS integrated (ebur128); reviewer: -14.1 LUFS, peak -3.9 dB |
| Captions | burned in (highlighted words) and `captions.srt`; seen on frames at 62, 67, 300, 700 and 1,100 s |
| Chapters | 12, first at 0 s, in the description |
| Pictures | 62 different on-topic pictures for 81 scenes (77%); 0 scenes without one; 0 real moving clips fitted (0 of 4 asked) |
| Blender | a real Cycles render of a globe turning to **Ephesus** (37.94 N, 27.34 E from the article's coordinates), clip 10.9 s / 262 frames (`cache/cc/clip-globe-a7f1fa0707ef015b.mp4`), on line 5 (60.2 to 73.3 s); seen on frames at 62 s and 67 s with its "Ephesus" label |
| Brand | channel mark bottom left; subscribe pop-ups at 463 s and 941 s; 13 sound cues |
| Hand-overs | script, voice, visuals, render: all passed, each with job, task id, contract, file references, checkpoint and models |
| Record | `approved: false`, no `video_id`; 3 thumbnail candidates |

## Review: **fail** (correctly held)
Two different free judges (never the writer) gave invented-facts risk 8/10 for three details the source articles do not support: a Qur'an verse number (18) for the dog Qitmir; church name lists stated as current official usage where the article gives them as historical listings; "old coins ... the bishop was summoned" (not in the article). The fixed-rule checks passed (every name and year in the source, no overclaim, originality 2.7%). Warnings: length, no question in the first two lines, a 346 s stretch without a question or turn, lines 12 and 30 tell the same thing.
Next step (owner's or Autopilot's when it is on): `python run.py repair doc-did-seven-sleepers-hide-in-a-cave-and-awaken-` rewrites those lines from the source; scenes and parts of unchanged lines are kept.

## Fixes made during this production (each with a regression test)
1. Final parts lost frames when a scene changes pixel format/colour tags mid-part (`setpts=PTS-STARTPTS` restarts after ffmpeg rebuilds its filters): constant offset now. Test reproduces it with a globe-like clip; the old code fails it.
2. `ccdoc.source_lines` crashed on Autopilot's text sources: accepts both.
3. Word rate: 127.8 words a minute (short films) let a 19.1-minute script pass the 20-minute minimum; long films now use the measured 148.3 (`scriptgen.words_per_minute`).
4. Scene records now carry their source and the resume says why a scene was made again.

## Limits (honest)
- **First resume kept 22 of 81 scenes**, not 81: the cause is not proven. Most likely the scene lengths changed once because try 1 made the voice fresh while try 2 read the voice timings back from their records. The next resume reports the reason per scene (diagnostics added). Try 3 kept 81 of 81 and 9 of 9 parts.
- The film is 19.1 minutes, not 20 to 25.
- The first failure counted as one of the film's three tries (it was a real code failure); the film finished on try 3.
- Frames were looked at at 5 moments only; the whole film was not watched.
