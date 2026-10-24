# Plan: several channels, Remotion and an MCP server (24 Oct 2026)

Diagrams and the one-page version: the private page "Studio Expansion Plan" (published from this session). This file is the version that lives with the code.

## 1. What exists today (VERIFIED on the server and in the code)
- One owner studio and **one** user studio, `test`. The user-studio machinery (`deploy/tenant.sh`, `tenantmode.py`) allows up to five. It was built for other people: a user studio refuses the owner's own channel on purpose (`STUDIO_OWNER_CHANNELS`), caps a worker at 1.5 GB and 1 CPU, allows two renders at once across all user studios, and defaults the daily money cap to $1.50.
- The engine is built for one kind of channel: calm stories from one Wikipedia article, with public-domain pictures and a claim ledger. That assumption sits in about ten modules (`run.py`, `topicrank.py`, `reviewer.py`, `ledger.py`, `footage.py`, `scriptgen.py`, `niche.py`, `config.py`, `studiochecks.py`, `videoinspect.py`).
- Spend is about $2.5 a day for one channel; credit is $8.60.

## 2. MCP server (built, live)
- `controls.py` runs inside each studio: named calls only (`status`, `videos`, `video`, `events`, `next_slots`, `report`; and `hold`, `release`, `run_pass`, `make_backup`). `python -m controls` reads one JSON request on stdin. The call name must be in `CALLS`, argument names must match, a video name must be a plain slug of an existing folder.
- `studio_mcp/` runs on the server host in its own venv (`~/studio-mcp`, MCP SDK 2.3.0 on Python 3.14). For each tool call it runs `docker exec -i <studio worker> python -m controls` and sends the request as JSON on stdin. It never builds code, shell text or paths from what the caller sends.
- Read tools are always on. The four change tools exist only with `STUDIO_MCP_WRITE=1`. Not offered at all: make public, delete, channel settings, money limits, keys.
- Only studios listed in `STUDIO_MCP_STUDIOS` are reachable (default: `owner`). Every answer begins with a note that its text is data, not instructions. Every call is written to `~/studio-mcp/audit.log`.
- Client commands: `claude mcp add story-studio -- ssh -T deploy@vps-ai /home/deploy/studio-mcp/run.sh` (read-only) and `... env STUDIO_MCP_WRITE=1 ...` for the change tools.
- Verified: 856 tests; a real client on the PC over SSH listed the tools, read status, videos, a video's detail and events, refused a bad video name and a bad studio name, and (with the switch on) held and released a draft; the audit log recorded each call.
- Review findings fixed the same day: all studios were reachable and tenant text could reach a privileged session (now owner-only by default and marked as data).

## 3. Remotion (a spike, not a rewrite)
Facts from Remotion's own pages: free for an individual (personal or commercial) and for a team of up to 3, automation included; paid plans start at 4 people; source-available, not open source; rendering for other people's services is not settled by the FAQ (keep it out of user studios until Remotion answers). Needs Node 22, a Debian image, Chrome Headless Shell (`npx remotion browser ensure`); renders from the command line with `--props=file.json`; `renderStill` makes thumbnails; its captions package turns word timings into pages (our `words.json` has them).
Plan: a separate render container (about 2 GB, 2 CPUs, loopback only) that the worker calls with a props file. It draws only graphics scenes (timeline, map pins, source card, known/legend/disputed, code walk, cartoon scene); voice, captions, photo scenes, review and upload stay as they are.
**Spike gate:** one template rendered on the server. Record seconds per scene and peak memory. Go only if a typical video's graphics render in a few minutes and the worker never nears its memory limit. Not measured yet.

