# Branded 3D animation for the channel: research, proof and plan (30 Oct 2026)

**Owner's words (30 Oct):** not approved; "you could create a full 3D animation video that looks professional and could create a brand channel"; use Remotion, Remotion skills, Motion Canvas, Motion, GSAP, Anime.js, Rive, dotLottie, Three.js and the pmndrs 3D family, SVGO, Satori, Howler, Mediabunny, FFmpeg; research on Google and YouTube, check the research again, plan, then implement; keep it cost efficient and fitting the current system.

## What was wrong with the Cambyses film (checked, fixed locally, commit 9da1ac9, tested, NOT deployed)
1. **Same footage twice.** `render.py` looped (`-stream_loop -1`) any clip shorter than its scene. Seven of the eight animated scenes were 8.2 to 10.2 s on 8 s clips (measured from words.json). Now `render.clip_fit`: slowed at most 1.25x, the rest held on the last frame, never looped.
2. **Big, bending faces.** The depth warp (`parallax.py`) bends a picture by depth (stretched nose seen at 8 s), the plain camera is ffmpeg `zoompan` (whole-pixel steps), and some plans zoom to 1.45x. Now a picture whose note does not say "no people" gets a flat sub-pixel zoom with no depth shift and a push of at most 8 percent (`parallax.depth_safe`, `flat_scenes`, `gentle`). A global motion measure I tried was flawed (same value on every scene) and is not used as evidence.

