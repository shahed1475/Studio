# Short production report (20 Nov 2026)

## Identity
| Field | Value |
|---|---|
| Video folder (id) | `the-true-story-of-tenali-rama` |
| Output path | `~/studio/output/the-true-story-of-tenali-rama/video.mp4` |
| Title | Tenali Rama Stories: Who Was the Real Scholar? |
| Topic and source of the topic | "Tenali Rama", chosen by `topicrank.pop_best` from the Studio queue at 08:27:57 UTC (research score 3.648, source article 4,164 characters, premise screen passed; activity feed "Chose a topic: Tenali Rama") |
| Job | `python run.py autopilot make short` in studio-worker, 08:27:31 to 08:44 UTC (`autopilot.make_one`: Autopilot's own `make_short` executor, then the reviewer); log `logs/mission-short-20nov.log`, exit 0 |
| Source | Wikipedia: Tenali Rama (CC BY-SA 4.0), retold in our own words |

## The file (measured on the MP4)
| Check | Result |
|---|---|
| Duration | 54.23 s (target 35 to 58) |
| Video | H.264 1080x1920, 30 fps |
| Audio | AAC stereo 44.1 kHz; -14.0 LUFS integrated, LRA 2.8 LU, true peak -4.1 dBFS |
| Size | 46.9 MB |
| Full decode | no errors (`ffmpeg -v error -f null`) |
| Black frames | none (`blackdetect` 0; reviewer 0%) |
| Captions | burned word captions + captions.srt (subtitle timing from the voice's word times) |
| Pictures | 11 scenes, 11 different, all drawn on the free Cloudflare account (FLUX.2 klein, 1,719 Neurons), each moved by 2.5D camera motion with a depth map (11 clips, 0 failed) |
| Music | one CC0 recording (Chopin, Nocturne Op. 55 No. 1, Commons file page in the record), about 23 dB under the voice |
| Branding | hook question on screen, channel mark top left, subscribe pop-up at 50 s, riser and hit sound cues |
| Frames looked at | 1, 8, 16, 24, 32, 40, 48, 53 s: a consistent photo-real style, period Indian settings, readable captions, no repeated or broken frames. These are 8 frames, not the whole video. |

## Models (all free, $0.00)
- Writer: `extra:gemini-3.5-flash` (served as gemini-3.5-flash), recorded in `script_writers`. (`script_model` keeps the assigned model by design, so training-data rules err toward exclusion.)
- Judges (AI review): `extra:gemini-3.6-flash` and `extra:nemotron-3-ultra-550b`, neither the writer; the stricter answer counts. Invented-facts risk 0/10, policy risk 0/10.
- Blender: nothing planned. The article "Tenali Rama" has no coordinates and no line names a place a template can show truthfully. That is the rule working (no guess).

## Review and what was then found
- First review (08:44): verdict PASS, 35 checks.
- Engineer's fact check against the article: 9 of 10 factual lines match it. Line 10 said "Yet textual dedications **prove** he actually served later ruler Venkatapati Raya"; the article says "Internal textual evidence and dedications in his works **suggest** that he ... received patronage from later Aravidu dynasty rulers and nobles like Venkatapati Raya". Both free judges missed this overclaim.
- Permanent fixes: reviewer check `overclaim` (human), fixer repair for it, written centuries in the claim ledger (the ledger had been empty). Second review (09:30): verdict **needs_human**, exactly line 10 flagged; the ledger now lists "sixteenth century" VERIFIED.
- Repair: through `python run.py repair the-true-story-of-tenali-rama` (the fixer under the Autopilot lock) once the documentary releases the lock. See the update below.

## Registration and status
- Registered in the dashboard's own list (`dashboard.videos()`), state "needs review". Not approved, not scheduled, not uploaded (`approved` false, no `video_id`, no `publish_at`).

## Update after the repair
(filled in below when the repair has run)
