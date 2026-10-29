# Video craft research, 29 Oct 2026: 3D, thumbnails, long-video engagement, Shorts

Asked by the owner: how to make 3D videos for free, how to make thumbnails that attract viewers, how to hold viewers in long videos, how to build a Short (hook, curiosity, story or value, payoff), then train the studio with what holds up.

**How it was done.** YouTube's own Help pages first, then the vendors' and authors' own pages, then secondary sources, each labelled. Tools: web search (standard mode) and page fetches. A page fetch returns an answer extracted by a small model from the page text, so quotes below are "as extracted"; read the linked page before relying on one for money or policy. Pages that could not be read are named. Labels follow CLAUDE.md section A: `VERIFIED` (a page was read and says it), `PARTIALLY_VERIFIED` (only a search summary, a secondary source, or part of the claim), `CONFLICTING`, `UNVERIFIED`. Nothing here is a claim that a technique will raise views: YouTube publishes no formula, and the exact weighting of its signals is not public.

## Point 1. Free 3D video

| Claim | Label | Source and limit |
|---|---|---|
| YouTube accepts 3D uploads (rectangular 3D, VR180, 360 3D), side-by-side left-right layout, with stereo metadata (`st3d` box for mov/mp4, `StereoMode` for mkv/webm); it plays as 3D only after full processing. No removal notice on the page. | VERIFIED (page) | support.google.com/youtube/answer/7278886. No date on the page; which devices play it in 3D is not stated. Low value for a story channel: few viewers watch stereo. |
| What you make with Blender is your property and may be used commercially; the program is GPL. | VERIFIED | blender.org/about/license |
| Poly Haven assets are CC0: any purpose, no credit needed, may be redistributed. | VERIFIED | polyhaven.com/license |
| Smithsonian Open Access CC0 items include 3D models (glTF, glb, obj), free for commercial use without credit. | PARTIALLY_VERIFIED | Smithsonian's FAQ (dashboard.si.edu/openaccess/faq) returned HTTP 403, so this rests on search summaries that quote it. CC0 covers copyright only; trademarks and other people's rights remain. |
| Depth Anything V2 (single-picture depth estimation): **Small (24.8M parameters) is Apache-2.0; Base, Large and Giant are CC-BY-NC-4.0 (not for commercial use).** | VERIFIED | github.com/DepthAnything/Depth-Anything-V2 README. One vendor page says otherwise; the authors' README wins. Use Small only. |
| The studio already has a 3D animated-film look (`aiart.STYLE_3D`, `house_style`) and paid image-to-video clips (`animate.py`, about $0.24 for 8 s). Real archive pictures are never animated (creator playbook). | VERIFIED (code) | `aiart.py`, `animate.py`, `playbooks/creator.md` |
| The server has 4 CPU cores, 16 GB memory, 65 GB free disk, no Blender; `lspci` listed no graphics card (the tool may be missing, so a GPU is not ruled out). | PARTIALLY_VERIFIED | ssh check, 29 Oct 2026 |

**What "free 3D" can mean for this channel, and what each costs**
1. **Keep the 3D look, cut the cost of motion (recommended to build).** A 2.5D parallax move on the studio's own drawn pictures: Depth Anything V2 *Small* makes a depth map on the CPU, a layered warp moves the camera a little, ffmpeg encodes it. No per-clip fee (paid clips are about $0.24 per 8 s). Needs a new dependency on the server (a container rebuild, only when no render runs). Drawn pictures only, labelled as AI art, as `animate.py` already requires.
2. **Blender with CC0 3D models for a few hero scenes.** Free and legal, but the server has no graphics card, so scenes would be rendered by hand on the owner's PC. Not automatable today.
3. **Stereoscopic or VR180 upload.** Allowed by YouTube, small audience, extra metadata work. Not recommended.
4. **Free AI video generators.** Terms and quotas change and the owner has ruled out anything outside OpenRouter and free models. Not relied on.

**Policy overlap.** Animated or AI-made videos must still show original insight and avoid templates (see Point 5). A 3D look applied identically to every video is exactly the "templated" risk; vary scenes and framing.

## Point 2. Thumbnails

