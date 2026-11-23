---
name: youtube-scriptwriter
description: "Use when writing or revising a documentary or Short script for this channel: grounded in sources, no invented facts or quotations, a strong honest hook, a real ending, no padding, and checked by the studio's script rules and two judges before voice and pictures."
---

# YouTube scriptwriter

Write from sources, then prove it. The numbers below come from the code; when they disagree, the code wins (`scriptgen.py`).

## Workflow
1. **Sources first** (`youtube-research`). Write only from them. The pipeline reads up to three Wikipedia articles (`scriptgen.source_budget`, about 18,000 characters each for a 20 to 26 minute film); the reviewer checks against the FULL article (`reviewer.source_text`, cached in `cache/wiki/`). When you write by hand, read the full article, not the cut one.
2. **Length is the owner's** (`rules.json` long_min/max_minutes, today 20 to 26 minutes; `scriptgen.doc_budget`): about 148 words a minute, lines of 30 to 44 words (hard limit `LINE_WORDS_MAX`, one picture a line), 10 to 13 titled chapters. Shorts: `scriptgen.short_word_range` and the Short prompt (open who/what/where/why/how hook, a payoff line, "subscribe", never "follow").
3. **Shape** (`scriptgen.DOC_STRUCTURE`, `HOOK_RULE`, `REHOOK_RULE`): line 1 the central question, open and under 20 words; line 2 the promise; a new question or turn every 60 to 90 seconds; every theory labelled with who holds it; one chapter on documented fact versus legend; the closing chapter weighs the evidence with facts already told (no new fact), gives the most reasonable reading, and leaves one question open.
4. **Never pad.** If the sources run out, the film is shorter. A chapter that retells another, a person named without an introduction ("Cobb suggested"), or a fact added after the ending are defects (23 Nov 2026: the Mary Celeste draft had all three; `scriptgen.growable` now keeps the hook and closing chapters from being extended, `split_long_lines` cuts long lines at whole sentences).
5. Plain American English. No invented names, dates, numbers, quotations or statistics; your own arithmetic ("150 years") is not a source fact. Quote only what a source says, exactly, and name who said it.
6. **Check before any voice or picture**: `scriptreview.rows` (free rules: labels, speakable text, quotations against the source, hook, ending, repeats) and `scriptgen.unsupported` (two judges of different families). Or, for a saved video: `.venv/bin/python .claude/skills/youtube-scriptwriter/scripts/check_script.py <slug>`.
7. **When a judge flags many correct lines** and cites a "cutoff" (a free model can lose the middle of a long source), ask the judges again about the flagged lines only, against the source sections they come from, and confirm each remaining flag by an exact passage. Never wave a flag away without a passage.
8. A script written in a Claude session is recorded as such (`script_model`, `script_writers`, `script_rewrite`): it stays out of the training set (`trainset.py`).

## Never
Report a script as checked without running the checks and quoting their output; present a hedge or a theory as a verified fact; lengthen a film by retelling.
