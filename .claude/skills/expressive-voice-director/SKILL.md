---
name: expressive-voice-director
description: "Use before narrating a script: reads the whole script, marks the emotional arc and gives every line an emotion, intensity, pace, pauses, emphasis and (rarely) a vocal event, as structured line-level delivery notes. Restrained documentary acting, never overacting."
---

# Expressive voice director

## Responsibility
Turn a finished, fact-checked script into delivery notes. It never changes the words, the facts or the order of lines.

## Input and output
- Input: the script lines in order (for a studio video: the `lines` list of `data/pending_doc.json` or `meta.json`), the chapter titles, the subject.
- Output: one object per line in the shared format of [references/delivery-schema.md](references/delivery-schema.md), saved beside the video as `delivery.json` only after the owner asks for it.

## Steps
1. Read the WHOLE script once before marking any line: find the central question, the turns, the saddest moment, the biggest surprise and the ending.
2. Mark chapters first (one mood per chapter), then lines inside them. Most lines stay at the chapter's mood with intensity 0.2 to 0.4.
3. Give a line its own emotion only when its MEANING changes: a discovery (surprise), a loss (sadness, empathy), a threat (suspense), a theory (curiosity), a conclusion (reflective).
4. A paragraph is not one emotion: a sad sentence inside a curious chapter is marked on that sentence only.
5. Pauses: longer after a fact that should land (0.6 to 1.0 s), short between ordinary lines (0.2 to 0.4 s).
6. Vocal events: at most one per few minutes, only when the text itself is light (an absurd legend, a hoax). Never on a death, a disappearance or a family's loss.
7. Pronunciation: list every name the voice may get wrong, with a respelling of one word (the studio's rule in `tts.py`, `PRONUNCIATION`).

## Quality criteria
- Each chapter has a clear mood; emotion changes follow the meaning, not punctuation.
- No more than about one line in ten above intensity 0.6.
- A tragic event is serious and respectful; a surprising discovery sounds surprised; a hoax may be lightly amused.

## Failure handling
A line whose meaning is unclear stays `neutral`, intensity 0.3, and is listed for the owner. Never guess a laugh.

## Example
- "Why did ten people abandon the Mary Celeste...?" curiosity 0.5, moderate, pause_after 0.8, emphasis ["abandon"].
- "None of those who had been on board were ever seen or heard from again." sadness 0.4, slow, pause_after 1.0.
- "...and put live chickens aboard." curiosity 0.3 with a light chuckle allowed (a magazine's invention), never a laugh.
- "Parker died in poverty three months later." serious 0.4, no event.
