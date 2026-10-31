# Plan: a studio for "football clip Shorts" and "film recap" videos (31 Oct 2026)

Status: PLAN ONLY. Nothing is built, deployed or spent. Owner decisions are in section 7.

## 1. What was looked at (coverage statement)
Three links the owner gave. For each I read the official YouTube metadata (`run.py inspect`, saved in `data/research/<id>/metadata.json`) and **looked at the thumbnail image only**.
No frame of any video was seen, no audio heard, no transcript read (the vidIQ connector had no credits; YouTube's API gives no transcript for other channels; downloading other people's videos is forbidden by YouTube's terms and by CLAUDE.md B). `whole_video_watched` is false for all three.
The studio's own vision reading failed (local OpenRouter key returned 401); I read the three thumbnails myself.

| | Video | Channel | Length | Views / likes / comments | Published |
|---|---|---|---|---|---|
| 1 | `O-8WkPzWSw0` "Classic Cristiano Ronaldo 😮‍💨" (Short) | FIFA (official) | 11 s | 38,835,864 / 489,149 / 5,443 | 2025-08-30 |
| 2 | `C-ZI7D8ZtUQ` "Ronaldo Won The Saudi League Trophy 🚨🤩" (Short) | Slicx7 | 25 s | 4,062,247 / 81,935 / 1,000 | 2026-05-21 |
| 3 | `R3Xqm0KtPa4` "He Loses Everything and Must Learn to Survive Alone \| Film/Movie Explained In Hindi/Urdu" | Prince Explains | 19 min 21 s | 38,917 / 312 / 22 | 2026-10-28 |

Seen in the thumbnails (facts): 1 is 16:9 match footage shown vertically with a blurred copy filling the sides, a player in a Portugal kit, a pitch-side advert board. 2 is a vertical crop of match footage with a bold yellow caption "*GETS EMOTIONAL...*", a channel name over the picture and a small logo badge top-left (I cannot say whose). 3 is a wide, very smooth desert scene with a man and a woman at a well beside a wooden hut (I cannot tell a film still from an AI picture).
From the text: 2 and 3 have a "fair use" disclaimer in the description; 3 has 16 tags (film-type, "true story", "desert survival", "explained in hindi") and "Follow me on Instagram"; none has captions on YouTube.

## 2. What these videos are (inference, labelled)
- **1 and 2: football clip Shorts.** One famous person, one emotional beat, 11 to 25 s, news-style or nostalgic title with an emoji, a big caption in the first second. INFERENCE from metadata and one thumbnail: the footage is somebody else's broadcast. Video 1 is posted by FIFA itself (the rights holder). Video 2 is a third party; its description relies on a disclaimer. Whether either has original commentary is NOT KNOWN.
- **3: a film recap ("movie explained").** A long narration that retells a film's whole story under an emotional-stakes title, in Hindi/Urdu, aimed at a language audience. INFERENCE: it uses the film's footage under the narration; not verified.
- Performance is not proof of a method: 1 is a rights holder with a huge channel; 3 has 39 k views.

## 3. The rule that shapes the whole plan
All three formats are normally made from other people's footage. This studio may only use public domain, CC0, free-licence or labelled AI pictures (CLAUDE.md D), and never downloads other people's videos.
Read from YouTube's own pages on 31 Oct 2026 (VERIFIED, page wording):
- Reused content = repurposing content already online "without adding significant original commentary, substantive modifications, or educational or entertainment value" (support.google.com/youtube/answer/1311392). Allowed: "Using clips for a critical review", reaction with commentary, "Edited footage from other creators where you add a storyline and commentary". Not allowed: "Clips of moments from your favorite show edited together with little or no narrative", "Short videos you compiled from other social media websites". The page does not mention recaps. It lists "Replays of a sports tournament where you explain the moves a competitor did to succeed" as allowed.
- Fair use (support.google.com/youtube/answer/9783148): YouTube cannot decide it, "There aren't any magic words", "no infringement intended" gives no protection; the page does not mention film or sports clips. So the disclaimers on videos 2 and 3 protect nothing.
- Shorts and Content ID (support.google.com/youtube/answer/13053317): a claimed Short can be blocked or must have the claimed content removed; I did not pin the exact length rule, re-read before relying on it.
Blogs (not official, unverified): broadcast match footage is claimed quickly by leagues; recap channels that swap clips on one formula are a demonetization risk; some sources say YouTube's July 2026 partner-programme wording names template-based videos. Treat as leads.

**So: copy the FORMAT, never the FOOTAGE.** The system below keeps what makes the examples work (a name people search, one emotional beat, a stakes title, a caption in the first second, a whole story told clearly) and replaces the footage with sources we may use.

## 4. Two packs
### Pack A: story recap (long form, 8 to 15 min)
Source of the story, in the order I recommend:
1. **A1, true stories and legends in a recap voice** (Wikipedia + primary sources, drawn scenes, real free-licence clips). This is what the studio already does; the new part is the title and structure ("what happened, step by step, what it means") and a language pack. Cheapest and safest.
2. **A2, public-domain books and folk tales** retold with drawn scenes.
3. **A3, public-domain films** with the film's own footage and our narration. US public domain on 1 Jan 2026 took in works from 1930 (Internet Archive and Duke's Center for the Study of the Public Domain list them; *All Quiet on the Western Front* (1930) is named). Caveats: public domain in the US only; foreign copyright can run longer; a distributor's restoration or a Content ID match can still produce a claim. Every film needs a rights record before use.
4. **Not in scope:** recapping a film still in copyright with its footage. A recap with our own art only is a grey area (a close retelling of a plot): needs the owner's and a lawyer's view, not built here.

