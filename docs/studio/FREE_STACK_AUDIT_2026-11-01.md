# Free "everything by code" stack: audit of the owner's pasted list (1 Nov 2026)

Status: RESEARCH ONLY. Nothing was installed, downloaded or changed. Every install waits for the owner's yes (CLAUDE.md, "When something is missing"; third-party skills only through `python extend.py add`).
Method: GitHub API (`gh api`) for licence, stars and last push; the repos' own READMEs; Remotion's LICENSE.md, pricing page and FAQ; the Hugging Face model card for FLUX.1 schnell; web searches (results are secondary and are marked so); signed-out YouTube searches in a Playwright window (titles and view counts only, no video watched). The PC: GTX 1050 Ti 4 GB, 6 cores, 23 GB RAM; Blender 5.2.3 and stable-diffusion.cpp + Z-Image-Turbo already measured (docs/superpowers/plans/2026-11-01-claude-code-video-workflow.md, section 7).

## 1. Verdict per item (what the owner pasted)
| Item | Facts read | Fits this PC (4 GB) | Verdict |
|---|---|---|---|
| Hostinger Agent Skills | MIT, 28 stars, pushed 30 Oct 2026; folders billing, dns, domains, ecommerce, horizons, hosting, reach, vps (README says 6 domains) | n/a | Relevant: the VPS address belongs to Hostinger (section 6). Installing through `/plugin marketplace add` skips the pinned-hash intake; use `extend.py add`. Billing/ordering skills exist: ask first. |
| Hostinger MCP (`mcp.hostinger.com`) | MIT, 167 stars; OAuth to the whole Hostinger account (billing, orders, DNS, VPS) | n/a | Useful for VPS status and DNS now that the provider is confirmed. It can reach billing and orders: the owner's yes for each use; read-only first. |
| anthropics/skills | 185,829 stars; GitHub shows no licence; README: many Apache-2.0, docx/pdf/pptx/xlsx are source-available | n/a | Nothing new: the account already lists `anthropic-skills:*` and `skill-creator`. Skip. |
| ComfyUI | GPL-3.0, 144 k stars, pushed 31 Oct 2026 | runs, slowly; same models as sd.cpp | Optional. No gain over the measured sd.cpp path on 4 GB; GPL is fine for use, not for copying code into the studio. |
| Comfy MCP (artokun) | MIT, 881 stars, created Feb 2026; 38 tools, 42 skills, 3 hooks, started by `npx -y comfyui-mcp@latest` | needs ComfyUI | Not now. `@latest` runs unpinned npm code on every start (against "never auto-updated"); hooks are never copied by `extend.py`. A 100-line client for ComfyUI's HTTP API, pinned and tested, is safer (my recommendation). |
| FLUX.1 schnell | Hugging Face card: Apache-2.0, commercial use allowed, 12 B, 1 to 4 steps | UNVERIFIED: a search found no 4 GB benchmark; guides give 6 GB as a floor for Q2/Q3 GGUF | Licence is fine. Not a clear gain over Z-Image-Turbo (measured 312 s a picture). Test one picture before promising anything. |
| Wan 2.2 | Apache-2.0, 18 k stars. README: TI2V-5B "at least 24GB VRAM", A14B "at least 80GB" | NO | Not free on this PC. Needs a rented or bought GPU. |
| LTX-Video / LTX-2 | LTX-Video Apache-2.0 (last push Jan 2026); LTX-2 has its own "LTX Community License" (header read, terms NOT read); wiki says 32 GB+ for LTX-2 | NO (forum claims of 6 to 8 GB are for quantised LTX-2.3 with large RAM, unproven) | Not for this PC. Read the licence before any use. |
| Remotion | LICENSE.md: free for an individual, up to 3 employees, commercial allowed. FAQ: the Automators plan ($0.01 a render, $100 a month minimum) "only applies to the Company License"; an individual may automate. LICENSE.md says terms change in 5.0 | yes (Node + Chrome) | Allowed for the owner as an individual. This corrects the 31 Oct note that said it charges automated pipelines. Re-check at 5.0 and before offering it to user studios. The FAQ answer came through a page summary: confirm the exact wording once. |
| FFmpeg | already used (8.1.3) | yes | Have it. |
| Whisper.cpp | MIT, 54.8 k stars, pushed 30 Oct 2026 | yes (CPU) | Worth adding: a free, offline listen check to replace the paid audio model in `voicecheck.py` (about a cent a film). Captions already come from the voice's word timings (`subtitles.py`), so it is not needed for captions. |
| Unreal Engine 5 + MetaHuman | MetaHuman is covered by the Unreal licence (free under $1 M revenue per a secondary report; confirm on metahuman.com/license) | Epic's minimum GPU NOT read; a 4 GB Pascal card is, in my judgement, not workable | Skip. Blender Python (installed, scripted, reproducible) does the same job. Photoreal humans also clash with the studio's no-realistic-people rule and the synthetic-media label. |
| Blender automation | `ccrender.py` + `scenes/` already do this; blender-mcp (MIT, 32.9 k stars) rejected on 1 Nov for a good reason (live socket, not reproducible) | yes | Done. |
| Next.js + FastAPI + PostgreSQL + Redis/Celery | n/a | n/a | Not needed. The studio is Python + files + two containers, resumable by design (CLAUDE.md C). Four more services would add failure points and no capability. |
| "Claude API (paid usage)" | the list itself says paid | n/a | Contradicts "free". |
| "YouTube Agent Skill" (priority 1) | no repo or name given | n/a | Not identified. The project already has about 14 `yt-*` and `youtube-*` skills. Send the link. |

