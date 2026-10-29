# Real 3D and motion for the films (plan, 30 Oct 2026)

**Owner's words (30 Oct):** the first frame and the second frame faces are wrong; create new images; "I told you to create 3D and motion video, you did not fulfil both"; learn from the Short https://youtube.com/shorts/n0MC7hQodIY; tell me which skills and plugins Autopilot uses; Google Flow may be used, I know nothing about it; research first, then plan, then do it step by step.

## What was true (checked)
- The Cambyses film is in `photo` style with `parallax` (free 2.5D camera motion on stills) and `graphics` (2D cards). It never had `animate` (real image-to-video clips) and never used `art_style: 3d`. So the owner is right: only two of the three things were delivered.
- First frame: the distorted face came from the picture, and the camera motion stretched a second face (nose) at 8 s. Fixed by a new back-view picture (third try) and a wide Siwa view for the second scene; 58 pictures were looked at, none else is clearly broken, 9 are repeats (new lines reuse pictures).
- Reference Short (public API data only; not watched, project rule): a 43 s tutorial "How to create Explanation Videos with AI", channel AI by Moiz, 310 views, tagged Google Flow; its prompt is behind "comment Flow". It shows nothing we can copy except that the maker uses Flow.

## Research (30 Oct; third-party prices are labelled)
- Google's Flow help page (support.google.com/labs/answer/16353333): access needs Google AI Plus, Pro or Ultra (or a qualifying Workspace plan, 50 daily credits); the cost of a clip is shown inside the product; every output has an invisible SynthID watermark; commercial use follows Google's terms. No free tier is described there.
- No official Flow API found. Programmatic Veo is through the Gemini API or Vertex (per second; third-party lists Veo 3.1 Lite about $0.05 a second at 720p, Fast $0.10, standard $0.40; unverified). Our own measured price through OpenRouter: Veo 3.1 Lite $0.24 for an 8 s clip.
- Automating a logged-in Flow session with extensions would break the rule "no bypassing logins" in CLAUDE.md B: not an option. Flow stays the owner's hands-on tool.
- YouTube label: `upload.py` already sets `containsSyntheticMedia` on every upload; the compliance rule `ai_disclosure` was verified on 20 Oct.

## Measured today (two clips, $0.48)
- Clip 1, old prompt: real motion, the face stayed natural, but after 3 s the model invented fire and explosions ("warm light flickering"). Not acceptable in a documentary.
- Clip 2, new prompt (`animate.motion_prompt` bans invented fire, explosions, people and objects): the soldier walks away, a dust storm builds and swallows the scene; no invention. Cached at `cache/anim/fe422c5a18027f1e051a.mp4` for the new prompt (the server needs this code deployed to reuse it).

## Steps
1. [x] First and second picture replaced; film re-rendered (render 2); frames looked at.
2. [x] Motion prompt fixed with a test, an `agenteval` case and a mutation check; one clip proved it.
3. [ ] Owner decides: yes to deploy this commit; budget and clip count for the Cambyses film (suggest 8 clips, $1.92: opening, sandstorm, 2000 expedition, Kaper scenes, closing); the daily cap has $0.46 left and credit is $11.94 (Risks: money at act).
4. [ ] Switch `animate` on for the film (`animate`, `animate_budget` in its record), re-render once, look at every animated second, run review and gate. Never animate an archive picture; clips are credited as AI video.
5. [ ] Flow path (hands-on, only if the owner has a Google AI plan): the studio writes one Flow prompt per scene (picture, motion, what must not appear), the owner makes the clips in Flow and adds them on the Footage page; the studio assembles and credits them. Check Google's terms for the owner's plan first.
6. [ ] Shorts: `--style 3d --animate 4` (3D-look pictures cost $0.067 each, a clip $0.24); a new 3D documentary costs about $4 in pictures before clips, so it needs the owner's budget.

## Not in this plan
Approval, upload, schedule; any automation of a logged-in Google session; claiming Flow is free.
