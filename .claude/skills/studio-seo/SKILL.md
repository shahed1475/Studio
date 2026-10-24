---
name: studio-seo
description: Use when judging or improving a video's search packaging: title scoring, description first 150 characters, thumbnail text, playlists and the post-publish title test. Matches packaging.py and the reviewer's seo_* warnings.
---

# Search packaging (Story Studio)

What the code already does, so do not repeat it by hand:
- `seo.py` finds the 2 to 4 word search phrase, pulls real YouTube autocomplete, writes 5 titles, the description intro and tags.
- `packaging.py` scores titles (`title_score`, `rank_titles`): phrase inside the first 40 characters, 40 to 62 characters, search words, a proper name, no vague "what do ... actually ...?" question, no shouting, not a near-copy of another title. `autopilot.finish_video` takes the best score.
- `reviewer.metadata_checks` adds warnings `seo_title_front`, `seo_description_150`, `seo_thumbnail_text`, `seo_title_length` (warnings never block).
- `thumbnail.hook_for` prefers text that names the subject and adds a word the title lacks (3 to 5 words, supported by the narration).
- `topicrank.pop_best` ranks topics with `seo.demand` (YouTube autocomplete); `scriptgen.country_ideas` asks for short subject names.
- `compliance.final_description` adds one playlist link from `data/playlists.json` ("cta"); `upload.join_playlists` adds each new upload to the playlists in that file.
- `titletest.py` (daily 08:00 UTC, mode in `data/titletest.json`): a weak video gets one new title; Analytics watch percentage under 25% means the content, not the title, is the problem.

Rules that stay human decisions: channel About, trailer, banner, name (owner approval), public/private state, deleting anything.
Limits: impressions and click rate are only in Studio (the Analytics API refuses them); a score is advice, not proof of more views.
