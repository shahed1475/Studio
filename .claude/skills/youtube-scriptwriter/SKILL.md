---
name: youtube-scriptwriter
description: "Use when writing or revising a documentary or Short script for this channel: grounded in sources, no invented facts or quotations, a strong honest hook, and checked by script rules before voice and rendering."
---

# YouTube scriptwriter

Write from sources, then prove it.

## Workflow
1. Research first (`youtube-research`). Write only from the gathered sources. The pipeline grounds scripts on up to two Wikipedia articles (`wikipedia.facts_multi`).
2. Shorts: 12 to 14 lines, 140 to 180 words, first line 14 words or fewer and a real question. Documentaries: 8 chapters, 6 lines each, 400 words or more, every chapter titled.
3. Plain American English, short sentences. No invented names, dates, numbers, quotations or statistics. Uncertain history gets a hedge ("some historians believe", "legend says").
4. Quote only what a source says, exactly, and name who said it.
5. No loops: no line repeats; opening and ending differ from recent videos.
6. Check: `.venv/bin/python .claude/skills/youtube-scriptwriter/scripts/check_script.py <slug>`. It fails on short scripts, repeated lines, unconfirmed claims and contradicted claims.
7. Fix what it reports, then run the `youtube-fact-check` workflow before rendering.

## Never
Report a script as checked without running the check and quoting its output; present a hedge as a verified fact.
