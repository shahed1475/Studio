# My Downloads: save my own videos to the Desktop (2026-10-31)

Owner's request (31 Oct 2026): a Download button in the dashboard. Type or speak what is needed and how many; the videos are saved in a folder on the Desktop. Purpose: the owner's own works, which are sometimes lost. The owner deleted the earlier test download (`raw_videos/movie_explanation.mp4`, another creator's video) first.

## What it is
A small local app, `mydownloads/`, that runs on the owner's PC (not on the VPS) and a **Downloads** tool page in the dashboard that opens it.

Why on the PC: the Desktop folder is on the PC; the browser only allows the microphone on `localhost`/`127.0.0.1` (the dashboard at `http://vps-ai:8913` is not a secure page); YouTube often refuses datacentre addresses. The dashboard cannot reach into the PC, so its page is a button that opens `http://127.0.0.1:8923/`.

## Scope rule (decision, owner can widen it)
Only the owner's own videos. `CLAUDE.md` section B forbids downloading other people's YouTube videos (YouTube's terms), and the owner described the tool as "for my own works". So every video is checked twice against the **list of my channels** (`channels.json`): once when planned, and again from the video's own fresh metadata (`channel_id`) right before it downloads. Anything else is refused with the reason. The studio's channel (`@thesleepinglib`, `UCYeOLFYx2orIghktFlQrV7A`) is seeded from the studio's own upload records; another channel is added only by an explicit "this is my channel" statement, which is logged (a statement, not proof). Widening to other creators' videos would amend rule B and is the owner's separate decision.

## Flow
1. Type or speak: "download my last 5 videos", "all my Shorts", "3 videos about Cambyses", or paste a link.
2. `intent.parse` (fixed rules, no model, no cost) reads count, order, kind, keywords, links.
3. **Find** lists matches (preview, titles and lengths, "already saved" marked). Nothing downloads yet, so a misheard command costs nothing.
4. **Download N videos** starts a queue, one video at a time, progress per video, **Stop** at any time.
5. Files: `~/Desktop/My YouTube Downloads/<channel>/<title> [<id>].mp4`. A video already there is skipped.
6. The queue is written to disk before each video, so after a power cut the page offers **Continue** (partial files resume).

## Parts
- `intent.py` words to a request. `store.py` paths, channels, job file, audit log (all under `$MYDL_HOME`, default `~/.config/studio-mydownloads`). `engine.py` yt-dlp as a library (injectable for tests): list from the uploads playlist (newest first, one list of Videos and Shorts) plus the Shorts tab (to tell them apart), check, download, plain-words errors. `server.py` stdlib HTTP on `127.0.0.1:8923`. `web/` the page (typing box, microphone via the browser's speech recognition, preview, progress).
- Safety on the local server: loopback only; `Host` must be `127.0.0.1:8923` or `localhost:8923` (DNS rebinding); every POST needs the header `X-MyDownloads: 1` (a web page on another site cannot send it without a permission check, which is never granted) and a matching `Origin`; files only under the download folder; the only subprocess is `xdg-open <download folder>`.
- Dashboard: a **Downloads** entry in `TOOLS` (owner's studio only, hidden in user studios), a page with the button and the plain instructions, three icons.
- Auto-start: a systemd user service `studio-mydownloads` so it is back after a power cut.

## Limits (said honestly)
- Private or still-scheduled videos need a login; YouTube Studio's own Download button handles those. The tool says so.
- Titles only are searched (the channel list carries no descriptions or dates).
- The microphone uses the browser's speech recognition; in Chrome that sends the audio to Google's service. Firefox has none, typing works everywhere.
- YouTube changes often; when a download fails the page says to update `yt-dlp` (`.venv/bin/pip install -U yt-dlp`).
- The dashboard button appears on the live dashboard only after the next deploy (not done: this branch carries other unpushed work). The downloader itself works now at `http://127.0.0.1:8923/`.

## Tests (written first)
`tests/test_mydownloads_intent.py`, `_store.py`, `_engine.py` (fake yt-dlp, no network), `_server.py` (real server, fake engine), `_dashboard.py`, `_ui.py` (real Chrome, fake speech). One real download of one of the owner's own public videos was run by hand as the live check.
