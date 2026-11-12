# Making a video with Claude Code instead of Autopilot (plan, 1 Nov 2026)

Status: PLAN ONLY. Nothing was installed, downloaded or rendered. Every install below waits for the owner's yes (CLAUDE.md, "When something is missing").

## 1. The aim
The owner wants the next video built in a Claude Code session: realistic 3D look, motion graphics, pictures made by code, free tools only, no OpenRouter spend (credit was $4.44 on 31 Oct; a documentary costs about $3.5 to $4 on the Autopilot "photo" look).

## 2. Where Autopilot spends money, and what replaces it
| Autopilot step (OpenRouter) | Cost seen in CLAUDE.md | In a Claude Code session |
|---|---|---|
| Script writing + fact-check rewrite | about $0.25 + reviews | I write it from fetched sources; `youtube-scriptwriter`, `youtube-fact-check`, `check_script.py` |
| AI review, claim ledger, web check | about $0.2 | I read the sources and fill `claims.json` with passages; the free rule checks run unchanged |
| Pictures (AI storybook / photo scenes) | $0.54 to about $2 | **Blender renders written as code** (section 3) |
| Clips (video models) | up to $1.5 | none; camera moves are rendered or 2.5D parallax |
| Voice | free (edge-tts) | unchanged |
| Render, captions, loudness, pop-up, corner mark | free (ffmpeg) | unchanged |
Precedent: `numbershort.py` and `filmshort.py` already build a whole Short with no model call (spec file in, held draft out; `grep llm` finds nothing in them).
Not free: the Claude Code session itself uses the owner's Claude plan allowance. A 9 minute film with 58 scenes is a long session; the plan's limits were not measured.

## 3. Picture stack (ranked; licences from the GitHub API / vendor pages read 31 Oct and 1 Nov 2026)
1. **Blender 5.2 headless** (`blender -b -P scene.py`), scenes written by me as Python. Blender is GPL; our output is ours. Standalone tarball `blender-5.2.3-linux-x64.tar.xz` (367 MB, blender.org) needs no sudo; Fedora also has `blender` 5.2.2 (95 MB, needs sudo). `bpy` from PyPI needs Python 3.13 and this PC runs 3.14, so use Blender's own Python.
   - Not using the Blender MCP (ahujasid/mcp-for-blender, MIT, 32.9 k stars): it runs model-written Python over a socket in an open Blender; a script file is reproducible, resumable (CLAUDE.md C) and needs no running server.
   - Realism comes from physically based materials, a real sky/HDRI and depth of field, not from the tool alone.
2. **CC0 assets, downloaded as files**: Poly Haven HDRIs, textures and models (assets are CC0). Do NOT build on the live Poly Haven API: its own pages disagree and the API page asks commercial users for a licence. Also candidates, licence to be read before use: ambientCG, Quaternius, Kenney. Every file goes in a ledger (`assets/cc0/LEDGER.md`: name, URL, licence, date) before `studiochecks licenses` sees it.
3. **Real depth for the free camera motion**: Blender can write an exact Z pass; `parallax.py` can use it instead of the estimated depth map.
4. **Studio3D (three.js + Remotion)** exists (`studio3d/`: March, Caravan, Storm, SubscribePop) and keeps its job. Do not use Remotion in anything automatic: its licence charges automated pipelines (research file of 31 Oct). Fine by hand for the owner.
5. **Motion graphics**: the studio's own `motiongraphics.py` (cards, date badges, hook text) and Pillow cards. `motion-reel` / `anidoodle` skills exist in the account; use only when asked, they are advice.
6. **AI photo by code, free, on a GTX 1050 Ti 4 GB (optional test)**: stable-diffusion.cpp (MIT) + Z-Image-Turbo GGUF (code Apache-2.0). Its docs say it runs on "4GB of VRAM, or even less" with `--offload-to-cpu`; quality, minutes per picture and the licence of the weights are UNVERIFIED. This PC has 23 GB RAM. Run as a measured test, not a promise.
7. **People**: no free path to realistic faces. Use silhouettes, figures from afar, hands, objects, places and maps. Candidates for stylised figures (CC0 packs) need a licence read first. A realistic synthetic person must also be labelled (`containsSyntheticMedia`).

