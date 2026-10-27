---
name: ai-film-studio
description: Build and run a low-cost AI short-film and micro-drama engine (consistent original characters, scene-by-scene AI video, voice, music, edit, multi-platform publish) inside my existing Story Studio system, using direct pay-per-use API keys instead of Higgsfield or other subscription platforms. Use when I ask to plan, build, extend, fix or run AI movies, AI short dramas, AI series, characters, shots, API keys/providers, or the studio MCP server.
---

# AI Film Studio

You are the lead engineer and producer adding an **AI short-film / micro-drama engine** to my existing **Story Studio** system. The goal: make videos like viral AI short dramas (hooked story, consistent characters, cinematic shots, cliffhangers) for YouTube, Facebook, Instagram and TikTok, at a fraction of the cost of all-in-one platforms such as Higgsfield. We do that by calling the underlying models **directly with my own API keys, paying only per use**, and by spending money only on shots that need it.

This skill works together with `CLAUDE.md` (tools, cost, safety rules) and the `media-studio-expansion` skill (channels, assets, quality gates, SEO, publishing). Where they overlap, follow them; this file adds the film engine.

Work step by step. **Stop at every 🛑 checkpoint and wait for my answer.**

---

## Rule 0: Before every task

Do these four things, in this order, every time:

1. **Read the progress file** `docs/studio/PROGRESS.md` (create it if missing; see "Progress file"). It tells you where we are, so you don't re-explore what's already known.
2. **Load the skills and tools that fit the task, before doing the work.** Check what's actually installed (`claude mcp list`, the plugin list, the skills folders). Load a skill with the Skill tool before improvising. Never assume a skill or tool exists; if it's missing, say so and give the install command, and ask before installing.
3. **State the plan in 1–3 lines**: what you'll do, which skills and tools you'll use, and how you'll verify it.
4. **Check the budget** for the step (see "Cost rules"). If the step costs real money, show the estimate and wait for my OK.

## Rule 1: No hallucination

- Every claim about my system comes from code, config, logs or commands you ran this session. Cite the file or command.
- Prices, API limits, model names, model versions, licenses and platform rules change often. Look them up in the provider's own docs or pricing page **at the time you need them**, give the link and the date, and write "Not verified" if you couldn't confirm. The prices in this file are starting points from research on 25 Oct 2026, not facts to build on.
- Never invent a model, endpoint, parameter, SDK function, skill, plugin, MCP tool, view count or source. If unsure, check the docs or say you don't know.
- Never say "done" or "working" for something you didn't run and check. At the end of each step, list what you skipped, assumed or couldn't verify.

## Rule 2: No hard-coding

- **No API keys, tokens, account IDs, URLs, model names, prices, prompts, voice IDs, channel IDs, file paths or limits in code.** They go in:
  - secrets → environment variables (and `.env.example` with empty placeholders; real `.env` is git-ignored)
  - settings → config files (YAML/JSON) validated by a schema at startup, with clear errors if anything is missing
  - per-channel and per-series choices → the channel profile and the series bible files
  - prompts → versioned prompt template files, not strings in code
- **Providers behind adapters.** Each video, image, voice, music and text provider is a small adapter with the same interface. Which provider and model to use is a config choice, so switching costs one line of config, not a code change.
- Fail loudly on missing config. No silent defaults for anything that costs money or publishes.
- Add a check (test or lint) that fails the build if a secret pattern, a raw provider URL or a model name appears in code.

## Rule 3: Direct API keys, pay per use (main cost saver)

All-in-one platforms charge a markup and a monthly plan. We use **my own API keys straight with the model providers (or the cheapest reliable host of the same model)**, so we pay only for what we generate.

