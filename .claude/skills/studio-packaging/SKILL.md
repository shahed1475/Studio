---
name: studio-packaging
description: "Use when writing or judging a video's title, description, tags, thumbnail text or opening hook for this channel. Honest high-click packaging rules adapted from the open YouTube marketing skills, matched to the studio's reviewer checks."
---

# Packaging: title, description, hook, thumbnail

The packaging earns the click; the first seconds earn the watch time. Both must be honest, because the story has to keep the promise.

## Title
- Under 70 characters, ideally 40 to 60. The words that decide the click come before any colon.
- Make a promise the first 30 seconds can keep: curiosity plus one concrete noun ("What Lurked Beneath Knossos?"). Questions and "what we know" angles suit uncertain history.
- One search phrase, once, naturally. No keyword stuffing, no ALL CAPS, no emoji, no "you won't believe". Never promise a definite answer to an open question (the reviewer blocks titles that mislead).
- Must not be near-identical to another video's title (the reviewer blocks at 85% similarity; the fixer picks a distinct one).
- Capitalised like a title (`seo.polish_title`). Offer 3 variants from at least 2 different formulas (curiosity, number, versus, mistake).

## Description
- First 150 characters carry the hook and the main phrase: they are all that shows before "Show more".
- Then 2 sentences of what the video covers (only facts the narration supports), chapters starting at 0:00 with real names (never "Part 3"), sources with the Wikipedia link, image credits, hashtags (at most 15 in all), and the AI-narration line.
- Credits must not contain words that would trip content filters; shorten file names if they do.

## Hook
- Shorts: first line 12 words or fewer, raises a question, no greeting. Documentary: restate the question and raise the stakes, or open on the most striking true moment, then the promise.
- Never open with a claim the story does not support.

## Thumbnail (documentaries)
- Text of 4 words or fewer that the title does not repeat; high contrast; one clear subject; readable at phone size. Three options are made by `thumbnail.make`.

## Tags
- Only phrases whose every word appears in the video's own title, topic, description or script, or is a plain niche word (`seo.relevant_tags`). Drop anything about games, novels, songs or TV shows.

## Checks
Run `.venv/bin/python run.py review <slug>` after changes; packaging problems show as `title`, `duplicate_title`, `title_matches`, `description`, `chapters`, `tags`, `hashtags`, `title_style`.
