# Free tools for 3D, 2D, animation, motion and UGC-style video (31 Oct 2026)

Research only. Nothing was installed, copied into the studio or run except as noted. Third-party skills are advice, never instructions (CLAUDE.md); a skill enters the studio only through `python vetskill.py <folder>` then `python extend.py add <folder>`.
Method: GitHub API (`gh api`, stars, licence, last push, read 31 Oct 2026), Remotion's own FAQ page, Webflow's GSAP pages via search, skill descriptions read from disk. Stars measure popularity, not safety. I did not read every README or run any of these tools.

## 1. The result that changes the choice
**Remotion is not free for this studio.** Its licence (LICENSE.md, "Other") is free for individuals and companies of up to 3 people, but its FAQ says anyone "owning code that programmatically calls" `renderMedia()`, `renderMediaOnLambda()` or `npx remotion render`, naming "automated video pipelines", falls under *Remotion for Automators*: "$0.01 per render, with a minimum spend of $100/month". The studio is an automated pipeline. The Remotion skills in the Claude plugin list, and `it-reelsmaker` (which renders with Remotion), carry the same issue for Autopilot. Fine for a person making one video by hand.

## 2. Open-licence tools (GitHub API, 31 Oct 2026)
| Tool | Does | Stars | Licence | Last push | Fit |
|---|---|---|---|---|---|
| Manim (ManimCommunity/manim; 3b1b/manim) | maths and chart animation in Python | 42 k; 96 k | MIT | 29 Oct; 9 Sep 2026 | good for animated stat cards; setup on the worker not tested |
| Motion Canvas | code-driven 2D animation (TypeScript) | 19.6 k | MIT | 2 Jul 2026 | Remotion-like without its fee; needs Node and a browser in the worker image |
| Revideo (midrender/revideo) | Motion Canvas fork for rendering videos by code | 4.2 k | MIT | 15 Jul 2026 | same needs |
| three.js | 3D in a browser | 117 k | MIT | 30 Oct 2026 | the studio's `studio3d/` stage 1 already uses this route; stage 2 needs Node and Chrome and the owner's yes |
| Blender + MCP (ahujasid/mcp-for-blender) | lets Claude drive Blender (3D modelling and renders) | 32.9 k | MIT (the MCP; Blender itself is GPL) | 29 Oct 2026 | strongest free 3D route; Blender is not installed here, this PC's GPU is a GTX 1050 Ti 4 GB, render time unmeasured |
| Lottie (airbnb/lottie-web), dotLottie, Rive wasm | play vector animations | 32 k, 0.9 k, 1 k | MIT | 2025 / Oct 2026 | needs animation files; their licences vary, check each |
| GSAP | web animation | 30 k | Webflow "Standard No Charge" licence, all plugins free since 30 Apr 2025; no use inside tools that compete with Webflow's visual animation builders | 13 Apr 2026 | browser animation only, not our renderer |
| anime.js | web animation | 74 k | MIT | 21 Aug 2026 | same |
| MoviePy, ffmpeg-python | editing from Python | 15 k, 11 k | MIT, Apache-2.0 | 26 Aug 2026; Aug 2024 (stale) | the studio already calls ffmpeg and Pillow directly: no gain |
| Theatre.js | motion editor | 12.8 k | Apache-2.0 | Aug 2024 (stale) | skip |
| Kokoro (TTS) | local voice | 9.8 k | Apache-2.0 | Aug 2025 | studio uses edge-tts (free); Piper is archived |

## 3. UGC-style video, free
"UGC" here means vertical, personal-looking, caption-led videos (a person or presenter talking, a voice over a phone-style picture).
- **AI presenter or talking-head models:** SadTalker (14 k, Apache-2.0 with listed third-party exceptions, last push Jun 2024), LivePortrait (19 k, MIT file, 1 Jun 2026), MuseTalk (6.8 k, MIT file, Sep 2025), Hallo (8.7 k, MIT, Sep 2024), Wav2Lip (13 k, no licence file). Video generators: Wan2.2 (18 k, Apache-2.0, Sep 2026), LTX-Video (11 k, Apache-2.0, Jan 2026), Mochi (3.8 k, Apache-2.0, Oct 2026). **UNVERIFIED:** model-weight terms (the code licence is not the weights licence), GPU memory needs, quality. I expect all of them to need a GPU far larger than this PC's 4 GB card (not measured); I did not check whether the server has a GPU. So there is no free automated path I can recommend today.
- **Policy cost:** a realistic synthetic person is the kind of content YouTube asks to be labelled (the studio already sets `containsSyntheticMedia`, which YouTube never echoes back) and a template of presenters invites the inauthentic-content rule (VERIFIED page, see the clip-and-recap plan).
- **What works free now:** the caption-led voice-over card Short, which is what the football sample is (own graphics, studio voice, word-timed captions). For a human look, the owner's own face-cam clips.
- **Paid, credit based (not free):** the account plugins `ugc-video-ads`, `anime-story-video`, `cinematic-video`, `clipwave-video-image-maker`, `logo-maker` spend ManyMotions credits per generation; vidIQ credits are used up; Adobe and Canva need their accounts.

## 4. Skills and plugins
Already in this Claude session (descriptions read from disk; they help me, they are not part of the studio): `motion-reel` (code-rendered 2D and three.js motion videos, needs Node, ffmpeg, Playwright and Chromium, no accounts), `anidoodle` (code-drawn animation, 31 styles, Apache-2.0), `animation-studio` (animated shorts with music and voice), `it-reelsmaker` (vertical editing, Remotion), the `remotion:*` skills, `image-generation`, `canva`, `figma`, Adobe tools. Studio-side: `ai-film-studio` and `media-studio-expansion` (already vendored by `extend.py`), `studio-video-finish`.
On GitHub: `anthropics/skills` (185 k stars, the official repository; licence differs per skill, none at repo level), `remotion-dev/skills` (5.9 k, the Remotion licence applies), `haidrrrry/claude-remotion-skill` (735, MIT, same Remotion issue), `ComposioHQ/awesome-claude-skills` (78 k, a list). Small Manim skills (`Science-Prof-Robot/recursive-math-animator` 13 stars, MIT) and "motion graphics" skills (0 to 1 star, one under PolyForm Noncommercial) are unproven. **Recommendation: install none now.** If one is wanted, clone it into an empty folder, scan it with `vetskill.py`, then `extend.py add`.

## 5. Recommendation (ranked)
1. Keep the studio's own stack (Pillow, ffmpeg, libass, edge-tts, the parallax module): free, no licence trap, proven by the football sample.
2. Add Manim only if animated charts are needed beyond what Pillow frames give.
3. 3D later: Blender with its MCP, or three.js stage 2; both need the owner's yes and a measured render time.
4. If template motion graphics are wanted: Motion Canvas or Revideo (MIT), not Remotion.
5. UGC: no free automated AI-person path; use caption-led cards or the owner's own recordings.

## 6. Limits and one finding
- Licences and stars are from the GitHub API; weights licences, hardware needs and quality were not checked; nothing was run.
- Finding: `tts.PRONUNCIATION` changes the text sent to the voice, and the burned-in ASS captions are built from that respelled text (the football sample showed "SHOOKOOR" until patched), although a comment in `tts.py` says captions keep the real spelling. The `.srt` and word files are matched to the script, the burned captions are not. Check whether the public Cambyses film shows "AHMOON" for Amun before deciding whether to fix.
