# Blender integration audit (20 Nov 2026)

## 1. What was there before today
- Blender 5.2.3 LTS installed by the owner's earlier session in `~/tools/blender` (host only). `ccrender.py` + `scenes/` (dunes, temple, stones) rendered a still and its depth map, used only by hand in a Claude Code session (`ccdoc.py` / `ccbuild.py`). Autopilot never used Blender. The studio containers could not run it.
- GPU: the GTX 1050 Ti is present but `nvidia-smi` cannot talk to the driver today (kernel 7.3.4), so Blender renders on the CPU. Not assumed: measured below.

## 2. What was found and fixed (evidence)
| Problem | Evidence | Fix | Status |
|---|---|---|---|
| Blender cannot start in the worker image | `ldd`: libSM.so.6 and libICE.so.6 not found | `libsm6 libice6` added to the Dockerfile; image rebuilt; containers recreated while idle (user 1000:1000, healthz 200) | PASS |
| Blender not visible to the containers | no mount | `deploy/home-compose.yml`: `${HOME}/tools/blender:/opt/blender:ro` and `BLENDER=/opt/blender/blender` for worker and dashboard | PASS (`docker exec studio-worker $BLENDER -b --version` = 5.2.3 LTS) |
| Depth pass aborted headless | "Couldn't open libEGL.so.1", core dump (EEVEE needs OpenGL/EGL) | depth pass on Cycles (4 samples, no bounces, no denoiser): exact and needs no GPU | PASS |
| Temple scene showed a modern villa | contact sheet: the `venice_sunset` sky has buildings | pure-sky HDRI, stone (not brick) columns | PASS (looked at) |
| Globe camera upside down, label mirrored on the planet | contact sheet | camera up axis Y; label and marker not seen by glossy, diffuse or shadow rays | PASS (looked at: Africa, Arabia, India the right way up; Hampi marker in south-central India) |

## 3. Measured speed (worker container, 3 CPUs, Cycles CPU)
- Still + depth at 1920x1080, 32 samples: temple 60 s, dunes 65 s, stones 55 s; sea, night, temple again: 2 min 40 s for three.
- Globe clip: 35 to 65 s a frame at 1920x1080 with an air sphere (too slow); 4 to 5 s a frame at 960x540, 4 samples, air glow inside the planet's material, persistent data. Clips are drawn at 12 fps and half size, blended to 24 fps (ffmpeg `framerate`; `minterpolate` dropped the last frames) and scaled to the video size. About 10 to 14 minutes for one 12-second globe.

## 4. How it is used in production now (blenderscenes.py)
- GLOBE: coordinates only from a Wikipedia article's own primary coordinates (no coordinates, no globe; never a guess). When the film's main source is itself a place, the globe goes on the first line that names it (never the hook lines), else on the second chapter's first line. Otherwise the candidates are the film's sources and named places (anchors) whose article has coordinates, and a globe goes ONLY on a line that names that place, labelled with it. Found live on "Seven Sleepers": its second source, "Cave of the Seven Sleepers", is pinned near Amman, Jordan (31.90 N, 35.97 E), while the legend is told at Ephesus; the first rule would have put a Jordan pin on an Ephesus line. NASA Blue Marble 8192x4096 (public domain, Commons file page and SHA-1 in assets/cc0/LEDGER.md and assets/cc0/earth/SOURCE.json).
- STILLS with exact depth (then free camera motion through parallax.py): dunes, stone circle, Greco-Roman colonnade, open sea, only on a line whose own words name that place (fixed whole-word list), never a line whose picture is a person, never next to another Blender scene, one per chapter, at most 6 a film and 1 a Short. The night template is not used automatically (its CC0 sky holds a light that may be modern).
- A line Blender drew is not drawn again on the free picture account.
- Resumable: clip frames go to their own folder; a stopped render continues (Blender's no-overwrite + placeholders; an empty placeholder frame is removed and redrawn); a clip is checked for its length before use; stills are cached by spec hash.
- A failure is recorded in the video's record (`blender.failed`) and the line keeps its usual picture: Blender never stops a video. `blender: false` in a record switches it off.
- Credits: "3D globe rendered in Blender by the studio; Earth picture: NASA Blue Marble (NASA Earth Observatory), public domain" (NASA wording, so it goes into the description) and "3D scene rendered in Blender by the studio (drawn by code (original work)); skies and textures: Poly Haven, CC0".

## 5. Tests
- tests/test_blenderscenes.py: 11 (matching, placement, failure handling, resumable frames, length check, a real headless Blender still + depth + globe clip, the behaviour case and 3 mutation checks). tests/test_ccrender.py real render test now uses the real path explicitly.
- agenteval: `case_blender_scenes_are_true_to_the_line_and_never_stop_a_video` (fails when Blender is put on a person's line, on the hook, or when a failed scene blanks its line).

## 6. Limits
- Blender's templates are simple. They are used only where the line names that place; the globe is the strongest, most informative use.
- CPU only today: a globe of 12 s costs about 10 to 14 minutes of render time.
- The Short "Tenali Rama" got no Blender scene: its source article has no coordinates and no line names a place a template can show truthfully. That is the rule working, not a failure.

## 21 Nov 2026: Blender in a finished production film
- The Seven Sleepers film carries a real Blender scene: a Cycles (CPU, headless) globe turning to **Ephesus** (37.9411 N, 27.3419 E, from the article's coordinates), clip `cache/cc/clip-globe-a7f1fa0707ef015b.mp4`, 10.9 s, 262 frames, on line 5 (60.2 to 73.3 s of the film). Looked at: frames at 62 s (Europe and Africa) and 67 s (the "Ephesus" label over Anatolia), captions over them.
- On the resumes the globe came from its cache (record field `seconds: 0.1` is the time spent, not the clip length).
- Shorts: none planned for either Short, correctly (no coordinates, no line naming a place a template can show).
- A side effect found: the globe clip is `yuv420p`, tv range, bt709, sRGB transfer, while the still scenes are full-range `yuvj420p`; ffmpeg rebuilt its filters at that scene and the new final parts lost frames. Fixed in `render.py` (PERMANENT_FAILURE_FIXES.md row 5).