## Checked facts (labels: VERIFIED = read at the source, REPORTED = third party only)
- Remotion licence VERIFIED (remotion.dev/docs/license/faq): free for an individual, personal or commercial, and for a team of up to 3 people; automation allowed under the free licence; server telemetry voluntary; the Remotion 5.0 change affects "Automators" customers, not free users. "Total headcount" is defined in terms we did not read: if other people's studios on the server ran Remotion, the count could pass 3. Keep it to the owner's studio until that is settled.
- Licences VERIFIED by the GitHub API on 30 Oct: MIT for Motion Canvas, Motion, Anime.js, Rive web runtime, dotLottie web, three.js, React Three Fiber, Drei, React Three Rapier, React Postprocessing, SVGO, Howler; MPL-2.0 for Satori and Mediabunny (fine unmodified); Zlib for `postprocessing`; Remotion and FFmpeg have their own licence text; GSAP has its own no-charge licence (free for commercial use unless end users are charged; REPORTED by Webflow's pages); `remotion-dev/skills` states NO licence, so read it as advice and never copy it into our repo. Scan: `vetskill.py` 0 high, 34 medium (unscanned file types and links), 11 low.
- Remotion skills (REPORTED by the repo page): `npx skills add remotion-dev/skills`; 12 skills, including markup (animation, layout, typography, audio), captions, maps (CesiumJS flyovers), render. No dedicated three.js skill.
- Free 3D assets (REPORTED by one aggregator, not the sites): Kenney and Quaternius CC0; Poly Pizza mostly CC-BY. Rule: CC0 only, check each pack's own page, record it in the credits file.
- Google Flow: needs a Google AI plan, no official API (see 2026-10-30-real-3d-and-motion.md). AI clips cost $0.24 per 8 s: a 9 minute film fully animated would be about $16.

## Measured proof (my PC, 6 cores; scratch project, not committed)
Remotion 4.0.539 + three.js 0.186 + R3F: a 3D dune scene with 360 low-poly soldiers marching and fog closing in, 1280x720, 24 fps.
- GPU (`--gl=angle`): 72 frames in 5.7 s including start-up.
- CPU only (`--gl=swangle`, what the server must use): 24 frames in 6.6 s including start-up, frame identical to the GPU one.
- Estimate, NOT measured on the server (4 shared cores): about 0.2 to 0.5 s a frame, so a 9 minute film that is entirely 3D (13,000 frames) would take 45 to 110 minutes of background CPU, and nothing in dollars.
- Quality: honest verdict, a crude first prototype (block soldiers, empty sky, framing off). It proves the pipeline and the speed, not a professional look. Professional needs art direction: CC0 character and prop models, a sky and lighting set, post effects (bloom, depth of field), dust particles, camera rules, a fixed palette.

## Tool by tool (what to use for a rendered film)
| Tool | Verdict | Why |
|---|---|---|
| Remotion + skills (read only) | USE | frame-based and deterministic, free for us, composes scenes, titles, chapter cards, captions, audio |
| three.js, R3F, @remotion/three | USE | real 3D scenes at zero per-clip cost |
| Drei, React Postprocessing | USE (stage 1 to 2) | sky, instancing, bloom, depth of field; costs GPU or CPU time, measure each |
| Rapier physics | LATER | stepping must replay from frame 0 to stay deterministic; only for a special effect |
| Satori, SVGO | LATER | title cards are easy in Remotion itself; Satori helps make thumbnails without a browser; SVGO when we adopt SVG icons and maps |
| Anime.js, GSAP, Rive, dotLottie, Howler, Motion (+AI Kit) | SKIP for the film | they are for interactive pages and real-time clocks; Remotion's `interpolate` and `spring` do the same frame by frame; GSAP can be seeked but adds nothing. Revisit only for a dashboard or a web preview |
| Motion Canvas | SKIP | MIT but 2D canvas only |
| Mediabunny | SKIP | Remotion already uses it |
| FFmpeg | KEEP | audio mix, loudness, final encode, joining, checks (already the core) |

## Brief: how this lowers cost and fits the system
- Today a documentary costs about $1 for a stills film, and about $4 for one film with 8 AI clips plus redraws (this session). Animating all of it with AI clips would be about $16.
- Programmatic 3D has no per-clip price: rendering is background CPU. Model money goes only to planning (about $0.1 to 0.3 for a scene plan) and to the AI pictures and the few AI clips that remain (estimate: about $2 a film instead of $4 to 16, an estimate until a real film is built).
- It fixes the two faults at the root: a 3D scene has no faces to bend, and a scene is rendered to the exact length it needs, so nothing loops.
- It is the owner's brand: one palette, one camera language, one set of 3D props, chapter cards and date badges drawn by Remotion instead of subtitle tricks (`motiongraphics.py`). It also gives the "original element" the platform rule asks for (the studio's own reading, not YouTube's words).
- Fit: a `studio3d/` Node project in the repo, a `scene3d.py` director (a model turns the checked script into a scene plan from a fixed list of templates and parameters; it may use only what the script says), the render writes one mp4 per scene into `cache/anim/`, and `render.py` already takes those (no darkening, fitted once). Money rules, holds, reviewer checks, claim ledger and review window stay as they are.

## Stages (each ends with a check I read before the next)
0. Deploy the two fixes (commit 9da1ac9) and re-render the Cambyses film (cached, about $0.1). Owner's yes needed.
1. Brand kit and three scene templates (army march, caravan and flyover, sandstorm) with CC0 assets and post effects; contact sheet to the owner; measure render time on the server.
2. Node 22 and the Chrome headless shell in the worker image, a low-priority 3D render queue (`nice`), the scene director with tests, an `agenteval` case and mutation checks, cost scopes (all zero dollars, time recorded). Needs the owner's yes for the new dependency.
3. First branded film (Cambyses) with the owner's approval of the look.
4. Vertical Shorts (1080x1920) from the same templates.
5. Autopilot switch (`house_style`), after one approved film.
Risks: CPU time on the shared server, the look (needs art direction and the owner's eye), asset licences (CC0 only), the Remotion headcount rule if other studios use it, Node and Chrome in Docker, upkeep.

## Decisions the owner must make
1. Yes to stage 0 (deploy and re-render).
2. Yes to stage 1 (a proof of the look on the PC, no server change).
3. Style: low-poly stylised 3D, or a more painterly look.
4. The channel's brand: name, colours, logo mark.