## 2. What a movie-quiz channel looks like (signed-out YouTube, 1 Nov 2026; titles and view counts of the first page only; not cross-checked, not a sample of the whole niche). Football was removed from scope on 1 Nov at the owner's order.
- "guess the movie quiz shorts": 17 results; most carry "New" and 2 to 1.2 K views; a few outliers at 1.9 M, 6.2 M and 8.8 M.
- Reading: demand exists, but the first page is full of near-identical templates. YouTube judges the whole channel for mass-produced or repetitive content (see section 7 for the rule text). A quiz format is a template by nature, so variation has to be designed in. Film stills are a copyright problem; emoji and own-drawn clues avoid them.
- Business point: this is a different audience from The Sleeping Library (history and legend, 10 subscribers). The open decision from 31 Oct stands: a new studio (user studios have their own niche) or this channel.

## 3. What actually gets "realistic image to 3D motion" for free on this PC
1. Still: Blender scene render (about 16 s, exact depth) or Z-Image-Turbo (about 5 min, most photographic).
2. Motion: `parallax.py` with the Depth Anything V2 Small model already on this PC (`data/models/`), or Blender's exact Z pass.
3. Not researched: image-to-mesh models (for a true 3D object from one picture). Say the word and I will research licence and VRAM first.
4. Honest limit: free + fully automatic + Claude-quality writing cannot all hold at once. Free models write worse scripts than Claude; the reviewers are Claude and cost credit.

## 4. Custom skills proposed (none written yet)
Existing coverage is wide (about 29 project skills), so new ones should fill gaps, not repeat. The four skills in the owner's list are mapped first.
| Proposed skill | Why | Overlap |
|---|---|---|
| `studio-cc-video-build` | The free build recipe exists only as a memory note; as a skill it loads when needed | none (memory note only) |
| `studio-blender-scenes` | Scene-writing rules: PBR, sky, depth of field, the fog and ground-height hazards, cache by hash, no people | none |
| `studio-local-image-gen` | Z-Image job runner, prompt rules (no people, no text), time budget, background runs; ComfyUI/FLUX only after a measured test | none |
| `studio-tool-vetting` | The check done in this audit: SPDX via `gh api`, weights licence read separately, hardware floor, employee or revenue limits, ledger line | `vetskill.py` scans skills, not models |
| `studio-completion-report` | Makes the six-point report (CLAUDE.md F) automatic and forces quoted test output | none |
| `studio-quiz-formats` (only if the owner opts in) | One skill for movie quizzes with a variation matrix and own-drawn clues, no film stills | replaces `movie-quiz-studio` |
| `story-video-studio` | Scripts, narration, storyboards | already `youtube-scriptwriter`, `yt-hook-scripter`, `studio-video-finish`: do not duplicate |
| `png-animation-studio` | Characters and scene continuity | needs GPU consistency tools; a Blender/Pillow cut-out version is possible |