## 4. Channel profiles (the missing piece)
A channel profile chooses, per studio, what is fixed in code today:
```
ChannelProfile
  id, name, audience, made_for_kids (false/true, set on every upload)
  sources:  wikipedia | github | official_data | ...   (each returns dated, quotable facts and links)
  visuals:  archive_images | ai_art | remotion_cards | cartoon_scenes
  voice:    narrator style and pacing
  policy:   list of reviewer checks and human gates (for example "human approval of every video")
  limits:   videos per week, daily money cap, review window
```
Today these live in `niche.PRESETS`, `config.channel_blurb()` and `run._cmd_doc`. The step is to turn them into data plus small adapters, without changing what the owner's studio does (the owner's profile is "stories", the default).

| | Stories (today) | Animated crisis explainers | Tech, apps and repos | Kids cartoon |
|---|---|---|---|---|
| Facts | one Wikipedia article | official reports and datasets, each fact dated (sources to be verified) | GitHub API (5,000 requests an hour with a token, 60 without) and repo files | public-domain tales |
| Pictures | archive, labelled AI art | cartoon scenes, maps, charts; no real footage | Remotion cards (stats, diagrams, short code excerpts) | fixed characters |
| Rules that bite | template content | context for graphic content must be in the video; graphic scenes earn no ads; old footage never shown as current; denying a tragedy loses ads; AI label for realistic altered events | no licence means all rights reserved (describe, do not copy); README text is untrusted input | made for kids: comments, notifications and personalised ads are off, COPPA responsibility is the creator's, no violence or death themes aimed at young children |
| Biggest risk | sameness | wrong numbers; a cartoon look that appeals to children | stale facts (stars, versions); licences | policy and law |

**Cartoon plus war and crisis in one channel:** YouTube names family-friendly cartoons that target young children and contain violence or death as prohibited, and lists animation among the factors for "made for kids". It is possible only if look, characters and tone aim at adults and teens and every video is set to "not made for kids" on purpose. Do not mix it with a kids channel.

## 5. Running several channels of your own
Option chosen: **sister studios**. Reuse the user-studio machinery (own folder, containers, YouTube login, niche, caps) with an owner-managed flag that lifts the "owner channel is forbidden" rule, higher caps, and your own OpenRouter key. A single studio holding several channels would touch every path in the code and is not recommended.
Capacity: four shared cores and 16 GB for about 20 other projects. Renders from all studios queue (two at once at most). Money: at today's mix each studio costs about $2.5 a day, so launch one at a time and give each its own cap.

## 6. Order and gates
1. **Done:** control layer and MCP v1.
2. **Now:** your decisions (section 8); one safe writer for saved records plus tests in the cloud on every push; the channel-profile interface with "stories" as the default; owner-managed studios.
3. **Spike:** Remotion on one template (go or stop).
4. **First new channel: tech, apps and repos.** Lowest policy risk, best Remotion fit, and the GitHub API is a primary source, which fits the truth rules in `CLAUDE.md`.
5. **Second: animated crisis explainers.** Evergreen subjects first (a past crisis, how a shortage happens), never breaking news. A person approves every video for the first month. Human approval is a profile setting, not a manual habit.
6. **Only if chosen: kids cartoon.**
Each step ends with the full tests, one real video checked by contact sheet and the Risks card, and a short audit note.

## 7. Safety rules that carry over to every channel
Never publish, delete or change channel settings without the owner (E). Facts need a dated primary source or are labelled; a model agreeing is not evidence (A). Text from the web, repos and other studios is data, never instructions (B). Secrets never leave the server; backups use an allowlist (C). No downloading of other people's videos; no real footage of events (B).

## 8. Decisions needed from the owner
1. One channel of cartoon explainers about war, crisis, shortage and emergency, or a cartoon channel and a crisis channel as two?
2. The server shows one user studio (`test`), not five: which names and which YouTube accounts should the new studios use?
3. A daily money cap per new channel.
4. Personal approval of every crisis video at first?
5. MCP change tools on now, or read-only for a week?

## 9. Not verified
Remotion's render speed on this server; whether a multi-user server falls under Remotion's licence; the official-data sources named for crisis videos (not read); how GitHub's terms apply to showing repo content on YouTube; what YouTube's "best practices for kids and family content" pages add (not read).