### Pack B: football Shorts (15 to 45 s)
- **B1 (build):** number and story Shorts with our own graphics (animated stat cards, timelines, trophy and stadium scenes, a big word-timed yellow caption like video 2's look), a voice, facts from an official or primary stats source. **No real person's likeness** from AI (a footballer's face): symbols, shirts without names, charts.
- **B2 (bonus):** free-licence footage where it exists. A web search on 31 Oct found NO confirmed freely licensed match video (only photos); `footage_real.py` already checks licences, so it can try Commons and will often find nothing.
- **B3 (not planned):** licensed broadcast footage (paid, needs an agreement).
- **Never:** clips of broadcasts, however short, with a disclaimer.

## 5. System design (reuse first)
| Need | Existing piece | New work |
|---|---|---|
| Separate channel so the "sleeping library" brand is not diluted | user studios (`deploy/tenant.sh`, `niche.py`, `tenantmode.py`); one test studio exists | owner decides (7.1); a tenant never gets the Gloamtale pop-up or mark |
| Kinds of video | `kinds.py`, `config/kinds.json` | cards `recap` and `football` (title pattern, hook, thumbnail line) |
| Script | `scriptgen` (`CASE_RULES`, doc and Short prompts), `scriptreview` | `RECAP_RULES` (stakes hook, steps, ending explained, what is source-said vs disputed); `FOOTBALL_RULES` (one fact per line, number first, no claim about a living person without a source) |
| Facts | claim ledger, `webcheck`, second sources | football stats must come from an official page; the ledger row keeps the URL |
| Voice and language | `tts.py` (edge-tts). Checked 31 Oct: voices exist: `hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`, `ur-PK-AsadNeural`, `ur-PK-UzmaNeural`, `ur-IN-GulNeural`, `ur-IN-SalmanNeural` | language field on a video; caption fonts (Devanagari, Nastaliq) and right-to-left shaping in the ASS captions (UNTESTED: must be proved on a real render); reviewer checks that assume English (word counts, title rules, hook-word limits) made language-aware; `voicecheck` listener tested in Hindi/Urdu |
| Pictures | AI scenes, parallax, `footage_real.py` | A3 only: a film rights register (`data/rights/films.json`: archive.org id, year, public-domain basis, country, date checked), a scene index of the film (cuts + a vision caption per scene, `videoinspect` already samples frames), matching narration lines to scenes; B1 only: a stat-card renderer (Pillow/ffmpeg) |
| Licences | `studiochecks.licenses` | accept "public-domain film" only with a rights record |
| Titles | `packaging`, reviewer title checks | stakes titles allowed ("He loses everything…") only if the video delivers; no misleading titles (VERIFIED constraint) |
| Sameness and pace | `governor`, `duplicates`, `weekplan` | per-pack caps; one story one video per format |
| Safety, money | reviewer, gate, hold, daily cap, per-video cost limits | limits per pack (see 6) |
| Every agent change | playbook + `agenteval` case + mutation check (CLAUDE.md) | one each per new rule |

## 6. Phases (each ends with a test run, a look at real frames, and a held draft; nothing goes public by itself)
0. **Decisions** (section 7). No code.
1. **Language pack** (about 1 day): a 60 s Hindi and a 60 s Urdu sample from an existing script, captions rendered and looked at, listener check. Cost about $0 (free voice) plus a few cents for the listener. Exit: captions read correctly right to left; if not, stop and report.
2. **Pack A1** (about 2 days): `recap` kind and rules, tests, one film of about 8 min as a held draft. Cost about $1 to $4 depending on the look (photo look is about $3.5 to $4 per CLAUDE.md; the account has $4.44 and a $5 daily cap).
3. **Pack B1** (about 2 days): stat-card renderer, `football` kind, three Shorts as held drafts (estimate $0.1 to $0.6 each; unmeasured).
4. **Pack A3** (about 3 days, only if the owner wants it): rights register, scene index, one public-domain film with every rights proof on file.
5. **Measure** with the growth collector after the first 10 videos of a pack: retention at 30 s, percent viewed, subscribers gained. Stop a pack that does not beat the channel's own median.
Evidence rule for every phase: report tests actually run, frames actually seen, claims still UNVERIFIED.

## 7. Decisions needed from the owner
1. **Where does it live?** A new studio (own channel and YouTube login) is my recommendation; football Shorts and recaps do not fit the sleeping-library channel. Or inside the current channel (dilutes the brand; the governor will see sameness).
2. **Language:** English, Hindi, Urdu, or all? Which first?
3. **Footage policy:** accept "no third-party broadcast or film footage" (recommended; matches CLAUDE.md D and YouTube's reused-content page), or the fair-use route (not recommended: YouTube says it cannot protect you).
4. **Football likeness:** OK to use no AI picture of a real player (symbols, charts only)?
5. **Money:** OpenRouter credit is $4.44 (about a day of spend). Phase 2 needs a top-up.
6. **Pack A3:** do you want public-domain film recaps at all (needs rights work per film)?

## 8. Not verified / limits
- Nothing about the three videos' picture, sound or narration was seen or heard beyond the thumbnails and metadata.
- The July 2026 YouTube partner-programme details are from secondary blogs only.
- Copyright terms outside the US (India, Pakistan, where a Hindi/Urdu audience lives) were not checked.
- Hindi/Urdu caption rendering, reviewer behaviour in another language and listener accuracy are untested.
- A sports-footage free-licence source was not found, not proven absent.
- No view-count or retention evidence exists that these formats work for a new channel; the only numbers are the three videos' public totals.

## 9. Sources read (31 Oct 2026)
YouTube Help: support.google.com/youtube/answer/1311392 (monetization policies), /9783148 (fair use), /13053317 (Shorts and claims). Searches (blogs, secondary): AIR Media-Tech and others on inauthentic and reused content; VidIQ and others on recap channels; fluxnote.io and openclip.app on football clips; Internet Archive and Duke CSPD on Public Domain Day 2026.
