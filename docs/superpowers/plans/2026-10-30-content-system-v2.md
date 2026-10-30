# Content system v2: the owner's order of 30 Oct 2026 (evening)

Order of work the owner set: (1) note every task point by point, (2) research, (3) plan, (4) implement step by step. Skills loaded first, tokens kept low (existing research reused, outputs short).

## 1. The owner's tasks, point by point
| # | Task (the owner's words, plainly) | State |
|---|---|---|
| T1 | The reviewer report on a video shows two warnings (no source beyond Wikipedia, no original element). Fix that with some real footage, push it, and use Autopilot for it. | open |
| T2 | Remove every video from the schedule, including the private scheduled uploads on YouTube. Every video needs changes. | DONE 16:01Z: three uploads made private with no time (read back from YouTube), the planned draft cleared; 13 public videos untouched |
| T3 | Create no schedule from now on, until the owner says so. | in progress: an owner switch that stops scheduling and uploading |
| T4 | First check the videos that were never uploaded (drafts). | open |
| T5 | For every Short and every long video, pick the first image (and the thumbnail) so a viewer is curious enough to finish. | open |
| T6 | The hook and curiosity from the first second: voice, sound effects, a question, so the viewer feels they must see the whole video. | open |
| T7 | Use real footage and real images; make AI footage or images only where needed; turn them into 3D animation. Shorts AND long videos both 3D and animated. | open |
| T8 | Weekly rhythm by Autopilot: 4 long videos and 6 Shorts. | open |
| T9 | The 4 long videos: day 1 mystery history; day 2 unsolved crime, case or history; day 3 a famous person documentary; day 4 a trending subject that fits the channel. | open |
| T10 | The 6 Shorts are based on those long videos. Check which Shorts get high views and use that for the last (6th) Short of the week. | open |
| T11 | Research first: how channels get more views, how they edit, how they hook and build curiosity, how Shorts work, how story and value are delivered, how videos are paid off and finished, how subscribers are engaged. Sources: Google and YouTube. | open |
| T12 | Then write the plan, then implement step by step, perfectly. | open |
| T13 | Use skills before starting and spend fewer tokens. | applied |

Money fact for the plan: credit $7.94, daily cap $5.00, Autopilot off. A realistic animated film costs about $3.5 to $4 and a Short about $0.6, so 4 + 6 a week is about $18 a week: it needs a top-up and real footage (cheaper than drawing every scene).

## 2. Evidence (research, 30 Oct 2026)
Reused from the studio's own research of 29 and 30 Oct (docs/studio/VIDEO_CRAFT_RESEARCH_2026-10-29.md, THUMBNAIL_CURIOSITY_RESEARCH_2026-10-30.md): hook advice from YouTube's own blog (start with a question, say within 5 seconds what the viewer will see, cold open); the retention report's "Intro" = share still watching at 30 s; Shorts are ranked on viewed-vs-swiped, average view duration and percent viewed; since 24 Aug 2026 "engaged views" exclude loops; Test & Compare decides by watch time and is not for Shorts. New in this pass:

| Finding | Label | Source |
|---|---|---|
| YouTube forbids "violent or gory content intended to shock or disgust"; a documentary or educational exception exists but the context "must appear in the images or audio of the video itself" (title or description alone is not enough). | VERIFIED | support.google.com/youtube/answer/2802008, read 30 Oct 2026 |
| Prohibited: "content that realistically simulates deceased or abused individuals describing their death or violence experienced". Documentary content may be allowed, "not a pass to harass someone". | VERIFIED | support.google.com/youtube/answer/2802268, read 30 Oct 2026 |
| So a case or crime video must not show a realistic AI face or voice of a real victim or suspect, must keep violence non-graphic, and must say its documentary purpose in the narration. | our reading of the two pages | same |
| Realistic AI content must be disclosed; "this disclosure is not a free pass to violate our policies". The studio sets `containsSyntheticMedia` on every upload. | VERIFIED (page) / not readable back from the API | support.google.com/youtube/answer/2802008 |
| Shorts can carry one "related video" link to a long video on the same channel (YouTube Studio, desktop). Click-through is reported as very low; the long video should open by answering the Short's promise within 5 to 10 seconds. | PARTIALLY_VERIFIED: news and creator guides only, no official Help page found | searchengineland.com, vidIQ, Tubefilter; creator guides |
| The retention curve usually falls most in the first 15 to 30 seconds; a steep early cliff is a slow start or a thumbnail mismatch; benchmarks depend on format, compare with your own similar videos. | creator practice | vidIQ, Subscribr, AIR Media-Tech (no controlled study of documentary openings exists) |
| Sound effects (riser into a reveal, a hit on the reveal, a whoosh on a cut): no study shows an effect on retention. One music-licensing blog argues viewers leave when audio does not support the visuals. | UNVERIFIED as a retention effect; a design choice | vendor and creator pages |
| End screens run in the last 5 to 20 seconds and need a relevant video or playlist plus subscribe. No rigorous Shorts-to-subscriber study found; the "20 percent" figure has no method. | creator practice / UNVERIFIED | creator blogs |
| Public-domain footage: the Internet Archive gives no written permission and an uploader's "public domain" label needs checking item by item; Library of Congress items carry their own rights statements; NASA media is generally usable but gives no right to names or likenesses. | PARTIALLY_VERIFIED (secondary pages, 2015 to 2016 era) | nofilmschool.com, openculture.com, filmdaft.com. Rule for the studio: check every item, keep its address and licence. |