## 4. Per-video workflow (all in the session, one held draft at the end)
| Step | Skill / tool |
|---|---|
| 0 Topic + state | `studio-video-finish` section 0, `duplicates.py` (one story, one video per format) |
| 1 Sources (2+, passages, dates) | `youtube-research`, `webcheck` only if credit allows |
| 2 Script (hook, curiosity, story, value; 8 to 10 min) | `youtube-scriptwriter`, `yt-hook-scripter`, `check_script.py` |
| 3 Fact check, claim ledger | `youtube-fact-check` |
| 4 Scene list: one Blender function per picture, camera move, light | new `scenes/` module (to build) |
| 5 Render stills/clips, depth pass | `blender -b -P`, cached by scene hash |
| 6 Voice, captions, 2.5D motion, graphics, pop-up, mark, loudness | studio code, unchanged |
| 7 Packaging | `studio-packaging`, `yt-title-optimizer`, `yt-thumbnail-brief`, `thumbstyle.py` |
| 8 Checks | `youtube-quality-gate`, `youtube-video-editor` (`check_video.py`), `studio-qa-video`, `youtube-copyright-check`; I look at frames and say how many |
| 9 Stop | `hold: true`; approval, scheduling and upload are the owner's |

## 5. Setup steps (each waits for a yes)
A. Install Blender (tarball to `~/tools/blender`, no sudo) and write `tools/cc_preflight.py` (a read-only check of Blender, ffmpeg, Chrome, Node, edge-tts, disk, credit).
B. Speed test on this PC: one 1920x1080 still and 120 frames of camera move, Cycles CPU vs Cycles CUDA vs EEVEE. Whether Blender 5.2 still runs Cycles CUDA on a GTX 1050 Ti is UNVERIFIED. The result sets how many scenes a film can have.
C. Download a small CC0 set (3 HDRIs, 6 textures) into `assets/cc0/` with the ledger.
D. (Optional) stable-diffusion.cpp + Z-Image-Turbo test, one picture, timed.
E. Build `scenes/` and a `ccbuild.py` that takes a spec (like `numbershort`) and builds the held draft with no model call. Tests, an `agenteval` case and a mutation check, as CLAUDE.md requires.
F. Pilot: one 30 s Short first, then one film.

## 6. Open points for the owner
- The server: the PC does the rendering (the VPS has no GPU that I know of: UNVERIFIED). How a hand-made draft gets to the server's upload queue still has to be confirmed; `numbershort` drafts were never uploaded.
- Look: one consistent "photo" look per story is allowed; the same scene template on every video invites YouTube's inauthentic-content rule, so scenes must differ by story.
- Subject for the pilot.

## 7. Measured on this PC (1 Nov 2026)
Installed with the owner's "all free" yes: Blender 5.2.3 (`~/tools/blender`, SHA-256 matched blender.org's file), stable-diffusion.cpp master-0a06712 Vulkan build and Z-Image-Turbo Q3_K + Qwen3-4B Q4_K_M + FLUX VAE from the Comfy-Org copy (`~/tools/sdcpp`; Hugging Face cards list Apache-2.0 for the Z-Image GGUF, the Qwen3 GGUF and the Tongyi-MAI Z-Image-Turbo repo; the FLUX.1-schnell card also says Apache-2.0).
| Test (GTX 1050 Ti 4 GB, 6-core i5) | Result |
|---|---|
| Blender Cycles 1280x720, 64 samples, CPU | 25.5 s |
| Blender Cycles 1280x720, 64 samples, CUDA | 10.8 s |
| Blender Cycles 1920x1080, 128 samples, CUDA | 37.8 s |
| Blender EEVEE 1280x720, 64 samples | 15.5 s |
| Dunes scene (`scenes/`, Cycles CUDA 1280x720, 48 samples + depth pass) | about 16 s in all |
| Z-Image-Turbo, 448x768, 8 steps, `--offload-to-cpu --diffusion-fa` | 312 s (303 s sampling, 4.7 s VAE) |
Looked at: the dunes frame (believable sand, sky and shadow; composition not yet good) and the Z-Image frame (reads as a real photograph of dunes and a stone ruin; I did not check it for flaws such as text, hands or odd shapes beyond a first look).
Consequences: Z-Image gives the most photographic pictures but costs about 5 minutes each at 448x768 (larger sizes will take much longer, not measured), so a 58-scene film is an overnight job and a Short of 8 scenes is about 40 minutes. Blender is about 20 times faster and gives exact depth and exact camera moves, but looks less photographic. Plan: Z-Image for hero scenes and thumbnails, Blender for repeatable shots, tables, maps and camera moves. UNVERIFIED: how it behaves at 1080 wide, and whether it draws people acceptably (the studio's rule is no realistic people).
Blender hazards found: the world volume fog blacks out Cycles frames (haze is done afterwards from the depth picture); a camera must be placed from the terrain height (`kit.ground_z`).
