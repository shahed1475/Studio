# Studio progress

## Status now
- Current phase / step: Foundation steps 1 to 4 done; step 5 (off-server backup) waits for the owner to create a private GitHub repo; Remotion test waits for the owner
- What works end to end: the stories pipeline (about 25 min, about $1 a documentary), 862 tests pass; Autopilot is ON again (owner, 25 Oct 19:24 UTC); ecc plugin removed
- What's broken or blocked:
- API keys needed but missing: (variable names only)
- Next step (26 Oct): owner saves the capped key in the TEST studio, then Phase E real run (docs/studio/NEXT-STAGE.md); earlier: owner approves the migration plan at Checkpoint 5 (docs/architecture/06-migration-plan.md) and picks the first step (suggested: step 1, cloud tests) (docs/architecture/01-current-state.md, 02-problems.md), then Phase 3 requirements
- Money spent so far (this project): $0 for this kit setup; studio spend about $2.9 on 24 Oct

## Log
### 2026-10-27 - Channel audit (owner: "check every video: title, thumbnail, description, keywords ... you are allowed to change", before any push)
- Read-only audit of all 12 uploads through the YouTube API on the server (channel: 6 subscribers, 681 views). No file was uploaded twice (no video id shared by two records, nothing on the channel missing from the records); the duplicates were different videos on one story (3 Thunderbird Shorts, 2 Hong Gildong), made before the one-story rule. The two Thunderbird Shorts y6Cyujv7vZg (252 views, record says hold) and 6wmhp10qR1s (6 views) are BOTH public: owner decision, not touched.
- Changed on YouTube (owner allowed metadata and thumbnails; privacy never changed, read back from the API): 8 descriptions (5 weak "This video covers..." openers rewritten from the facts already in them, 3 proper names in lowercase fixed), 1 title (Skinwalker Ranch Short now names its subject), 3 documentary thumbnails (Bell Witch: caption ghost gone, hook BELL WITCH VOICE; Pied Piper: PIED PIPER 1284; La Llorona: LA LLORONA'S MANY ORIGINS and a river picture instead of a tree photo). Old values: data/audit_backup_20261026-1823.json on the server (inside the worker's data folder); old thumbnails are the ones YouTube served before. Records on the server were updated to match so the re-check does not undo it.
- Code (local commit, not pushed or deployed): `seo.ensure_lead` capitalises the phrase like a name (the bug behind "The la llorona legend"); `thumbnail.hook_for` no longer teaches the model "<NAME> REAL STORY" (3 of 6 documentary hooks used it) and prefers a real detail over generic words; tests/conftest.py isolates agentlog, agentbus and lessons (tests had written 99 invented events into the local activity feed; removed from data/agent/events.jsonl, backup .bak-27oct).
- Not verified: whether the new thumbnails or openers raise clicks (impressions and click rate are only in Studio; views are 4 to 252 per video); whether YouTube stores the AI-content flag (containsSyntheticMedia is not returned by the API either way); Shorts thumbnails show a caption fragment (YouTube picks the frame), left alone.
- Tests run: full suite 1269 passed (local).
### 2026-10-26 - Off-server backup repo (owner: "create the private github repo, you have full permission")
- The private repo shahed1475/studio-records-backup ALREADY existed (made 24 Oct, private, one deploy key "Story Studio server (backup push)"), and a systemd user timer studio-backup-push.timer on the server already pushed nightly at 03:45 UTC (last real push 25 Oct 03:45). What was missing: the new push marker, so the Risks card said "no copy off the server". I ran deploy/backup_push.sh once (2 archives pushed, marker written); the Risks row "Losing the records" is now ok ("off-server copy is 0 hours old").
- Mistake and cleanup: before noticing the repo existed I made a second deploy key; it was removed from the repo and the server (the original key and the original timer are untouched). I replaced ~/.ssh/known_hosts_studio_backup with GitHub's published host keys (from `gh api meta`).
- Caps: the owner said they set the cap to $3 but both studios still read $1.50 (llm.json unchanged); the owner then left cap changes to me. The test clip costs about $0.24, so no change is needed; I will only raise a cap when a test needs it and will say so here.
- Also: a probe with zero size or NaN length is now a clean rejection (suite 1160 passed).
### 2026-10-26 - Owner approved "1,2,3,4": done
- (2) min_balance now holds AFTER the clip is paid (balance minus the clip's estimate must stay at or above the floor; nothing bought otherwise). Test added; suite 1157 passed.
- (3) Pushed feature/footage-tool, PR #1, CI green on both runs (pytest 1m29s and 1m16s), merged to main as e659dd4, deployed to the owner studio with deploy/deploy.sh (no render was running; worker not restarted; dashboard restarted and healthy; 40 files changed). Risks card on the server shows the new backup row ("no copy has been pushed off the server yet"). Autopilot is still OFF (it paused itself on La Llorona on 25 Oct 14:19 UTC): turning it on is the owner's switch, not done by me.
- (1) La Llorona: YouTube's own read shows it PUBLIC (no schedule left) with the new title; nobody needed me to change visibility.
- (4) The capped OpenRouter key in the TEST studio can only be saved by the owner in its Settings; checked earlier: not set. Then Phase E steps 3 to 6 can run.
### 2026-10-26 - Checks done by me: test studio synced, keyless proofs, browser look, La Llorona private (finding)
- Test studio (NOT the owner studio): code from the committed branch copied with `git archive HEAD` (tracked files only, no secrets) to ~/footage-src on the server, then `STUDIO_SRC=~/footage-src deploy/tenant.sh sync test`; worker and dashboard restarted, healthy; container runs Python 3.13 (local 3.14), config/footage.json and tools/footage/clipgen.py are there. The owner studio was not touched.
- Bad-source proof in the real test container (dummy value instead of a key, throwaway config with https://127.0.0.1:9): run FAILED with the reason "request failed after 2 tries ... /credits", no job id, cost_booked 0.0, spent today 0.0. A non-https base_url is refused at config load. This proves modules, config and the fail-closed path load in the real image. A failed run record "footage-proof-badsource" now exists in the test studio's /footage page (harmless; delete when you like).
- NOT done: the real clip run and the cap-refusal proof (both read the live OpenRouter balance first, so they need the owner's capped key in the test studio: checked, it is NOT set; cap 1.5, enabled False).
- Browser check (Chrome, throwaway local server, fake data, network blocked): /channels, /now, /footage and the main page load; links correct; /now shows "Footage clips last run done, 1 started today"; sidebar links visible; no sideways scroll at 616 px (the window would not go narrower than that, so 390 px was NOT checked).
- La Llorona doc (ySdp68IDtAE): YouTube's own status read shows it PRIVATE with no schedule, while 7 other API uploads are public and Voynich is scheduled. Autopilot paused on it at 14:19 UTC. I did not touch visibility. Earlier event (24 Oct) shows the cause pattern: a Studio edit can clear a schedule. The "API project stays private" theory is refuted; docs and the alert text corrected (commit after 39879b3). The owner still has to decide to make it public (outward-facing, not done by me).
- Title of La Llorona changed in YouTube Studio at the owner's request: "La Llorona: Where the Weeping Woman Legend Really Comes From" (reload showed it saved). The studio's record updates itself on its next re-check ("The saved title now matches YouTube" events exist).
- 390 px check DONE with Playwright (viewport 390x800, throwaway local server, fake data): /channels, /now, /footage and the main page have no sideways scroll (scrollWidth 390). Found and fixed a real defect: the new page links were only in the desktop sidebar, so they were hidden on a phone; they are now in the phone "More" menu (checked: Right now, Footage clips, Channels visible inside the screen). Console errors seen were only the missing favicon and my fake video's thumbnail.
- INDEPENDENT REVIEW of tools/footage/clipgen.py DONE (a separate read-only agent, 26 Oct; its report is data, I re-checked each claim in the code before acting). Confirmed and fixed: (1) NaN or Infinity in config/footage.json passed load_config and would have switched the caps off (now `math.isfinite`); (2) a provider `usage.cost` of 0 refunded the whole booking even when the balance fell (0 is now treated as unreadable, so the balance rule applies); (3) a give-back or correction after midnight UTC landed on the new day (now booked on the day of the reservation, from the run's created_at); also a NaN balance is now unreadable. Mutation-checked: 13 new tests fail without the fixes. Suite: 1156 passed.
- Reported by the reviewer but NOT changed (decisions or low risk, logged for the owner): the refund test can be fooled by a top-up during the wait or a stale balance on `resume`; `resume` never settles against `usage.cost`; `min_balance` is checked before the buy, not after the estimate; a real charge above max_clip_cost_usd is booked only up to the cap; the audio price is not read; interrupt windows leave money OVER-booked (safe side), never under; a 2xx with no job id cannot be resumed (money stays booked).
- Tests run and result: full suite 1156 passed (local, after the review fixes).
### 2026-10-26 - Next-stage Phases A to D built and tested with mocks (branch feature/footage-tool; nothing pushed, merged or deployed)
- Resumed from: the working tree already held Tasks A1 to A3 (uncommitted); I checked them (full suite green), then committed dbb163b.
- A1 to A3 (footage money rules, commit dbb163b): the provider's own `usage.cost` is booked instead of the estimate; a live price check (`/videos/models`) runs before any money is reserved and fails closed; a `failed` job is given back only if the balance did not move (else it stays booked).
- B1 to B3 (commit b44ae10): Risks card row "Losing the records" now also shows how old the OFF-server copy is (`backup.pushed_age_hours`, marker `backups/last_push.txt` written by `deploy/backup_push.sh`): watch if never pushed or older than 30 h (not 24: the push runs after the 03:30 backup, so 24 h would flap), act over 72 h. `/now` has a footage block; new read-only `/channels` page (`channelsview.py`, `channelconfig.load_all`); sidebar links to Right now / Footage / Channels; `tests/test_dashboard_routes.py` reads the route table from the code and checks every GET route with empty and populated data (no 500, JSON for /api, nothing opens without the login once a password is set, outbound network blocked).
- Found and fixed on the way: both channel templates (`config/channels/tech.json`, `crisis.json`) said `human_approval: false`, against requirement R10 (a new channel type starts with a person approving). Now true. They are templates only: the live gate is still `data/profile.json`, unchanged on every server.
- C1 (commits after b44ae10): `githubfacts.fetch_repo` (real read: stars, licence, latest release, README; each dated). A rate limit, outage or missing repository gives facts marked `unknown` with the reason; the GitHub token (optional) is checked for shape and goes only into the Authorization header. Owner-written fields (description, release tag, README) are cleaned to one line and printed inside a fence in `githubfacts.render` (an automated security review pointed out the description and tag were outside the fence: fixed, with a test).
- Live smoke, read-only, no token, 3 public repositories (26 Oct 2026): GNOME/gimp (a mirror): 6,546 stars, licence NOASSERTION (GitHub could not detect one licence), no GitHub release; KDE/krita: 10,633 stars, GPL-3.0; KDE/kdenlive: 5,935 stars, GPL-3.0; no release on GitHub for any of the three. The GIMP result exposed a wording bug (NOASSERTION would have read as a licence name): fixed, it now says "do not state a licence".
- C2: `techreview.py` (fail-closed script check, same style as `crisisreview.py`): held when facts are unknown, a star count differs from the fetched one, a star count has no "as of", a star count is written in words, a "free / open source" claim names a repository without a detected open-source licence, or 8 words of the README are copied. `tests/test_tech_dryrun.py` runs profile -> prompt -> mocked model answer -> verdict. Limits: only star counts are number-checked; the meaning of a sentence is not.
- D: `docs/studio/COSTS.md` written (measured numbers only, each with its source).
- Tests run and result: full suite `.venv/bin/python -m pytest -q`: 1137 passed (local, 26 Oct).
- Browser check of the new pages (B3 asked for one): NOT done in this session; the pages were checked only through HTTP tests (status, JSON, login). The Channels page copies the layout of /now, but nobody has looked at it at 390 px.
- Not verified: any real footage run (Phase E needs the owner's capped key in the TEST studio); the OpenRouter video price list shape and whether failed jobs are billed (from public docs, which may change); the off-server copy age on a real server (no repo exists yet, so the card will say watch until the owner creates it).
- Needs the owner: (1) Phase E item 1, the capped OpenRouter key in the TEST studio's Settings; (2) a private GitHub repo and deploy key for the off-server backup; (3) yes before any push, merge to main or deploy; (4) the Hong Gildong release decision (still held).
### 2026-10-25 - Owner studio: cap raised for today, Hong Gildong Short repaired, 26 Oct documentary started (owner's explicit go-ahead in chat)
- Owner decisions (asked, answered in chat): fix the Hong Gildong Short title; raise TODAY's daily cap to $3; make the 26 Oct documentary slot's video.
- Money: ~/studio/llm.json daily_budget_usd 1.5 -> 3.0 (backup llm.json.bak-25oct-cap on the server; read live by the worker: 3.0). MUST BE PUT BACK to 1.5 when the documentary is done (see "Next").
- Hong Gildong Short (held, was failing title_matches): `run.py repair` (sanctioned path, Autopilot lock held): new title "Why Tradition Credits Hŏ Kyun With Hong Gildong", description rewritten (the unsupported "because its author is unknown" claim removed), reviewer verdict pass, cost $0.049. Narration NOT re-rendered: its first line still says "Korea's 'John Doe' novel may have an author: Hŏ Kyun" (the reviewer no longer flags it; I think it is still a loose label). Hold left ON, not approved, not scheduled: the owner decides. Only warning left: seo_title_front (the phrase "hong gildong" starts after character 40). Backup of the old record: ~/hong-short-meta.bak-25oct.json on the server.
- 26 Oct documentary: one Autopilot pass made nothing (the slot Mon 26 Oct 22:00 UTC starts preparing about 08:00 UTC on 26 Oct, and the weekly limit of 5 videos per 7 days is already exceeded: 12 in the window, Risks card at "watch"). So `run.py doc` was started by hand in studio-worker (log ~/doc-26oct.log on the server); the studio's own ranking chose "Mami Wata". Not scheduled or approved by me; Autopilot's normal flow (review, 2 h window, private upload) applies.
- Commit 9340567 on feature/footage-tool (local only): footage tool second-review fixes + dashboard "Footage clips" page; 1020 tests pass. Browser test (Chrome, isolated demo with a fake provider and a real H.264 clip, no network, no money): page loaded with done / failed-download / over-cap runs, clip played 8 s at 1280x720, contact sheet and ledger row shown, no sideways scroll at 390 px. The first demo clip used MPEG-4 part 2 and did not play (my demo's fault; the server sent identical bytes).
- NOT done: real footage run on the test studio (its OpenRouter key is missing: saved by the owner in that studio's Settings, never pasted in chat), the cap-block and bad-source proofs on the test studio, the architecture map (published artifact; no link in this session), COSTS.md (none exists).

### 2026-10-25 - Footage tool: second review fixes, dashboard "Footage clips" page (mocks only; NOT committed)
- HANDOFF (read this first): branch feature/footage-tool; HEAD 424295e; everything below is uncommitted in the working tree. Test studio OpenRouter key is MISSING (checked yes/no in studio-test-worker): waiting for the key, so the real run, the cap proof, the bad-source proof and the dashboard link on the test studio are not done.
- Done: 2 failing tests fixed (test-fake bug; an `https://` literal in clipgen replaced by a urlparse scheme check). Second independent review (11 findings) fixed in tools/footage/clipgen.py: resume gives money back on a provider-failed job and catches every error; a catch-all marks the run failed; Ctrl-C releases or keeps the booking by how far the submit got; a balance fall above cost_warn_factor is booked (up to max_clip_cost_usd); streamed capped download with identity encoding; ffprobe length/height/shape check; broken-pipe-safe progress lines; a new paid run is refused while a same-scope run with a job is still "running". Also: footagestore.runs() takes scope/run id from the folder; footageview survives bad records; dashboard.send_ranged gives 416 and suffix ranges, nosniff; run_remote.sh resume hint goes through ssh; 3 new keys in config/footage.json.
- Dashboard "Footage clips" (/footage, /api/footage, /footage/file/...): footagestore.py, footageview.py, footage.html, behind the existing login; tests/test_footageview.py (11 tests).
- Tests run: full suite 1015 passed (local), before the re-check below.
- Not verified: a third reviewer (re-check of these fixes) was still running when this was written: its result is not in; real OpenRouter video API shape and the $0.03/s price; the real container (config/ and the new modules in the test image); phone width of the page; architecture map and COSTS.md not updated (no COSTS.md exists in the repo).
- Not fixed on purpose: run.log name reused in ~/render-out; ffmpeg picture filters in code; min_balance not tied to autopilot; no per-video MAX_VIDEO_COST for real video scopes.
- Next: read the re-check result and fix it; commit on the branch; owner saves a capped key in the test studio; sync the test studio; one smallest real run; cap proof; bad-source proof; give the dashboard link.
### 2026-10-25 - Footage tool: built, reviewed, cost booked (mocks only; no real run yet)
- Goal: a guarded, config-driven paid clip generator with an asset-ledger row, run only on the TEST studio
- Done: branch feature/footage-tool (commit 424295e, local only, not pushed, not synced): tools/footage/clipgen.py, tools/footage/run_remote.sh, config/footage.json, tests/test_footage_tool.py (35 tests), names added empty to .env.example (FOOTAGE_SSH_TARGET, FOOTAGE_SSH_KEY, FOOTAGE_CONTAINER, FOOTAGE_LOCAL_OUT); scratch scripts ~/ft.sh, ~/ft2.py, ~/ft2.sh removed
- Independent review (separate agent) found 11 points; fixed: paid clip kept when the ledger write fails, job id printed at submit and named in every error, job id validated (no path or shell injection), absolute paths, container allowlist (default studio-test-worker only), quoted and validated shell values, sha256 check of the copied clip against the ledger row, AI label + prompt hash in the ledger row, printable short server text, weak tests replaced
- Finding 8 (owner approved): the clip cost (list price per second x length, from config) is booked through llm.cost_scope into data/video_costs.json and into the day total, so it counts against the daily cap; a clip that would go over the cap is refused before any call; a provider-failed job books $0; a job that may have run is booked even if a later step fails; per-clip cap in config. Tests prove: cost recorded in both files, 6 clips fit the $1.50 cap and the 7th is refused with no HTTP call
- Tests: full suite 964 passed (local); skills: none; MCP tools: story-studio-rw (read), key names: OPENROUTER_API_KEY (already used by llm.api_key), no new key names
- Real cost so far: $0.24 for the first test clip (owner studio, before the rules); nothing spent by the new code
- Not verified: the real OpenRouter video API shape against this code (mocks copy its assumptions); the price per second ($0.03 list price, not re-checked live); whether the test studio image has the config, python version and modules the remote step needs; the model's commercial-use terms; the fixes made after the review have had no second review (a new reviewer is planned after the real run)
- Next: the owner saves a separate capped OpenRouter key in the TEST studio's dashboard Settings; then push the branch, sync the test studio, run once, look at the clip, second review
### 2026-10-25 - Banner live; keys for the tech channel (Part 4 step 1); real-upload check not yet possible
- Banner: now visible on the signed-out channel page (name, banner, picture and About text all show)
- Real-upload check (Part 1 3a): server clock 00:59 UTC 25 Oct; La Llorona (slot 14:00 UTC) and Voynich (17:00 UTC) are scheduled but not uploaded yet (Autopilot uploads about 12 hours before the slot: about 02:00 and 05:00 UTC); nothing to check yet; the daily spend counter reset at midnight UTC so the cap is open again
- Keys the tech channel needs (Part 4 step 1): NO new paid provider. OPENROUTER_API_KEY exists (credit is the limit: owner top-up needed for any new video); GITHUB_TOKEN optional, free, read-only for public repos (raises limit 60 to 5,000 an hour; not needed for mocks or a handful of repos); voice edge-tts and Remotion graphics need no key; YouTube needs the owner's own Google sign-in per channel (OAuth), not a pasted key; names added (empty) to .env.example: GITHUB_TOKEN, BACKUP_REPO_URL, BACKUP_SSH_KEY_FILE
- Not verified: prices (nothing paid is added); the GitHub rate limits are as of earlier research
- Next: owner says when the uploads happened (I then read the log and the records); credit top-up decision; the tech pipeline build

### 2026-10-25 - Tech channel set up in the owner's browser (competitor research first)
- Goal: check the new channel, research competitors, set the channel up
- Found: the owner's channel is UCWGYkqwWfGWmOT4vAL0RVaQ, handle @thetoolpantry, name was "thetoolpantry"; @toolpantry is a different channel (UCeqHkBg1Qw2DUNLaYlnxajQ): my earlier "handle looked free" check was true when made and stale later
- Competitors (YouTube channel search "open source alternatives to paid software", read in the owner's Chrome, public pages only): about 20 channels, almost all tiny (1 to 571 subscribers: OpenSoft 12, Libretech 302, GitLaunch 18, Repo of the Day 7, OverClocked 89, rialbbeTV 2.46K); one large channel, TJ FREE (321K subscribers, 565 videos; its newest videos in the "Latest" list were about 3 years old, so it looks inactive: from one page view, not verified); formats seen: "daily GitHub repo" shorts, "Name | Free <category> app" 2 to 4 minute screen demos with a branded corner ribbon on an app screenshot; hype wording on some About texts ("insane"); opportunity: dated facts, licence clarity, "what you lose by switching", plain language, no hype
- The watch skill was NOT used on competitors' videos: it downloads with yt-dlp and CLAUDE.md forbids downloading other people's videos; I looked at their channel pages, titles and thumbnails in the browser instead
- Done in Studio (owner's explicit request to set the channel up): name "Toolpantry - Free Software, Explained" (published, confirmed on the public page); About text (published, confirmed publicly, 492 of 1000 characters); 8 keywords and audience "No, set this channel as not made for kids" (Settings saved toast); profile picture (shelf mark, generated locally, free) published and visible on the public page; banner (2560x1440, text measured inside the 1235x338 safe area, crop view looked at) published but NOT visible on the signed-out page yet
- Not done: playlists (empty public playlists are worse than none), links, trailer and featured video (no videos), contact email, country of residence (personal), upload defaults (the studio sets category, AI disclosure and audience per video through the API), watermark; channel switcher not touched; The Sleeping Library untouched
- Next: check the banner in Studio and on the public page; first videos need credit and the tech pipeline (Part 4)

### 2026-10-25 - Toolpantry channel exists; not reachable from the owner's browser account
- Done: public check: https://www.youtube.com/@toolpantry answers 200, page title "Toolpantry - YouTube", channel id UCeqHkBg1Qw2DUNLaYlnxajQ (the handle was accepted); read-only look in the owner's Chrome: YouTube Studio for that channel says "you don't have permission", and the account's channel list (youtube.com/account) shows only The Sleeping Library: so Toolpantry was created under a different Google account than the one signed in in this Chrome profile
- Not done: nothing entered on the new channel (no About text, keywords or settings); nothing changed on The Sleeping Library
- Next: owner signs in (themselves) to the Google account that owns Toolpantry in this Chrome, then Claude sets up About text, keywords and defaults with their go-ahead

### 2026-10-25 - Tech channel name chosen (no personal name)
- Done: personal-name options dropped at the owner's request; naming guidance read (short, easy to say and spell, signal the niche, check availability everywhere, a standalone brand suits a channel without a face; vendor blogs, general practice); 30 brand-style handles checked on YouTube (13 free); finalists Toolpantry, Nullcost, Freeharbor re-checked; web search for Toolpantry: no brand found; Nullcost: only technical meanings; domains: toolpantry.com resolves (likely registered), .net and nullcost.com/.net do not
- Selected: Toolpantry, title "Toolpantry - Free Software, Explained", handle @toolpantry (docs/studio/TECH_CHANNEL.md updated)
- Not verified: trademarks, other platforms, that YouTube will accept the handle at creation; nothing created on YouTube
- Next: owner creates the channel with this name; then About text, keywords, playlists with the owner's go-ahead

### 2026-10-25 - Tech channel: niche research and setup package
- Goal: research a good, audience-friendly tech niche and prepare the channel setup
- Done: YouTube autocomplete read for 16 seeds (the studio's seo.suggest; it always returns 14 so it shows WHAT people type, not volume); two web searches (vendor blogs: unverified growth and CPM figures; measured AIR Media-Tech data: Gadgets & Tech median RPM $2.33, Studio CPM $5.73); read-only look at the owner's browser: YouTube Studio is on The Sleeping Library (4 subscribers); I did not open the channel switcher, so I do not know whether a second channel already exists; owner decisions: a NEW channel (they create it), niche = all three under one promise (free/open-source alternatives first); package written: docs/studio/TECH_CHANNEL.md (promise, three series, name options, About text, keywords, layout, formats, 10 topic ideas, rules)
- Not done: nothing entered on YouTube; no channel created (account creation is the owner's step); names not checked for availability; no tech pipeline exists yet
- Next: owner creates the channel and tells me; then About text, keywords, playlists with the owner's go-ahead

### 2026-10-25 - Stage 2 (mocks only) merged: channel profiles, GitHub facts, asset ledger, crisis review agent
- Goal: build the tech and crisis channel parts with mocks, $0 paid; the owner chose the reviewer agent as the only approver of crisis videos
- Done: merged to main (cloud runs 40144983771 and 40145129136 green; 929 tests pass locally): channelconfig.py + config/channels/tech.json and crisis.json (checked when loaded, secrets only as variable NAMES, $0 daily budget, made_for_kids false, crisis official_domains empty on purpose), prompts/tech_script.md, githubfacts.py (dated facts, README carried as untrusted data, fetcher injected), assetledger.py (licences, authors incl. AI model, 64-hex hashes fail closed), crisisreview.py (fails closed: whole-number sourcing tied to the line and an official-domain allowlist, number words and title/description, manifest + ledger + hashes, context line, not-for-kids, AI label, evergreen only, weekly limit, input validation, crash-to-hold, two distinct model reviewers that see the sources; evidence file per verdict)
- Review: a separate adversarial reviewer agent found 6 ways a bad video could pass; all fixed with tests; the automated commit review then made 3 more findings (fail-open hash, footage not checked against the ledger, number words in title/description); all fixed with tests. 46 tests in tests/test_stage2_mocks.py (about 40 cases that must hold)
- Not verified / limits: it is a mock: it checks the evidence it is given, not that the evidence is true; the real source fetcher, the real model reviewers and the official-domain list do not exist yet (UN, WHO, World Bank, ICRC terms unread); nothing here is used by the live studio and nothing was deployed; the remotion branch spike/remotion is still unmerged
- Next: owner's different YouTube channel (name, Google login, which studio it is for); credit top-up before any paid call; real fetcher and reviewers with a smallest-possible paid test (Part 4); Part 1 checks after La Llorona uploads and the owner signs in through the tunnel

### 2026-10-25 - Next stage N1: Remotion one-template test (real numbers)
- Goal: measure render time, CPU and memory of one Remotion template on this server (plan approved by the owner; $0 paid; owner also said they will open a different YouTube channel for the new work: name and account still to come, nothing needs them yet)
- Done: branch spike/remotion (d50a7a8, pushed, NOT merged): render/ folder (Dockerfile node:22-bookworm-slim, Remotion 4.0.536 pinned (released 16 Oct 2026; latest is 4.0.538 of 22 Oct), one Timeline template driven by a props JSON, measure.sh); render/ is excluded from the user-studio sync in deploy/tenant.sh so it never reaches user studios (licence caution); built on the server from a separate clone (~/render-spike), image studio-render-spike 1.53 GB; run with --memory 2g --cpus 2 --network none while no studio render was running (host load 1.0)
- Real numbers (two runs, 10 s clip, 300 frames, 30 fps): vertical 1080x1920: 30.7 s then 21.7 s wall (45.7 and 32.7 CPU-seconds; the first run includes warm-up); wide 1920x1080: 12.8 s then 13.9 s wall (18.6 and 20.8 CPU-seconds); peak memory 1848 and 1856 MiB of the 2048 MiB limit (cgroup memory.peak)
- Output looked at: contact sheets of both clips (events appear one by one, "Facts as of 2026-10-25" footer present in both formats; the vertical layout leaves its lower half empty: design polish needed)
- Verdict against the plan's gate: GO with conditions: about 1.3 to 2.2 seconds of rendering per second of graphics, so a 60 to 90 s Short with 30 s of graphics is about 1 minute; memory sits at 90 percent of 2 GB, so use a 3 GB limit; one render at a time and only when the studio worker is not rendering (they share 4 cores)
- Not verified: speed with richer templates (images, maps, charts); behaviour with the worker rendering at the same time; the Remotion licence for a multi-user server (kept out of user studios); disk growth of the image over time; phone view
- Cleanup: temporary files I put in the worker container's /tmp were removed; ~/render-out holds two 0.25 MB test clips
- Next: N2 tech channel profile and N3 crisis review agent, mocks only

### 2026-10-25 - Part 2 deployed; Part 3 decisions
- Done: /now merged (d3c0879) and deployed, then a wording fix (879f41f): a video past its public time says so, a held upload says it is kept private. Live evidence: dashboard container healthy; nowview.build() on the live studio returned Autopilot ON, no pass running, spend $2.88 of $1.50 (over: new work paused until tomorrow UTC), 6 real videos with stages, 15 log lines; /api/now without login answers 401. 883 tests pass
- Owner decisions (Part 3 batch): (1) ONE crisis channel, adult audience, "not made for kids"; (2) money cap for a new studio: $0 paid until credit is added (mocks and free tools only); (3) approver for crisis videos: the reviewer agent only, and the owner wants that agent built "perfect so that it can check everything" (risk noted to the owner: war and crisis content is the highest-risk kind; the agent will fail closed: any doubt, any unverified number or any unsourced footage means hold for a human); (4) MCP change tools: switched ON (client side: user-scope MCP entry story-studio-rw with STUDIO_MCP_WRITE=1; still no publish, delete or settings)
- MCP: user-scope entry story-studio-rw added in ~/.claude.json (ssh -T deploy@vps-ai env STUDIO_MCP_WRITE=1 /home/deploy/studio-mcp/run.sh); it connects after Claude Code is restarted; NOT yet connected or tried; the server default stays read-only for any client that does not set the variable
- Not verified: /now seen in a browser on the live server (needs the owner signed in through the tunnel); phone width
- Next: the next-stage plan (Remotion one-template test, tech channel profile, crisis review agent) for the owner's approval before anything is built

### 2026-10-25 - Part 2: watching from your own computer, and the "Right now" page
- Goal: a safe way to open the dashboard on the owner's PC, plus a "what is happening now" view
- Done: docs/studio/LOCAL.md (A: SSH tunnel to the live dashboard on the server's loopback, B: a local test copy on 127.0.0.1:8914); new read-only page /now and data /api/now (nowview.py, now.html, route in dashboard.py, behind the same login): Autopilot on/off, a pass or dashboard job running, spend today vs the cap, what is being repaired, where each of the last 10 videos stands (being made, waiting for review, repair, approval, upload time, on YouTube, held), last 15 Autopilot log lines; 2 new tests (883 pass); branch part2/now-view pushed, NOT merged, NOT deployed
- Proof: B started on 127.0.0.1:8914 only (ss shows the loopback address), /, /now, /api/now all 200, screenshot of /now looked at (shows the PC's old local test videos, Autopilot OFF, cap $1.00 there: it is the PC's own data); A: tunnel opened from this PC, live dashboard through it: /login 200, / 303 to /login; tunnel closed afterwards
- Not verified: /now on the live server (needs the owner's yes to merge and deploy; the dashboard container restarts); the page was only looked at on desktop width; CI result of the branch not yet read
- Next: owner checks B, says yes to deploy /now; Part 3 questions

### 2026-10-25 - Part 1 step 2: off-server backup built and proven
- Goal: a daily off-server copy of the records (R4)
- Done: private repo shahed1475/studio-records-backup created by Claude with the owner's go-ahead (gh login, repo scope); SSH deploy key made ON the server (~/.ssh/studio_backup, mode 600, private half never left the server), public half added to that one repo with write access (deploy key id 167570333); GitHub's ed25519 host key fingerprint checked against the value in GitHub's API (match) and pinned in ~/.ssh/known_hosts_studio_backup; settings by name in the server .env: BACKUP_REPO_URL, BACKUP_SSH_KEY_FILE (a repo address and a file path, not secrets); deploy/backup_push.sh (commits 0a39428, 0e8a7c9, b42d55c) pushes the newest two archives as one replaced commit; a systemd user timer studio-backup-push.timer runs it daily 03:45 UTC (the host has no crontab; linger is on); no key or token was printed or committed
- Proof: pushed once; cloned the repo into a temp folder on the server, restored the archive and compared: same sha256, 552 files vs 552, diff -r clean, 0 secret-looking file names; a symlink planted as a newer backup was ignored; systemd run result: success; next timer fire Sun 25 Oct 03:45 UTC
- Review of my own change (automated commit review): 2 findings, both fixed: only regular backup-YYYYMMDD.tar.gz files (links ignored, gzip-tested), key and known-hosts paths must be plain absolute paths. Another bug found while testing: find needed -regextype posix-extended
- Not verified: the first scheduled run at 03:45 UTC (check the log ~/studio/logs/backup_push.log and the repo after it); the Risks card does not yet show the age of the off-server copy; the repo keeps old commits' objects on GitHub after a force push (private repo)
- Next: Part 2 (local view of the dashboard); real-upload check after La Llorona uploads

### 2026-10-25 - Review of the Part 1 entry (separate reviewer agent) and corrections
- Reviewer verdicts from the log alone: gate DONE; backup NOT DONE; real-upload check NOT DONE; dashboard buttons NOT DONE; money guard PARTLY. Credit arithmetic confirmed (8.426 - 1.50 = 6.93; 6.93 / 1.50 = 4.6 days)
- Accepted and fixed in this log: (1) the money guard is PARTLY proven (cap and credit effects shown with values patched in memory in the test studio; no new-video plan was ever produced there, so not shown end to end); (2) the gate was tried on a throwaway video and the owner studio has had one clean Autopilot pass, not a real video through it; (3) step 2 as given to the owner: private repo `studio-records-backup` under `shahed1475`, empty; an SSH deploy key made on the server, public half added as a repo deploy key with write access; server .env variables `BACKUP_REPO_URL` (repo address) and `BACKUP_SSH_KEY_FILE` (path of the private key on the server); no secret is ever pasted into chat
- Clarifications: dates in this log are the owner's local date (25 Oct); the server clock is UTC and read 23:26 on 24 Oct, so no upload has happened yet (Voynich uploads about 05:00 UTC on 25 Oct for its 17:00 UTC slot; La Llorona about 02:00 UTC for 14:00 UTC); spend figures differ because about $2.5 a day was the earlier average and $2.88 is what was spent today before the cap was lowered to $1.50

### 2026-10-25 - Part 1 step 1 (gate deployed) and step 4 (money guards)
- Goal: deploy the approval gate to the test studio first, then the owner studio (gate off); prove the $1.50/day guard
- Done: tests 881 passed locally; test studio synced from a separate clone of main cf2a73b (tenant.sh sync test; owner files untouched), then owner studio deployed with deploy.sh (cf2a73b, no render running, containers healthy, owner Autopilot pass clean, human_approval false, no profile.json)
- Evidence, gate (inside studio-test-worker, throwaway video in a temp folder, real planner): gate off -> approve + schedule; human_approval true -> schedule only, no approve; back off -> approve again
- Evidence, money (test studio container, values patched in memory): (a) with spend at the $1.50 cap llm.chat raised ModelUnavailable and made 0 paid calls; (b) can_afford is False for a doc and a Short with $0.12 left and True for a Short with $0.40; (c) credit $1.00 (under the $1.50 floor) -> the planner starts no work; credit $8 -> it plans ideas. Not shown end to end: a "make" action never appeared in the test studio (no YouTube login, no topics), so "no new video when the cap is hit" rests on (a), (b), tests/test_autopilot_budget.py and the can_afford check at autopilot.py:179 and :184
- Credit: $8.426 on 25 Oct; owner studio spent $2.88 today before the cap was lowered (cap_left -1.38). New work stops under $1.50, so usable credit is about $6.93, about 4.6 days at the full $1.50 a day (less if re-checks and reviews use the reserve above the cap)
- Not done: step 2 (needs the private repo from the owner); step 3a (no real upload yet: server clock 23:26 UTC 24 Oct, La Llorona upload due about 02:00 UTC); step 3b (this PC's browser cannot reach http://vps-ai:8913, and the dashboard needs the owner's login: needs the Part 2 tunnel and the owner signed in)
- Not verified: dashboard buttons, save paths of upload/reviewer/seo/thumbnail/subtitles on real data
- Next: owner creates the backup repo; Part 2 tunnel; check the next upload

### 2026-10-25 - Architecture map: teal steps, cost text, gate note (version 7)
- Done: (1) build steps 1, 2, 2b, 3a, 3b, 3c, 3d are teal in the Foundation view (step 4 teal, step 5 dashed); (2) "What it depends on" now says: credit $8.43 on 25 Oct, it spent about $2.5 a day before the money guard capped it at $1.50 a day on 25 Oct (the two numbers differ because the cap was set after that spend was measured); (3) the Human gate box in the Planned view says "merged, not deployed; off"
- Checked by eye on the desktop render: step rows 1 to 5, the Human gate box (after shortening its text, which first overflowed the box). The new "What it depends on" sentence was confirmed in the page text, not looked at as an image; phone width not re-checked this time
- Next: owner to say what to do about step 5 (private repo), deploying the gate, and the Remotion test

### 2026-10-25 - Architecture map: six fixes, republished (version 5)
- Done: (1) step 4 shown as merged in the build-steps box and caption; (2) first caption says "added on 24 and 25 Oct"; (3) steps 3a and 3c have full labels (two rows of step boxes, each with its modules and status); (4) the single server-to-services arrow is now a line across all five services, and each service says which step calls it; the Planned view got the same line; (5) the "planned next" legend item is gone from views 1 and 2 (kept in Planned); (6) a "Money guard: $1.50 a day, stops new videos under $1.50 credit" box sits next to OpenRouter
- Checked: desktop render (1100 px) of the Today, Foundation steps and services areas by eye
- Follow-up (same day, version 6): the Planned view's services label overlapped the new line; moved it above the line and re-checked the bottom of Planned by eye (clean). Phone width (390 px): looked at the top of the page and the Today diagram (frame scrolls sideways inside itself, the page does not); that render was made before the last label fix, so the Foundation and Planned diagrams were not looked at on a phone
- Next: a final phone check of the Foundation and Planned diagrams

### 2026-10-25 - Step 4 merged, CI lock test, diagrams, step 5 instructions
- Goal: finish the Foundation as far as it can go without the owner
- Done: step 4 (channelprofile.py + human_approval gate, default off) merged to main as 64bcd91 after CI run 40130494258 green; NOT deployed (gate is off by default, no behavior change until deployed and a profile.json exists); a cross-process lock test added to tests/test_records.py (CI form of step 2b; the cross-container check was done on the server earlier), merged after run 40130618146 green; architecture map republished (version 4): Foundation view added, Planned view updated (Safe writer, Cloud tests, Budget per studio, Human gate marked done; Weekly cap set to 5), "both" text fixed to "all three"
- Tests run and result: local 881 passed; CI green on both branches
- Not done yet (needs a later moment): checking the new save path in the logs after the next real upload; clicking each dashboard button on the live server (needs the owner's logged-in browser; only on a throwaway draft)
- Not verified: dashboard buttons; save paths of upload, reviewer, seo, thumbnail, subtitles on real data
- Next: owner creates the private backup repo (step 5); owner says when to start the Remotion test

### 2026-10-25 - Foundation step 3d deployed (R7 done)
- Goal: every record write goes through records.py
- Done: merged d7c425c (CI run 40128676921 green), deployed (containers restarted, healthy); test tests/test_records_only.py forbids hand writes; on the server: hold and release of the leftover clip draft went through records (2 lock files now exist, no tmp files), Autopilot pass clean, dashboard answers (303 to login)
- Tests run and result: local 877 passed
- Not verified: dashboard buttons (login needed), reviewer/seo/thumbnail/subtitles paths on real data; note: the hold/release test reset the leftover draft autopilot_fails to 0, so Autopilot may try to repair it again once the daily cap resets
- Next: step 4 (settings file and approval gate), step 5 (off-server backup, needs the private repo)

### 2026-10-25 - Foundation step 3c deployed
- Goal: R7 for titletest, upload, fixer
- Done: merged 51967db (CI run 40128258624 green), deployed; server: Autopilot pass clean, title test ran (4 public videos, all too early to judge, no change), all 13 records readable, no lock or tmp files yet
- Tests run and result: local 875 passed
- Not verified: upload and fixer save paths have not run on the server; known remaining risk: fixer still replaces the whole record (atomic, locked) during a repair pass
- Next: step 3d (the remaining modules) and the grep test; watch the next real upload (Voynich Sun 25 Oct 17:00 UTC, upload about 12 h before)

### 2026-10-25 - Foundation step 3b deployed
- Goal: R7 for autopilot.py
- Done: merged e19e997 (CI run 40127956251 green), deployed; one Autopilot pass on the server: no actions, no errors; all 13 records readable; no .meta.lock or .tmp files exist yet (no write happened)
- Tests run and result: local 874 passed
- Not verified: the new save path in autopilot has not run on real data (nothing was due); first real use: the next prelaunch (about 24 h before La Llorona, Sun 14:00 UTC) or schedule/upload
- Next: step 3c (titletest, upload, fixer); owner to watch the next pass

### 2026-10-25 - Foundation step 3a deployed
- Goal: R7 for recheck, safety, controls
- Done: merged e8c9cba, deployed; on the server one Autopilot pass (no errors, no actions), health check (0 due), heal (none needed); re-check skipped because the day cap ($1.50) is already used ($2.88 spent before the cap changed)
- Tests run and result: local 873 passed; CI green (run 40127572972)
- Not verified: the new save path in recheck/safety/controls has not run on the server with real data (nothing was due); first real use will be the next re-check after midnight UTC
- Next: step 3b (autopilot.py)

### 2026-10-25 - Foundation steps 2 and 2b: records.py and the lock check
- Goal: R7 groundwork; verify the lock across containers
- Done: records.py + 7 tests merged to main (e1aee1d), deployed; lock test on the server: the dashboard container was blocked while the worker held the lock (1 s wait), and succeeded after release; both saw the same merged record; test folder deleted
- Tests run and result: local 871 passed; CI green on the branch
- Not verified: CI on main after this merge (see gh run list); behavior under real writer load
- Next: step 3a (recheck, controls, safety use records)

### 2026-10-25 - Foundation step 1: cloud tests
- Goal: R8, tests on every push
- Done: workflow on branch ci/cloud-tests (not merged): first run failed (10 tests need ffmpeg), fixed by installing ffmpeg; second run green (GitHub run 40126606661); vetskill deprecation warning fixed
- Tests run and result: local 864 passed; CI green on Python 3.14
- Decisions made: owner granted the workflow scope to the GitHub login themselves
- Not verified: runtime stays about 1 minute; the run on main after merge
- Next: owner decides to merge the branch into main; then step 2 (records.py)

### 2026-10-25 - kit setup and Step A, Phases 0-2
- Goal: install the kit, start architecture-redesign
- Done: two skills added with extend.py (ai-film-studio scan 0/0/3, media-studio-expansion 0/0/0); docs/studio/PROGRESS.md; kit rules appended to CLAUDE.md with a precedence note; docs/architecture/01 and 02
- Skills used: architecture-redesign (read), vetskill via extend.py
- Tests run and result: none needed for docs; extend.py verify: 13 skills match
- Decisions made: kept the installed architecture-redesign (the kit copy differs by one line); did not commit or push
- Not verified / assumptions: current-state is consolidated from earlier audits, not re-read from code today
- Next: Checkpoint 1

<!-- Newest entry first. Copy this block for each step. -->
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