## 5. Sources (read 1 Nov 2026)
GitHub API repo records for hostinger/hostinger-agent-skills, hostinger/api-mcp-server, anthropics/skills, Comfy-Org/ComfyUI, Wan-Video/Wan2.2 (README lines on VRAM and licence), Lightricks/LTX-Video, Lightricks/LTX-2, remotion-dev/remotion (LICENSE.md), ggml-org/whisper.cpp, ahujasid/blender-mcp, artokun/comfyui-mcp (README), city96/ComfyUI-GGUF. https://www.remotion.pro/license and https://www.remotion.dev/docs/license/faq (page summaries). https://huggingface.co/black-forest-labs/FLUX.1-schnell (card summary). Web-search snippets (secondary, not verified at source): low-VRAM FLUX and LTX guides, MetaHuman licence coverage, July 2025 YouTube policy coverage. Playwright result lists from youtube.com search pages.

## 6. Verification pass (1 Nov 2026, second round)
| Open point | Result | Status |
|---|---|---|
| VPS provider | `tailscale status` shows vps-ai direct at 187.127.107.64; `whois` on that address: netname HOSTINGER-HOSTING, "Hostinger MY". It is Hostinger's address block; the account/plan type is not known | VERIFIED (address owner) |
| Remotion FAQ wording | Read in the repo source `packages/docs/docs/license/faq.mdx`: free for "an individual, whether for personal or commercial use" (line 19); "Can I run an automation under the Free License? Yes. ... 'Remotion for Automators' ... only applies to the Company License" (lines 66 to 69); "you don't need to buy a license - even if you set up an automation, launch a SaaS, or are using it commercially" (line 77). Line 129 says organizations building automated pipelines fall under Automators, so the owner must stay an individual or a team of 3 or fewer | VERIFIED |
| LTX-2.x licence (Aug 2026 text) | Section 2.1: free for any purpose for entities under $10,000,000 annual revenue, "subject to the restrictions set forth in Attachment A" (Attachment A not read); entities at or above that need a paid licence. Hardware is still the blocker (32 GB+ per the repo wiki) | PARTIALLY_VERIFIED (Attachment A unread) |
| UE5 minimum GPU | Epic's Windows page lists no minimum GPU; it recommends 8 GB or more of graphics RAM and a DirectX 12 card; Lumen, MegaLights need RTX 2000 / RX 6000 or newer; the 1050 Ti is not mentioned. The Linux requirements page was not read. "Not workable" stays my judgement | PARTIALLY_VERIFIED |
| MetaHuman licence terms | The licence page redirects to an Epic login and the EULA page returned 403; I did not sign in. Terms stay unread | UNVERIFIED |
| FLUX schnell on 4 GB | stable-diffusion.cpp docs: Flux "with a GPU that has 6GB or even 4GB of VRAM"; memory table is for Flux-dev (q3_k 4,888 MB, q2_k 3,736 MB); schnell example uses `--steps 4`; no timing anywhere. A real timing needs a download of several GB (schnell GGUF, two text encoders, VAE) and the owner's yes | UNVERIFIED (timing) |
| Image-to-3D mesh models | TripoSR: MIT, README "about 6GB VRAM" default. Stable Fast 3D: licence shown as NOASSERTION (not read), 6 GB. Hunyuan3D-2: 6 GB shape, 16 GB with texture, licence NOASSERTION (not read). TRELLIS: MIT, "at least 16GB". None fits 4 GB by the documented figures; TripoSR on CPU was not tested | VERIFIED (figures); fit on this PC UNVERIFIED |
| YouTube inauthentic-content rule, primary page | support.google.com/youtube/answer/1311392: renamed from "repetitious content" to "inauthentic content" (15 Jul 2025); policy body under "Generic or Repetitive Content": "content that looks like it's made with a template", "Image slideshows, templated storylines, or scrolling text with minimal or no narrative, commentary, or educational value", "minimal variation across videos"; reviewers look at the channel as a whole (main theme, most viewed videos). Whether enforcement is per video is not stated on the page | VERIFIED (page summary read through a fetch tool) |
| Any claim that a format, effect or sound raises views | No study exists in the sources read; cannot be verified | UNVERIFIED by nature |