| Claim | Label | Source and limit |
|---|---|---|
| YouTube *recommends* 3840x2160 (Shorts 2160x3840), minimum width 640 (Shorts: height 640), 16:9 ("try to"), JPG or PNG; file limits 2 MB on mobile, 50 MB on desktop. The widely quoted "1280x720, under 2 MB" is not on this page. | VERIFIED | support.google.com/youtube/answer/72431. No update date on the page. |
| `thumbnails.set` accepts up to 50 MB, JPEG or PNG, costs about 50 quota units; returns 403 without upload permission and 429 `uploadRateLimitExceeded` when a channel sets too many thumbnails. | VERIFIED | developers.google.com/youtube/v3/docs/thumbnails/set |
| Test & Compare: up to 3 titles and/or thumbnails; **the winner is chosen by watch time, not click rate**; usually finishes in a few days to 2 weeks; outcomes Winner, Performed Same, Inconclusive; computer only; not for Shorts; variants should differ clearly; any variant under 1280x720 makes all be shown at 854x480; changing the title or thumbnail during a test stops it. | VERIFIED | support.google.com/youtube/answer/16391400 |
| The Data API can run Test & Compare. | UNVERIFIED | No official statement found (also listed in `rules.json` `unverified`). Treat it as a manual Studio tool for the owner. |
| YouTube's own advice: show familiar features or relatable emotion, use the rule of thirds, a readable font, not too busy, as large as possible, accurate; titles accurate, key words first, searchable or intriguing; check CTR in 24 h. | VERIFIED (advice, not rules) | support.google.com/youtube/answer/12340300 |
| A thumbnail that misleads viewers into expecting something not in the video is not allowed; maliciously misleading titles, thumbnails or descriptions can cost monetization or the channel. Documentary context may earn an exception, at YouTube's discretion. | VERIFIED | answer/9229980 and answer/2801973 |
| In 500 breakout long videos (30 niches, June 2026): 69% had a face, 56% high contrast, 89% one or both; 72% had overlay text, median 5 words among those; 5% an exaggerated expression. | PARTIALLY_VERIFIED | vidIQ's own study (vendor), and it states it describes what breakouts share, not what causes clicks. |
| Other figures seen (a face adds 33% CTR; thumbnails explain 70 to 80% of CTR variance; eye-tracking claims). | UNVERIFIED | Marketing pages with no checkable method. **Not used.** |

**What the studio does.** Thumbnail text prompt (honest, 2 to 4 words, adds a word the title lacks), kind cards, a scoring rubric (focal point, mood, contrast, legibility, text adds information, honest match) and a thumbnail made at 1280x720, which meets YouTube's test minimum. This already matches what the sources support, so **no change**. The 2 to 4 word range is the owner's judgement; the only data found shows a median of 5 words and is not causal. Settle it with the channel's own data: run Test & Compare on documentaries (Studio, by hand).

## Point 3. Keeping viewers in long videos

| Claim | Label | Source and limit |
|---|---|---|
| YouTube's retention report highlights four key moments: Intro (share still watching after the first 30 seconds), Top moments (almost no one dropped), Spikes (rewatched or shared), Dips (skipped or stopped). Needs at least 60 s and 100 views. Absolute retention can exceed 100% when people rewatch; relative retention compares with similar-length videos. | VERIFIED | support.google.com/youtube/answer/9314415 (the relative/absolute descriptions come from a search summary). |
| YouTube says it aims at viewer satisfaction, not clicks: signals include clicks, watch time, survey answers, shares and likes; "valued watch time" counts only 4 or 5 star surveyed views. Exact weights are not public. | PARTIALLY_VERIFIED | YouTube Blog "On YouTube's recommendation system" and Help (answer/16089387), read through search summaries only; the blog is several years old. |
| YouTube's own hook advice: start with a question; tell viewers within the first five seconds what they will see; use a cold open; brand with a bang. | VERIFIED but dated | blog.youtube "Four tips to hook your viewers on YouTube", **published 24 June 2014**. |
| In 6.9 million edX lecture-video sessions "shorter videos are much more engaging". | VERIFIED (abstract) | Guo, Kim, Rubin 2014 (L@S). The "under 6 minutes" figure often quoted could not be confirmed from the paper text. It studies course lectures, so it does not transfer cleanly to a documentary. |
| Curiosity comes from noticing a gap in what you know when the answer seems reachable. | PARTIALLY_VERIFIED | Loewenstein 1994, Psychological Bulletin 116(1) 75 to 98: the citation is confirmed, the claims come from secondary summaries. |
| "Re-hook every 60 to 90 s", pattern interrupts, open loops as measured retention effects. | UNVERIFIED | Creator lore with no primary measurement found. The 90 s limit is the owner's rule (`rehook_max_seconds`), kept as a warning only. |

**What the studio does.** The documentary prompt already opens cold on the strangest fact or central question, adds a question or turn every 60 to 90 s, labels each explanation, ends on the story with no thanks or subscribe line and leaves one question open; `reviewer.generator_checks` warns on each. **No change.** To use YouTube's own report: open a published documentary's Analytics, read Intro and the Dips, and match each dip to the script line at that time.

## Point 4. Shorts: hook, curiosity, story or value, payoff

