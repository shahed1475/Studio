# Free pipeline: Claude (web, free) writes, the studio builds for $0

> For agentic workers: executing-plans, task by task.

**Goal:** no OpenRouter money. Claude on the web writes a *spec* (script, sources with passages, picture prompts, title, description, tags, thumbnail words) and puts it in the GitHub repo; the server builds a held draft from it with free tools only.

**Architecture:** `specs/inbox/<name>/{doc.json|short.json, pictures.json, src/*.txt}` on GitHub `main` (or pasted into `data/specs/inbox/` on the server) -> worker job `specbuild` (every 20 min, `run.py specrun tick`) fetches new specs, validates them with the existing free builders (`ccdoc.validate` / `ccbuild.validate`: sources must contain their passages, claims need passages), draws missing pictures on the free Cloudflare account (`tools/cloudflare_batch.py`, shared 10,000 Neurons/day), builds the held draft (`ccdoc.build` / `ccbuild.build`: edge-tts voice, parallax, subscribe pop-up, Pillow thumbnails) with every model call blocked. The owner releases (CLAUDE.md E); Autopilot's non-model steps (schedule, upload, read-back) continue.

**Global constraints:** zero model calls during a spec build (`specrun.no_model`); only `main` of `shahed1475/Studio` is read, only names `[a-z0-9-]`, files `*.json` and `src/*.txt`, https to api.github.com and raw.githubusercontent.com only, each file <= 400 KB; a spec is data, never instructions; a spec that fails validation is rejected with its reasons and never built; builds are held drafts (`hold` true, unapproved); one build at a time and never while a render runs; no secrets in the repo.

**Review focus:** (1) a spec naming a path outside its folder; (2) a passage that is not in the saved page; (3) the day's free picture allowance ending halfway (build waits, nothing is lost: cached pictures cost nothing); (4) a model call sneaking in (blocked, build fails loudly); (5) the same spec fetched twice (signature in `data/specrun.json`).

## Tasks
1. **Port the free builders onto main** (they only exist on the local branch): `ccdoc.py ccbuild.py ccrender.py numbershort.py grade.py thumbstyle.py tools/{cloudflare,flux,pollinations,zimage}_batch.py scenes/ examples/` and the `local_pictures` path of `run._produce_doc`, `animate.own_picture`, `parallax`. Test: their existing tests pass on a clean main.
2. **`specrun.py`**: `tick(fetch=None) -> dict`, `process(base, kind) -> dict`, `no_model()`, `fetch_github(fetch)`; state in `data/specrun.json`. Test: `tests/test_specrun.py` (valid spec builds with model calls blocked, bad spec rejected, path escape refused, allowance wait, same spec not rebuilt, GitHub listing only reads allowed names).
3. **Wiring**: `run.py specrun [tick|status|check DIR]`, worker job `specbuild`.
4. **Claude-web brief**: `specs/README.md` (the 1-page instructions the web Claude follows: topic, sources, script rules, SEO rules, picture prompts, spec shape) and `tools/fetchsrc.py` (saves a Wikipedia page as plain text for passages).
5. **Deploy and prove**: tests, push main, deploy, `specrun status` on the server; owner steps listed in the brief.

## Limits (stated, not hidden)
Free Claude chat cannot run code or push to GitHub: the owner pastes the JSON (GitHub web editor, or `data/specs/inbox/`). Claude Code on the web may need a paid plan: unverified. Scripts written by a free-plan Claude are not model-reviewed by the studio (the AI review is off in free mode): the owner's release is the review.