## 6b. Work done after "go ahead" (1 Nov 2026)
- Demo Short built with `numbershort.py` (docs/studio/ronaldo/short.json; 36.4 s, 103 words). Gate result after the fixes below: PASS, 0 blocking, with warnings (pace 180 words a minute, subtitles flag, "grounded" is a Wikipedia-only notion).
- Code changes, each written test-first (red then green): (1) `studiochecks.ALLOWED_LICENSES` accepts the credit "drawn by code (original work)"; (2) `numbershort.passage_in_page` and `mark_checked`: a source may name its saved page (`file`) and its passage must be found in it, else the spec is refused; (3) `reviewer.source_text` and `ledger.build` count a listed source only when `passage_checked` is true, and the claim row names that source (not Wikipedia); (4) `numbershort.build` writes `claims.json`; (5) `numbershort.MAX_WORDS` 80 to 130 so a number Short can meet the review's 100-word minimum without weakening it. New `agenteval` case plus a mutation check. Full suite: 2238 passed, 4 failed (the same 4 depth-model tests that failed before the change, caused by the depth model now being installed on this PC), 14 browser tests deselected.
- FLUX.1 schnell timing test: files downloading to `~/tools/sdcpp/flux/` (clip_l, T5 Q4_K_M, schnell Q2_K, about 7.2 GB, SHA-256 checked against the Hub's listing; city96's GGUF card says Apache-2.0). Result not yet measured.

