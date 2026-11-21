# End-to-end video test (2026-11-20)

## 1. Controlled test job: done
The real documentary producer (`run._produce_doc`) ran in the worker container on a fixture script: 8 lines, 2 chapters, 8 local pictures. It used the real voice service, real ffmpeg, the motion graphics, the corner mark and the sound cues, and the new hand-over checks. Everything went into `/tmp/e2e-*` inside the worker: no real video folder, pending script, activity feed or cost file was touched.

| Check | Result |
|---|---|
| Hand-overs (`a2a.handoff`) | script ok (8 lines, 2 chapters); voice ok (26.4 s, 8 timings); visuals ok (8 scenes, 8 different); render ok (26.4 s) |
| ffprobe | 26.43 s, video 1920×1080 30 fps, plus an audio stream |
| Full decode (`ffmpeg -f null`) | no errors |
| Loudness | −14.25 LUFS integrated, true peak −4.24 dBTP |
| Captions (`studiochecks.caption_checks`) | present, in order, inside the video, match the script, voice timing matches the length: 5 of 5 |
| Chapters in the description | `0:00 The mystery`, `0:10 The search` |
| Record | `meta.json` with `handoffs` and `approved: false` (not approved automatically) |
| Dashboard registration | `dashboard.state()["videos"]` lists `doc-audit-test-film` "Audit test film" |

**Defect found by this run and fixed:** a documentary built from local pictures (the route used by Claude Code builds, `local_pictures`) rendered completely and then crashed before its record was saved (`UnboundLocalError: finder`). The committed code (HEAD) has the same gap. Fix in `run._produce_doc`; regression test `tests/test_local_pictures.py::test_a_local_picture_film_is_finished_and_registered`, which fails without the fix.

## 2. One real 20 to 26 minute Free Mode documentary through Autopilot: BLOCKED (not started)
| Prerequisite | State (20 Nov, about 04:10 UTC) |
|---|---|
| Pipeline, hand-overs, Free Mode gates, dashboard | verified (this report and the others) |
| A free writer | **1 of 6 tried answers** (`nvidia/nemotron-3.5-super-vl:free`). Gemini on the owner's proxy and the Gemma models give 429 (rate-limited upstream); the proxy's `auto` timed out after 120 s. |
| Free review | Needs **two other** free models, never the writer. With one model answering, the review would come back "unreviewed" and the film would be held. |
| "Through actual Autopilot" | Needs the owner's `enabled` switch on. With `auto_approve: true` and `pause_scheduling: false` that would also approve, schedule and upload other waiting videos. Not the assistant's switch. |
| What Autopilot would make next | **The waiting script in `data/pending_doc.json`**: "The Secret Code of the Pyramids: Egypt's Celestial Blueprint", 54 lines (the old 9-minute shape), **no source article**. It is the film that failed on 19 Nov (the GIF bug, now fixed). Autopilot renders a waiting script before it writes a new one. |
| Machine | Disk 268 GB free (fine); swap 7.0 of 8 GB used; the worker is capped at 3 GB; an estimated 1.5 to 2.5 hour render |

So no long film was made, and no video exists that would count as one. The Ronaldo film (20.8 min, made earlier by another route) is not counted.

## What the owner needs to decide to run it
1. Keep or discard the waiting Pyramids script. To discard, move `data/pending_doc.json` aside, for example to `backups/`. Otherwise Autopilot renders it first, as a 9-minute film with no source.
2. Set `pause_scheduling: true`, and either `auto_approve: false` or accept that passing videos are approved, then switch Autopilot on. Or run `python run.py doc "<topic with a Wikipedia article>"` by hand for a single film.
3. Run it when at least three free models answer (writer plus two judges). The doctor's `doc.json` now shows how many are usable.