| Claim | Label | Source and limit |
|---|---|---|
| Shorts are ranked on performance and personalisation; the signals are the share of viewers who chose to view, average view duration and average percent viewed. "Our system has no opinion about what type of Shorts you make." | VERIFIED | support.google.com/youtube/answer/11914225 |
| Since 24 Aug 2026 a view is counted the moment playback starts. **Engaged views** are views that stayed past the initial seconds, not counting loops. "Stayed to watch" is the share who did. Partner Program earnings use engaged views. "Initial seconds" is not defined. | VERIFIED | support.google.com/youtube/answer/12220281 |
| The Analytics API metric `engagedViews` is "viewed past the first frame, or the user clicks/taps to play", and the page does not mention Shorts. | CONFLICTING with the Help wording | developers.google.com/youtube/analytics/metrics. Whether "Stayed to watch" is readable from the API is unknown. |
| Hook within the first seconds; fast pace; one clear point; large captions for silent viewing. | PARTIALLY_VERIFIED | YouTube Blog guidance (search summary) and third-party creators. Exact windows such as 1.5 s or 3 s come from unverified creator videos and are **not used**. |
| The hook, curiosity, value, payoff sequence. | Design, not a YouTube formula | Built from the ranking signals above (the first line must earn the stay, the rest must reward the watch) and the curiosity-gap idea in Point 3. |

**The studio's Short beats.** (1) Hook: line 1, twelve words or fewer, a question or a turn. (2) Curiosity: the question stays open while the setting and tension build. (3) Story and value: specific facts from the source, nothing invented. (4) Payoff: the line before the invitation answers the hook, or says plainly what the sources disagree on, never a new question. (5) A short invitation to follow. Loops: **never ask viewers to loop** (a studio hard rule), and loops are excluded from engaged views anyway.

## Point 5. Platform rules re-read (changes a status in the rules file)

- **Inauthentic content** (renamed from "repetitious content" on 15 Jul 2025): not eligible are content that looks made from a template, has minimal variation, or is AI content from generic templates that gives an impression of mass production; original, authentic insight or perspective is needed. Source: support.google.com/youtube/answer/1311392, read 29 Oct 2026. **`rules.json` had this UNVERIFIED and dated "July 2026"; the page's latest dated update is 15 Jul 2025. It is now VERIFIED, and the summary no longer implies that YouTube requires two extra sources and an original element: those are the studio's own safeguard.** The page does not mention animation specifically.
- **Misleading thumbnails and titles:** added as a VERIFIED constraint (Point 2).
- `distressing_content` stays UNVERIFIED.

## What changed in the studio

| Change | Why (evidence) | Check |
|---|---|---|
| `scriptgen.short_prompt`: payoff beat before the invitation; never end on a new question | Point 4 ranking signals; the old prompt ended on "a closing line that lingers" then a follow line, with no payoff rule | `tests/test_generator_rules.py` |
| `reviewer.generator_checks`: `short_hook` and `short_payoff`, warnings only, limit `short_hook_max_words` (12) read from the rules file | the prompt asked for a 12 word hook but nothing checked it | `tests/test_generator_rules.py` (5 tests) |
| `rulesfile.py` and `config/rules.json`: inauthentic content VERIFIED and re-worded, misleading thumbnails added, the `engagedViews` question added to `unverified`, new benchmark | Point 5 | `tests/test_rulesfile.py`, shipped and default values equal |
| `playbooks/creator.md`, `playbooks/clipper.md`: Short beats | Points 4 | `playbook.problems` empty |
| `agenteval` case plus 3 mutation checks (no payoff in the prompt, any first line accepted, creator's Never rules cut off) | project rule: every agent change needs a case and a mutation check | `tests/test_agents_training.py` |

**A near-miss worth knowing.** A playbook goes into prompts cut at 1,500 characters. My first edit of `creator.md` pushed its safety rules ("Animate a real archive picture", the per-video spend limits) out of that window. It was caught, the text was tightened, and the eval case now fails if the creator's `Never` section is ever cut.

## Not done, and why

- **Free 3D motion (option 1):** needs the owner's yes for a new server dependency and a build; nothing was installed.
- **`engagedViews` in the collector:** the definitions conflict, and past experience here is that a query shape can pass tests and fail live. Probe a live query first (as `GROWTH_API_PROBE_2026-10-28.md` did), then add.
- **Test & Compare:** manual, by the owner, in Studio.
- **Thumbnail resolution:** YouTube's 3840x2160 is advice; 1280x720 meets the test minimum. Raising it costs picture money for no sourced gain.
- **Unread sources:** the Smithsonian FAQ (403); the recommendation-system pages were read only through search summaries; the full text of the engagement paper's recommendation table.

## Limits

A prompt and a warning guide a model; they do not make a script good. Passing these checks shows the rules hold on test cases, not that views will rise. Every figure from vendors or creators above is descriptive or unverified; none was turned into a rule.