The channel's own numbers (90 days, YouTube Analytics through the studio's collector): 10 Shorts, 859 views; 6 films, 235 views. Best Shorts: Voynich Manuscript 329 views (54 percent viewed, 54.5 percent still watching at 30 s), Thunderbird 265, Knossos 136; one Short keeps only 23 percent at 30 s. 305 of the top Short's 329 views came from the Shorts feed. Best film: 180 views, 20 percent viewed, 41.7 percent at 30 s. Mystery-object subjects win the Shorts.

What a viewer sees first in the four unfinished videos: a calm descriptive line over a still archive picture ("Picture two brothers,", "Close to modern Mexico City,", "Today, most of us expect one unbroken stretch of sleep."), no question, no stakes, no motion, no sound effect. One Short has a good question hook as text over a still book page.

What the studio can already do: real stock video (needs a Pexels key, not set), public-domain archive.org film (switched on, only Shorts use it), Wikimedia Commons still images (public domain and CC0 only), AI pictures, image-to-video clips, free camera motion, the pop-up and mark, second sources (works, never run on a new film). The long-film producer shows no real moving footage at all, and there is no sound-effect layer and no music folder.

Not verifiable and so not promised: any sound or editing trick raising views; the 4 + 6 weekly volume raising views (the studio's pace governor exists because YouTube judges a channel as a whole for repetitive, mass-produced content).

## 3. Plan (what Autopilot gets; the owner tests by generating; nothing is scheduled)
Cost facts for the weekly programme: a realistic animated film about $3.5 to $4 and a Short about $0.6 to $1, so 4 films and 6 Shorts a week is about $20 to $22 a week at the current look. Real footage replaces some drawn pictures and lowers it; the weekly rhythm needs a top-up and is capped by the daily limit of $5.

| Step | What it adds | Where | Proof |
|---|---|---|---|
| P1 | Scheduling switch: no slot, no upload while `pause_scheduling` is true (set on the server). Making, fixing, approving go on. | autopilot.py | tests, eval case, mutation checks (DONE) |
| P2 | Hook and curiosity: the writer opens a film and a Short with a question and stakes and promises the payoff inside 5 seconds; the reviewer warns when it does not; a big question text on the first 3 seconds of a film (Shorts already have one); sound cues (riser into the first word, a hit on the reveal, soft whoosh at chapter changes, a swell on the payoff) made by the studio itself with ffmpeg so no licence question exists, mixed quietly and never moving the loudness target. | scriptgen.py, reviewer.py, motiongraphics.py, sfx.py (new) | tests, a real ffmpeg render check (loudness within 0.5 LU, length unchanged), eval case |
| P3 | Real footage in films: public-domain and CC0 moving footage (Wikimedia Commons video, NASA, archive.org) for scenes about places and objects, never faces or events that need a person, each item with its address, licence and credit; AI pictures only where nothing real fits. | footage_real.py (new), run.py `_produce_doc` | tests with fake HTTP, one live search to show it works, licence check |
| P4 | The weekly programme: 4 films a week (mystery history, unsolved case, famous person, trending) and 6 Shorts (five from those films, the sixth copies what our best Short did); governor base 4 and 6; a new `case` kind with its own safety rules. | weekplan.py (new), kinds.py, topicrank.py, autopilot.json | tests, eval case |
| P5 | Case safety: no accusation of a named private person beyond official findings, no graphic detail, no realistic AI face of a real victim or suspect, the documentary purpose said in the narration. | scriptgen.py, reviewer.py | tests, eval case |
| P6 | Shorts winner: rank our Shorts by views and retention, name the winning pattern (subject kind, hook shape, length) and use it for the week's 6th Short. | shortpick.py (new) | tests on the real numbers |
| P7 | Look and cost defaults for both formats: realistic look, more moving clips in Shorts, with the cost written next to each setting. | autopilot.json house_style | tests |
| Owner steps (cannot be code) | Related-video link on each Short and end screens on each film (Studio, desktop); a free Pexels key if stock video is wanted; top up OpenRouter above $8; switch Autopilot on and set `pause_scheduling` false when ready. | | |

Out of scope on purpose: scheduling anything; touching public videos; re-uploading the held videos (the owner tests with new generations).


## 4. Status
- T2 done at 16:01Z.