## 6c. Verified after the owner opened an Epic account (1 Nov 2026)
The MetaHuman licence page (https://www.metahuman.com/license) loaded in a signed-out browser, so no login was used; its FAQ answers were read by opening each question.
- "MetaHuman is included as part of your standard Unreal Engine license, meaning it's free to use for anyone making under $1 million USD in revenue", and "From Unreal Engine 5.6, your use of MetaHuman is included under the terms of your existing Unreal Engine license."
- Use outside Unreal Engine: yes, "across all engines and creative software, subject to applicable terms"; no royalties (Non-Engine Products); a seat licence only above $1 million annual gross revenue when rendering outside Unreal Engine.
- AI: allowed "in workflows that incorporate artificial intelligence technology", but "you may not use MetaHuman characters or animation curves to build or enhance any database or train or test artificial intelligence, machine learning, deep learning, neural networks". This includes rendered output from MetaHuman characters. So MetaHuman renders must not become training data (the studio's `trainset.py` must never include them).
- Status: VERIFIED for the terms above. The Unreal Engine EULA itself (403 to a fetch tool) was not read; the FAQ says its terms govern. Hardware stays the blocker (Epic recommends 8 GB+; 1050 Ti 4 GB).
- LTX-2.x Attachment A (use restrictions) read: complies with Lightricks' Acceptable Use Policy (a PDF, not read); bans among others deepfakes of real people without consent and undisclosed machine-generated content. Free under $10M revenue. Status: VERIFIED for Attachment A; the Acceptable Use Policy PDF is unread.

## 6d. Ronaldo documentary script (1 Nov 2026)
`docs/studio/ronaldo/doc.json`: "Ronaldo's Six World Cups: Twenty Years of Goals", 80 lines, 1,085 words (about 8 minutes with the documentary's 0.6 s pauses), 11 chapters, 26 source passages, every line mapped to the passages that carry it (`src`). Sources saved verbatim in `docs/studio/ronaldo/src/` (Wikipedia revision of 30 Oct 2026, AP via FOX 9, Al Jazeera/AFP, ESPN, Guinness World Records, Sky Sports).
Checks that ran: all 26 passages found in their saved pages (`numbershort.mark_checked`); claim ledger 28 of 28 claims VERIFIED (`ledger.build`); script-review rules (`scriptreview.rows`) with no failing row; a separate script compared every spelled number with its mapped passage and the leftovers were ordinals, "first/one", derived sums (2006 to 2026 is twenty years; 2026 minus 4) and the "2007-08" season.
Currency catches: (1) the 2026 World Cup is over, so the angle is six World Cups, not five; the 2022 Short ("first man at five") is now out of date and should be remade; (2) Guinness now lists Lionel Messi (38 y 357 d, 16 June 2026) as the oldest World Cup hat-trick scorer, so the script says Ronaldo was "at the time" the oldest; (3) sources disagree on Ronaldo's World Cup goal tally (10 against 9), so the script gives no total. Left out on purpose: the post-World-Cup dispute and suspension (one secondary source, a living person).
Not done: no voice, pictures or render yet. No documentary builder exists for the free path (`ccbuild.py` makes 9:16 Shorts only); it has to be written and tested. Pictures wait for the FLUX timing, so GPU time is not spent twice.

## 6e. FLUX Schnell measured on this PC (1 Nov 2026)
Files: flux1-schnell-Q2_K.gguf (4.0 GB), T5-XXL Q4_K_M (2.9 GB), clip_l; all three SHA-256 values match the Hugging Face listing. Same scene (s01, 768x448, seed 101, same prompt, same low-memory flags, 4 GB GTX 1050 Ti):
| Model | Time | What the picture shows (one sample, my reading) |
|---|---|---|
| FLUX.1 schnell Q2_K, 4 steps | 212 s | good night mood and lights; small distortions (goals in the middle of the background, a rig at the left); soft |
| Z-Image-Turbo Q3_K, 8 steps | 340 s | more coherent stadium (mown stripes, light towers, stands), more photographic |
One sample proves nothing about the average. For 28 pictures: FLUX about 1.7 hours, Z-Image about 2.7 hours. Pictures: docs/studio/ronaldo/pictures.json (28 landscape jobs, no people, no text). Plan scan: every line has a defined picture, two unused jobs removed, prompts contain no people words (matches were "corner flag pole" and "no players"), `ccdoc.py --check` says spec ok. Z-Image needs `PYTHONPATH=.` when started from the repo root (`PYTHONPATH=. .venv/bin/python tools/zimage_batch.py <jobs.json>`).

## 6f. Pollinations.ai tested (1 Nov 2026, owner asked to add it for realistic pictures)
Read: github.com/pollinations/pollinations (MIT, 5,260 stars, pushed 1 Nov 2026): README and APIDOCS now describe a unified API at gen.pollinations.ai with API keys from enter.pollinations.ai and "Pollen" credits (pay as you go, about $1 for 1 Pollen). The terms page (pollinations.ai/terms) did not render for a fetch tool, so ownership and commercial-use terms are UNVERIFIED.
Tested with one harmless scene prompt (empty stadium at night), no key:
| Endpoint | Result |
|---|---|
| gen.pollinations.ai/image/... (model flux.1-schnell) | 401 "A valid API key is required" |
| image.pollinations.ai/prompt/... (legacy) | 200, 1024x576 JPEG in 7 s; the file's own metadata says model "sana" whatever model was asked (flux asked, sana returned); width 1280 and 1920 were not given; `nologo=true` was ignored: the picture carries a "pollinations.ai" logo bottom right |
| the same with model turbo, gptimage or size 1920x1080 | 402 payment required |
Looked at the picture: dark, flat, soft; weaker than the local FLUX and Z-Image pictures of the same scene.
Conclusion: the free no-sign-up route is a watermarked 1024x576 Sana picture; better models need a key (sign-up, credits). A third-party logo in a published video is not acceptable (provenance and "reused content" rules), and prompts sent to the service are not private (identical requests may be answered from a shared cache). Nothing was added to the studio. If the owner signs up and keeps the key in the server environment (never in chat or git), a keyed provider can be added test-first after the terms are read in a browser.

## 6g. Pollinations with the owner's key (1 Nov 2026)
The owner saved an `sk_` key in `.env` (three lines were appended; two differ in value; the first is the one loaded and it works). Account endpoint 200; `account/balance` is forbidden for this key (no `account:usage` permission), so the Pollen balance is unknown. `GET /v1/models` (no key needed) lists 77 image-capable models with prices in Pollen per image: tongyi-mai/z-image-turbo 0.004, recraft-v4.1-flash 0.007, seedream-5.0-flash 0.019, black-forest-labs/flux.1.1-pro 0.03, qwen-image-2.1-pro 0.04, flux-3-image 0.05 (the docs say about $1 for 1 Pollen: not verified against a bill).
Two test pictures (same scene as before, 1280x704, seed 7), no logo, no people, no text, both read `x-usage-completion-image-tokens: 1`: z-image-turbo 15 s (documentary look, flat but credible), flux.1.1-pro 11 s (polished, dramatic, a little stock-photo). Both sharper than the local 768x448 pictures and 20 to 30 times faster. A size must be a multiple of 32 for FLUX 1.1 Pro (a 1280x720 request got 400). Cost of the two tests: about 0.034 Pollen.
Estimate for the 54 film pictures: z-image-turbo about 0.22 Pollen, flux.1.1-pro about 1.6 Pollen (price list times count; no bill seen). Commercial-use terms still UNVERIFIED (terms page unreadable to a fetch tool). Nothing in the studio uses the key yet.

## 6h. "Free realistic images": the owner's pasted chat checked against the providers (1 Nov 2026)
| Claim in the paste | What I found | Verdict |
|---|---|---|
| Pollinations: 100% free, no registration | Keyless legacy route: 1024x576 "sana" picture with a pollinations.ai logo, other models 402. Keyed route (owner's key): clean 1280x704 pictures, but the starter credit was only about 0.25 Pollen and ran out after 7 FLUX 1.1 Pro pictures (402 "Insufficient balance", 0.006 left). | FALSE as stated: free only for a watermarked small picture or a small starter credit |
| Hugging Face API: free, unlimited | Inference Providers pricing page: "Free Users: Monthly Credits None"; credits must be purchased; PRO $9 gives $2 a month. Spaces/ZeroGPU have a quota; not tested. | FALSE for the API |
| HF "FLUX.1 Krea [dev]" for realistic photos | Model card licence: flux-1-dev-non-commercial-license. Not usable for a monetized channel. FLUX.1 schnell is Apache-2.0. | RISKY: non-commercial |
| Cloudflare Workers AI: 10,000 free credits a day | developers.cloudflare.com pricing page: 10,000 Neurons a day at no charge, reset 00:00 UTC; on the free Workers plan, usage past that "will fail with an error" (no bill). flux-1-schnell costs 4.80 Neurons per 512x512 tile + 9.60 per step: about 57.6 Neurons for a 1024x1024 picture of 4 steps, so roughly 170 pictures a day (my estimate; the model page does not document width/height or the output size). | TRUE (limits from the price list; output size and real count UNVERIFIED until a first picture is made) |
| OpenRouter has no free image models | OpenRouter /models: 12 models with image output, none with a zero price. | TRUE |
| "Paste this system prompt into Claude and it shows pollinations images" | Not how the studio works (pictures are files made by tools with a cap); the markdown link route is the keyless watermarked one. | NOT USED |
Built (test-first): `tools/cloudflare_batch.py` (token only in a header, daily Neuron counter in data/cloudflare_usage.json, cap 9,000, cached pictures free), `tools/pollinations_batch.py`, and `provider` job resolution in `ccbuild.py` and `ccdoc.py`. To switch it on the owner creates a free Cloudflare account and saves CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in `.env`.
Free and unlimited remains the local pair: FLUX.1 schnell (212 s a 768x448 picture) and Z-Image-Turbo (340 s) on the PC.

## 6i. The VPS as a render lane (1 Nov 2026, owner: "you can use my vps for render")
Read-only check of deploy@vps-ai (Hostinger, srv2029460): 4 cores, 16 GB (about 10.8 GB free), 57 GB free disk, load 0.15, NO GPU, about 25 containers (the live studio-worker is capped at 4 CPUs and 3 GB). The image `studio:local` has Python 3.13, ffmpeg 7.1.5, numpy 2.5, onnxruntime 1.31, Pillow 13, edge-tts and fonts; the depth model is in ~/studio/data/models. So the VPS can do the CPU parts (voice, depth maps, camera motion, ffmpeg render) but not the pictures, which stay on the PC GPU.
`tools/remote_build.py` (dry run by default, `--run` to execute; 7 tests): copies an allowlist of code (root *.py, tools, config, static, playbooks, branding) and the spec's folder to ~/render-jobs/<job>, the needed pictures to its cache/cc, runs the builder in a throwaway container (`--rm --cpus=2 --memory=4g`, `nice -n 10`, depth model mounted read-only), copies output/ back. Never .env, tokens, settings, data, output or git; never docker exec, restart or edits in the live containers; nothing is deleted. Smoke test passed (imports of ccbuild, ccdoc, thumbstyle, tts, render, parallax, depth; edge-tts voice sample 16,704 bytes in 2 s). A leftover folder ~/render-jobs/smoke1 (132 small files) is for the owner to clear. Not yet measured: how long a real film takes there against the PC (12 to 15 min on the PC).

## 7. Still open
FLUX schnell timing on this PC (files still downloading), the Epic EULA text and Lightricks' Acceptable Use Policy PDF, TripoSR on CPU, Hostinger plan type, whether a Hostinger MCP or skills install is wanted.