**When a step needs a provider:**
1. Check if its key is already set (by name only: check the variable exists and is non-empty; never print, log or echo the value).
2. If it's missing, tell me in 2–3 lines:
   - which provider and why it's the cheapest fit (with current price and source link)
   - the exact environment variable name to add (for example `VIDEO_PROVIDER_A_API_KEY`), and where to add it (`.env` locally, the server's secret store in production)
   - the link to the provider's official key page and billing page
   - which spending limit to set there
3. **Never ask me to paste a key into the chat.** I add it to `.env` or the secret store myself. If I paste one anyway, don't repeat it, tell me to rotate it, and continue with the variable name only.
4. Continue with mocks and other work while the key is missing; never block the whole build on one key.

**How to keep API costs low:**
- **Pay-as-you-go only.** Prefer providers with per-use billing and no monthly minimum. Only suggest a subscription or prepaid plan when real usage numbers in `COSTS.md` show it's cheaper, and show the math.
- **Cheapest host for the same model.** The same model is often sold by several hosts at very different prices (Seedance 2.5 720p ranged from about $0.67 to $2.36 per 5 s clip across hosts in Aug 2026). Compare hosts, put the cheapest reliable one first in `routing.yaml`, the next as fallback.
- **One key per provider per studio/channel** where the provider allows it, so cost per channel is visible and one leak doesn't expose everything.
- **Spending limits at the provider too:** set a monthly cap and usage alerts in each provider's billing dashboard, on top of our own caps in `budgets.yaml`. Two locks, not one.
- **Free tiers and credits first** for tests and the bake-off, where the terms allow commercial use; record them in `COSTS.md`.
- **Batch and discount APIs:** for non-urgent text work (scripts, titles, descriptions, reviews), use the provider's batch API when it offers a discount, and prompt caching for long repeated instructions (series bible, style guides). Verify the current discount on the provider's docs before relying on it.
- **Right model per job:** small, cheap text models for drafts, checks and metadata; stronger ones only for final scripts. Already in use: OpenRouter; check whether calling a provider directly is cheaper for the models we use most.
- **Track every call:** the adapter records provider, model, units, price and cost per call in `data/` and `COSTS.md`, so the cost guard and the daily report show spend per key, per channel, per episode.
- **Key hygiene:** keys only in env or the secret store; never in code, logs, error messages, the progress file, git or the MCP gateway's outputs. Least permission scope per key. A note in `docs/studio/film/keys.md` lists each key's **variable name**, provider, purpose, owner, spend cap and rotation date (never the value). Remind me to rotate keys every 90 days.

## Rule 4: Spend as few tokens as possible

- Read the progress file first; don't re-scan the codebase for things already recorded there.
- Search with `grep`/`glob` and read only the lines you need; don't open whole large files or re-read files you just wrote.
- Use subagents for broad searches and mechanical, verifiable work (they return a summary, not file dumps). Use cheaper models for subagents when the work is mechanical and easy to check; keep the main model for design decisions and final review.
- Batch independent tool calls in one turn. Don't narrate between tool calls.
- Keep replies short: decisions, results, next step. Details go in docs and the progress file, not the chat.
- Run `/compact` at natural breakpoints (end of a step), after the progress file is up to date.
- Don't paste long logs; summarize and point to the log file.

## Rule 5: Make sure everything works

Every step ends with proof, not promises:
- unit tests for logic, integration tests with provider calls mocked, plus **one real low-cost run** (smallest resolution and shortest clip) when the step touches a provider
- the output opened and checked: watch the video or read its contact sheet; listen to the audio; read the files
- cost of that run recorded
- a rollback note

If something fails, fix it and re-test. Don't skip or delete tests to pass. If you're stuck after two honest tries, stop and tell me what you tried.

---

## Progress file: `docs/studio/PROGRESS.md`

Create it on the first run. Update it **at the end of every step and before every 🛑 checkpoint**. Keep it short and append-only; newest entry at the top. Template:

```markdown
# Studio progress

## Status now
- Current phase / step:
- What works end to end:
- What's broken or blocked:
- API keys needed but missing: (variable names only)
- Next step:
- Money spent so far (this project): $

## Log
### YYYY-MM-DD HH:MM — <step name>
- Goal:
- Done: (files changed, features added)
- Skills used:
- Plugins / agents used:
- Connectors / MCP tools used:
- MCP tools built or changed:
- Providers / models called (with cost):
- API keys used (variable names only):
- Tests run and result:
- Real output checked: (what, how)
- Decisions made (and why):
- Not verified / assumptions:
- Next:
```

Also keep `docs/studio/DECISIONS.md` (one line per decision with date and reason) and `docs/studio/COSTS.md` (per-run costs by stage and provider), so the progress log stays short.

---

## What this is copying, and what we do differently

The reference video (Higgsfield's "5-Step Workflow: How to Make Viral AI Short Dramas", 22 Oct 2026) describes this workflow:
1. a story with an immediate hook
2. visually consistent characters (their SOUL 2.0 tool)
3. scenes generated shot by shot (Seedance 2.5), with failed takes fixed
4. edit with cliffhangers
5. monetize

We keep the workflow but not the platform. Instead:
- **Character consistency** comes from our own character bible plus reference images we generate once (character sheet: front, side, three-quarter, expressions, outfits) and reuse as image references in every shot.
- **Shots** go straight to the model APIs with my keys through our adapters, choosing per shot the cheapest model and host that pass the quality check.
- **Not every shot needs AI video.** Many shots can be a still image with camera motion, parallax, or Remotion effects, which cost almost nothing.

---

## Research starting point (verify before use)

Prices from public pages, checked 25 Oct 2026. They change often; re-check the provider's own pricing page before budgeting.

| Option | What it's good for | Price seen | Source |
|---|---|---|---|
| Seedance 2.5 via API hosts | Same model as the reference video; text- and image-to-video with audio | 720p, 5 s clip: about $0.67 (Atlas Cloud) up to about $2.36 (fal.ai) | [Apiframe comparison, 20 Aug 2026](https://apiframe.ai/models/seedance-2.5/pricing) (published by a competing host) |
| Kling API | Image-to-video, motion control, avatar/lip-sync | Standard 720p no audio about $0.084/s; Pro 1080p about $0.112/s; avatar 720p about $0.056/s | [Costbench, verified 18 Aug 2026](https://costbench.com/software/ai-media-apis/kling-api/) |
| Wan 2.6 (hosted) | Image-to-video | about $0.10/s at 720p | [RunPod guide](https://www.runpod.io/articles/guides/wan-2-7-runpod) |
| Wan 2.7 (Alibaba hosted only, no open weights) | Reference-to-video with up to 5 consistent characters and voices; 2–15 s clips | Not verified | same |
| Wan 2.2 self-hosted on a rented GPU | Lowest marginal cost if volume is high | RTX 4090 from about $0.34/hour; speed per clip not verified | same |
| Image models (for character sheets and keyframes) | Seedream, Flux Kontext, Nano Banana and similar | Not verified; usually cents per image | check each provider |

Rough episode math, for planning only: a 60–90 s episode of 15–20 shots, 5 s each, is 75–100 s of video. At about $0.08–0.13 per second that's about $6–13 per episode before retakes, so with 2× retakes budget $12–26. Mixing in cheap still-image shots can cut this a lot. Measure the real number on the first test episode.

**Your research task (Phase 1)** is to confirm or replace this table with current, sourced numbers and run a small bake-off.

---

## Phase 0: Current state and toolbox

1. Read `CLAUDE.md`, the progress file, the existing pipeline code (topics → script → fact check → voice → pictures → render → SEO → review → upload), the channel-profile plan, the MCP gateway, and the cost guard. Cite files.
2. List which API keys the system already uses (variable names only, from config and `.env.example`) and which providers they belong to.
3. Inventory installed skills, plugins, agents and connectors. Likely useful ones to check for (use only those really installed):
   - **Story and script:** scripting-and-storyboarding, storytelling-and-narrative, short-form-video-script, hook-writer, story-writer, viral-reverse-engineering, the novel-studio agents (plot/hook, characters, continuity)
   - **Video generation:** kling-ai, runway-api, together-video, video-generation skills, muapi, creative-claw (characters, film), ai-video-editor, video-shotcraft
   - **Images and characters:** image generation skills (flux, nano-banana, ideogram, together-images), creativeclaw-create-character
   - **Voice, music, SFX:** ai-voiceover, voice-builder, creativeclaw-clone-voice (my voice only), suno or ai-music skills, sound-effect skills, audiopod for cleanup
   - **Editing:** ffmpeg skills, Remotion engine (planned), captions-and-clipping, opus-clip / openclip, video-cleanup
   - **Publishing and growth:** youtube-publishing-and-metadata, youtube-shorts, tiktok-video-publishing, instagram-reels-publishing, facebook-strategy, thumbnail-design, hashtag-strategy, social-seo, one cross-poster at most (upload-post, ayrshare, post-bridge or bulkpublish)
   - **Engineering quality:** mcp-builder, backend-design skills, testing skills, dod-guard, code review agents
   - **Cost:** cloud-finops, token-usage, claude-code-cost
   - **Planning docs and diagrams:** Figma/FigJam, excalidraw, or Mermaid
   - Note: some plugins are themselves paid platforms with their own markup. Prefer a skill that calls the provider API with my key over a plugin that resells it, unless the numbers show the plugin is cheaper.
4. Write `docs/studio/film/00-current-state.md` and start `PROGRESS.md`.

🛑 **Checkpoint 0:** Show me the toolbox ("Will use / Missing but useful"), the API keys already in place (names only), and anything in my system that differs from what you expected.

---

## Phase 1: Research and bake-off

1. **Research** (use deep-research or tavily skills if installed; otherwise web search): for each candidate model, every host that sells it, with current price per second, free credits, rate limits, billing model (pay-as-you-go or plan), spending-limit support, and commercial-use terms. Record links and dates in `docs/studio/film/01-research.md`.
2. **Keys:** list the keys I need to create for the bake-off (variable names, links, suggested caps). Wait for me to add them.
3. **Bake-off**: one short test scene (same character sheet, same 3 shots: dialogue close-up, action, wide establishing) on 3–4 candidates at the lowest resolution. Score each on: character consistency, motion quality, prompt-following, lip-sync if needed, generation time, cost per second, failure rate, license for commercial use. Put the clips side by side in a contact sheet I can view.
4. Recommend a **default model and host per shot type** and a fallback, with the cost per episode.

🛑 **Checkpoint 1:** I approve the model and host choices and the budget per episode.

---

## Phase 2: Requirements

Ask me in small batches (3–5 questions, with options and a recommended default):
- genres, target audience and languages
- episode length, episodes per series, posting frequency, platforms
- 9:16 first or 16:9 first
- monthly budget, a hard cap per episode, and a monthly cap per API key
- voice: my cloned voice, TTS voices per character, or both
- approval: which steps I want to approve (default: series bible, first episode, every publish)
- monetization paths I want (ad revenue, platform creator funds, series/paywall, sponsorships)

Write `docs/studio/film/02-requirements.md` with numbered, testable requirements.

🛑 **Checkpoint 2:** Confirm.

---

## Phase 3: Design

Write `docs/studio/film/03-design.md` with diagrams. It must cover:

### 3.1 Pipeline (one episode)
1. **Idea and hook:** pick a premise using search demand and trend research; write a one-line hook and a cliffhanger.
2. **Series bible** (once per series): logline, world, tone, visual style, color palette, and each character's card (name, look, age, outfit, voice, personality, speech style) plus reference images. Stored as files; reused every episode.
3. **Script:** scenes, dialogue, beats, timing; hook in the first 3 seconds; cliffhanger at the end.
4. **Shot list:** each shot gets shot type, duration, camera move, characters, location, prompt from templates, and a **render method**: AI video, image + motion, or Remotion graphic. Cheapest method that serves the story wins.
5. **Keyframes first:** generate a still keyframe per shot (cheap). Review them as a storyboard contact sheet before any video money is spent.
6. **Shot generation:** image-to-video from the approved keyframes with character references. Auto-check each take (character match, artifacts, prompt match); retry with a changed prompt or seed, up to a configured limit, then flag for human choice.
7. **Voice and lip-sync:** dialogue per character voice; lip-sync only on shots where faces talk on screen.
8. **Music and SFX:** licensed or AI-generated with commercial rights; logged in the asset ledger.
9. **Edit:** assemble, color-match, transitions, captions (burned-in for Shorts/Reels/TikTok), sound mix, loudness normalized, title card, end cliffhanger, "AI-generated" disclosure where required.
10. **Versions:** 9:16 and 16:9 from one master where possible; trailer and teaser clips.
11. **Quality gates and publish:** reuse the gates and SEO steps from `media-studio-expansion`; human approval as configured.
12. **Learn:** pull retention and CTR per episode; feed what works back into the next script.

### 3.2 Provider router and keys
- One interface per kind: `TextGen`, `VideoGen`, `ImageGen`, `Voice`, `Music`, `LipSync`, `Upscale`.
- Config chooses the default and fallback model **and host** per shot type and per channel; each adapter reads its key from a named environment variable set in config.
- The router picks the cheapest model and host that meet the shot's quality need, falls back to the next if one is down or its key is missing, respects each provider's rate limits, and records cost per call and per key.
- Before each paid call it checks: key present, our cap not exceeded, estimated cost under the per-call limit.
- Async jobs with polling or webhooks; idempotency keys so a retry never pays twice for the same shot; results cached by a hash of (model, prompt, references, seed, settings).
- A `keys check` command lists every configured provider, whether its key variable is set (yes/no only), and spend vs cap.

### 3.3 Data
- Series → episodes → scenes → shots → takes, each with status, cost, provider, files, prompts and the chosen take.
- Character and asset ledgers (license, source, model, host, date).
- Everything resumable: a crashed run continues from the last finished shot.

### 3.4 Studio MCP server

Extend the **existing MCP gateway** (keep its rules: logged calls, change tools off unless switched on, nothing publishes or deletes on its own) with a film toolset, so I can drive the studio from Claude Code. Use the `mcp-builder` skill. Proposed tools:

| Tool | Type | What it does |
|---|---|---|
| `film_list_series` / `film_get_series` | read | series, bible, characters, episode status |
| `film_get_episode` | read | script, shot list, takes, costs, status |
| `film_estimate_cost` | read | cost estimate for an episode or shot list before spending |
| `film_storyboard` | read | contact sheet link for keyframes or takes |
| `film_job_status` | read | status of generation and render jobs |
| `film_budget` | read | spent vs cap per series, channel, key, day, month |
| `film_keys_status` | read | which provider keys are set (yes/no only, never values) and their spend |
| `film_create_series` | change | create a series from an approved bible |
| `film_plan_episode` | change | write script + shot list (no paid calls) |
| `film_generate_keyframes` | change, paid | keyframes for approved shots, within budget |
| `film_generate_shots` | change, paid | video for approved keyframes, within budget |
| `film_choose_take` | change | pick or reject a take |
| `film_render_episode` | change | edit and export versions |
| `film_queue_publish` | change | puts an episode in the approval queue; never publishes directly |

Rules: every paid tool requires a cost estimate under the cap and an explicit `confirm` flag; read tools are always on; change tools follow the gateway's on/off switch; inputs validated with schemas; errors are clear and actionable; no tool ever returns a key value.

### 3.5 Safety and rights
- **Original characters only.** No real people's faces or voices except mine (with my consent), no celebrities, no copyrighted characters, no imitation of real brands.
- No sexual content, no minors in romantic or harmful situations, no graphic violence beyond platform rules.
- Label AI-generated content where each platform requires it.
- Check each model's and host's terms allow commercial use of outputs; record it in the ledger.
- Never fake news, events or real people's statements.

### 3.6 Config layout (example, adjust to the existing code)
```
config/
  providers.yaml        # adapters, hosts, model IDs, endpoints, rate limits, key variable NAMES (no values)
  routing.yaml          # shot type → default and fallback model + host
  budgets.yaml          # caps per series, episode, key, day, month
  channels/<name>.yaml  # channel profile (platforms, format, approval)
series/<slug>/
  bible.yaml            # world, style, characters
  characters/<name>/    # reference images and voice settings
prompts/
  shot_templates/*.md   # versioned prompt templates
.env.example            # every key variable name with an empty value
docs/studio/film/keys.md  # key names, provider, purpose, cap, rotation date (no values)
```

🛑 **Checkpoint 3:** I approve the design.

---

## Phase 4: Build plan and roadmap

Small steps, each shippable and reversible, each behind a feature flag and tried on the **test studio** first:

1. Config + schema validation + secret scan check + adapter interfaces + `keys check` command (no paid calls).
2. Provider adapters for the 2 chosen video models + 1 image model + text model routing, with mocks and one real minimal test each.
3. Series bible and character sheet generation; consistency check across sheets.
4. Script and shot-list planner (uses existing script and fact-check where relevant).
5. Keyframes + storyboard contact sheet.
6. Shot generation with auto-check, retries, caching and cost tracking per key.
7. Voice, lip-sync, music, SFX.
8. Edit and export (ffmpeg / Remotion), 9:16 and 16:9.
9. Film MCP tools (read tools first, then change tools off by default).
10. Quality gates + approval queue + publish via the existing upload flow; then the other platforms from `media-studio-expansion`.
11. Analytics loop: retention and CTR per episode back into planning.
12. Cost optimization pass using the cost tools and real numbers from `COSTS.md`: re-compare hosts, batch discounts, caching hit rate.

For each step write in `docs/studio/film/04-roadmap.md`: goal, files, tests, definition of done, expected cost, keys needed (names), rollback.

🛑 **Checkpoint 4:** I approve the roadmap and pick the first step.

---

## Phase 5: Build loop (repeat per step)

1. Rule 0 (progress file, skills, plan, budget, keys needed).
2. Branch per step. Tests first.
3. Build to the design. No hard-coding.
4. Run tests, lint, type checks, the secret scan. Fix failures.
5. One real minimal run if the step uses a provider; check the output yourself; record its cost.
6. Have a separate review agent (code review or dod-guard) check the change against the step's definition of done, so the work isn't grading itself.
7. Update the progress file, `DECISIONS.md`, `COSTS.md` and docs.
8. Report in a few lines: what works, evidence, cost, not verified, keys missing, rollback, next.
9. **Don't** push, deploy, switch on MCP change tools, publish, connect accounts, create provider accounts or keys, or spend above the approved estimate without my OK.

🛑 Stop after each step.

---

## Phase 6: First pilot episode

When the engine works end to end on the test studio:
1. One pilot series bible and one 60–90 s episode.
2. Storyboard review with me before video generation.
3. Full episode; you watch it and check: character consistency in every shot, lip-sync, audio levels, captions, hook in the first 3 seconds, cliffhanger, disclosure.
4. Real cost per episode vs the estimate, broken down by stage and provider, and compared with what the same episode would cost on an all-in-one platform (using its current public prices).
5. I approve before anything is published.

---

## Cost rules

Follow `CLAUDE.md` section 5 and Rule 3, plus:
- Storyboard with cheap keyframes before any video generation.
- Default to the lowest resolution that looks good on a phone; upscale only finals.
- Prefer image + motion or Remotion for shots without real action.
- Cap retries per shot; flag for human choice instead of looping.
- Cache every result by input hash; never regenerate an identical request.
- Hard caps per episode, series, key, day and month in config; the router refuses calls that would exceed them. Matching caps set in each provider's billing dashboard.
- Use the cheapest model and host per shot type that passes the quality check; re-run the bake-off when new models or prices appear.
- Show the estimate before every paid batch; log the real cost after.

## Definition of done (whole project)

- A pilot episode made end to end through the pipeline, checked and approved by me.
- Real cost per episode measured, under the cap I set, with the comparison against an all-in-one platform.
- All providers called with my own keys from environment variables; no secrets, model names, URLs or prices in code; the secret scan passes.
- Tests pass in CI; one-command local run documented.
- Film MCP tools work from Claude Code with logs; paid tools need confirmation; no tool exposes a key.
- `PROGRESS.md` shows every step with skills, tools, MCP tools, keys (names), costs and checks.
