# My Downloads: save your own videos to the Desktop

For the owner. Plan and reasons: `docs/superpowers/plans/2026-10-31-my-downloads.md`.

## What it does
You say or type what you need ("my last 5 videos", "all my Shorts", "3 videos about Cambyses", or paste a link). It shows the list first. You press **Download**, and the videos are saved in `Desktop/My YouTube Downloads/<channel>/<title> [<id>].mp4`. A video already in the folder is skipped.

## Use it
1. Dashboard, **Downloads** in the menu, then **Open the downloader** (or open `http://127.0.0.1:8923` on this computer).
2. Type, or press the microphone and speak. After you speak it finds the videos by itself.
3. Look at the list, untick anything you do not want, press **Download N videos**.
4. **Stop** pauses. **Continue** carries on. After a power cut the page offers **Continue** and a half-finished video resumes where it stopped.

The downloader runs on this computer (a background service, back after every restart):
- status `systemctl --user status studio-mydownloads` · stop `systemctl --user stop studio-mydownloads` · off for good `systemctl --user disable --now studio-mydownloads`
- first install, or after moving the project: `mydownloads/install.sh`
- it needs `yt-dlp` and `ffmpeg` (`.venv/bin/pip install -r mydownloads/requirements.txt`).

## Only your own videos
It downloads only from channels on your list (shown under the ask box). The studio's channel (@thesleepinglib) is on it, taken from the studio's own upload records. To add another channel of yours, press **Add another channel**, paste its link or @name and tick "This is my own channel". That tick is your word, logged in `~/.config/studio-mydownloads/channels.json`; the tool cannot check it. A video is checked against the list twice: when it is listed and again, from YouTube's fresh data, right before it downloads. Anything else is refused with the reason.

This follows rule B in `CLAUDE.md` (no downloading other people's YouTube videos; YouTube's terms forbid it). Allowing other creators' videos would change that rule and is your separate decision.

## Limits
- A **private or still-scheduled** video needs your login, so it cannot be fetched this way. The page says so; use YouTube Studio: Content, the three dots, Download.
- Searching words match **titles only**.
- **Voice** uses the browser's speech service (in Chrome the audio goes to Google). Firefox has none: typing works everywhere. Say numbers as digits or words ("five").
- YouTube changes often. If downloads start failing, update the downloader: `.venv/bin/pip install -U yt-dlp`, then `systemctl --user restart studio-mydownloads`.
- The Downloads button only appears in the live dashboard after the next deploy. The downloader itself works without it.
- Files are saved as H.264 + AAC `.mp4` (plays on old phones and players), at the best size YouTube offers in that format.

## Where things are
Settings, your channel list, the saved queue and the log: `~/.config/studio-mydownloads/` (`channels.json`, `job.json`, `downloads.log`). Nothing there is secret and nothing is in the studio's data or on the server.
