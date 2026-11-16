# Learning video length and chapter pace from reference channels (17 Nov 2026)

**Owner's order:** Autopilot should check competitor channels and take knowledge about editing and video duration from every video.

## What it does
`craftlearn.py`, called from the daily reference-channel scan (`channelwatch.run`), reads data the YouTube Data API already returns for the 50 newest videos of each reference channel: length, views, publish date and the chapter timestamps in the description. No extra quota.
- A video **outperforms** when its views per day (age 7 to 365 days) are at least 1.5 times the median of its own channel and format, so a huge channel does not drown a small one. Shorts (60 s or less) and long videos (4 to 60 min) are judged apart.
- It writes `data/channels/craft.json`: the length band of outperformers (quartiles), how many have chapters, chapters per 10 minutes, seconds per chapter, and a plain comparison with the studio's own target.
- It reports a band only with at least 8 outperformers. It never changes a rule or the 8 to 10 minute documentary target: those stay the owner's choice. Tests: `tests/test_craftlearn.py`.

## Limits
- Cuts, music, captions and picture style are **not measured**: that would mean watching or downloading other people's videos, which rule B forbids. A person can study those by hand in the browser.
- Views per day is a rough yardstick (age, thumbnails and the channel's size all move it). The first real numbers appear after the next scan.

## Same day: weekly pace and the dashboard
- Weekly target set to exactly 3 documentaries and 7 Shorts (`governor.base`, `max_videos_per_week` 10, documentary slots Tue 18:00, Thu 15:00, Sat 10:00 US Eastern). The governor can still cut it for repeated openings, as designed.
- The dashboard video page shows "Open on YouTube" when `video.mp4` is not on this computer (30 uploaded videos lost theirs with the deleted VPS) instead of a player pointing at nothing.
