# YouTube Shorts automation (free, local)

Ollama writes the script, edge-tts reads it in a US-English voice, Pexels supplies footage, ffmpeg renders a 1080x1920 Short with word-timed captions, and the YouTube Data API uploads it.

## Dashboard
```
./start.sh     # opens http://studio.localhost:8913
```
Home shows the next step, Videos plays and approves, Create makes videos and edits the queue, YouTube connects your channel.

## Autopilot (hands-off mode)
Everything runs from the dashboard's **Autopilot** page. It is off until you switch it on.

1. Install the timers once: `./scripts/install-timers.sh` (remove with `--uninstall`). Autopilot then runs every 30 minutes and the YouTube news check runs on Mondays.
2. Each pass: refill topics, make a documentary, add thumbnails and a search-based title, run the **reviewer agent**, schedule passing videos into the next free publish slot, and upload them (private, with a scheduled public time) shortly before that slot.
3. The reviewer blocks a video on bad files (length, size, silent audio, black screens, missing thumbnail), repeated script lines, duplicate titles, or a risky script. Videos with unhedged specific claims (named people, years) and every news video go to **Needs you** instead.
4. **Shorts** (YouTube's vertical reels) run in their own lane: one a day by default, published at US-Eastern times from the research (Tue/Thu 12:30, Fri 16:00, Sat/Sun 13:00). They need a free Pexels key in Settings, otherwise autopilot pauses Shorts.
5. You can **Hold** any video before it uploads. Limits: 1 upload a day by default, never more than 5.

CLI: `run.py review NAME`, `run.py autopilot tick|status`, `run.py newswatch`, `run.py newsvideo`. Tests: `.venv/bin/python -m pytest -q`.

## Run it 24 hours a day on a server (Docker)
The project ships a `Dockerfile` and `docker-compose.yml`: a **dashboard** container and an always-on **worker** container (it replaces the systemd timers: autopilot every 30 minutes, the growth agent at 06:30 UTC, news and trends on Mondays 09:00 UTC, and a daily cache clean-up). Both restart by themselves after a crash or a reboot.

1. Server needs Docker with Compose and an SSH login. Nothing is opened to the internet: both containers listen on `127.0.0.1` only.
2. First time, from this computer: `STUDIO_VPS=user@your.host deploy/deploy.sh first` (clones the repo on the server, copies `.env`, `client_secret.json` and `token.json` over SSH, builds and starts).
3. Later updates: `STUDIO_VPS=user@your.host deploy/deploy.sh`.
4. Open the dashboard from your computer: `STUDIO_VPS=user@your.host deploy/tunnel.sh`, then http://127.0.0.1:8913.
5. Autopilot stays **off** until you switch it on in the dashboard (it publishes to your channel).

Secrets (`.env`, `client_secret.json`, `token.json`, `settings.json`) are listed in `.gitignore` and `.dockerignore`: they never go to GitHub and never into the image. Set your Google OAuth consent screen to "In production" or the YouTube login expires after 7 days.

## Subtitles
- New documentaries get subtitles burned in (white text, black outline, two lines at most). Shorts already have big word-by-word captions. Turn the documentary subtitles off with `YT_DOC_SUBS=0`.
- Every video also gets `captions.srt` and `words.json` in its folder.
- Add subtitles to a finished video without re-voicing it: `run.py subtitles NAME --burn` (or the **Subtitles** panel on the video page). It refuses uploaded videos, and if the regenerated voice timings do not match the video's length it stops and changes nothing.

## AI models (OpenRouter, optional)
Settings, **AI models**: paste an OpenRouter key (it is saved in settings.json, never shown again), pick a model per job, set a daily dollar cap, press **Test it**, then turn it on.
- **Writer** (scripts, news summary), **Fact-checker** (must be a different model from the writer), **Helper** (titles, tags, thumbnail text, ideas).
- Empty model, no key, the cap reached or any OpenRouter error: the local Ollama model is used instead, and the reason is shown on the panel.
- The panel shows today's spend and a cost estimate for this channel from OpenRouter's live prices.

## Daily use
```
.venv/bin/python run.py ideas 10          # fill the topic queue
.venv/bin/python run.py batch 3           # make 3 videos -> output/<name>/video.mp4
.venv/bin/python run.py list
.venv/bin/python run.py approve <name>    # after you watched it
.venv/bin/python run.py upload <name>     # private; add --public or --at 2026-10-20T14:00:00Z
```

## One-time setup
1. Footage (free): get a key at https://www.pexels.com/api/ and `export PEXELS_API_KEY=...`. Without it you get plain colour backgrounds.
2. Upload: in Google Cloud Console create a project, enable "YouTube Data API v3", create an OAuth client of type Desktop app, save it as `client_secret.json` here. The first upload opens a browser to sign in. (Unverified projects upload as private until the project passes Google's audit; request it if you plan to post public videos through the API, or upload manually in YouTube Studio.)

## Monetization notes
YPP needs 1,000 subscribers plus 4,000 watch hours or 10M Shorts views (thresholds are reported to rise Feb 2027). Channels that are automated, repetitive and interchangeable risk being demonetized, so edit niche.json to a real angle, review each video, and add your own insight.
