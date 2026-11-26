# Mary Celeste film: why its pictures repeat (24 Nov 2026, investigation 22:55-23:05 UTC)

Video: `output/doc-the-ghost-ship-the-true-story-of-the-mary-cel/video.mp4` (made 23 Nov 15:57 UTC, 1,181.5 s, 104 scenes). Not approved, review verdict "fail",
not on YouTube. Nothing in its folder was changed or deleted by this investigation. Evidence files (not in git): `data/research/mary-celeste-repeats-24nov/`.

## What was measured
- The record's own count (`footage` in meta.json): 104 scenes, **54 different pictures**, 0 missing, 19 drawn. Build log (logs/mary-celeste-doc.log):
  "only 52 different pictures for 104 scenes: drawing more" - the top-up added 2. 54/104 = 52%, under the studio's own floor (run.MIN_VARIETY 55%).
- One frame from the middle of every scene of the real MP4 (scene times from words.json: scene i = start of line i's voice to start of line i+1's), 104 frames.
  - Looked at all 104 (contact sheets `mc_sheet_0.jpg`, `mc_sheet_1.jpg`): **scenes 52-103 replay scenes 1-51 almost in order** (1/52, 2/53, 3-4/54-55, 5/56, 9/61,
    7/58-59, 10/62, 11/63, 12/64, 13/65, 14/60/66, 20/73, 21/74, 22/75, 23/76, 24/77, 26/78, 27/80, 29/82, 30/83, 31/84, 32/85, 33/86, 34/88, 35/89, 36/90, 37/91,
    38/92, 40/94, 41/95, 42/96, 43/97, 44/98, 45/99, 46/100, 47/101, 48/102, 49/103).
  - Automatic grouping (8x8 dHash of the frame centre above the captions, pairs within 10/64 bits; `mc_repeat_groups.json`): 87 distinct-looking frames, 10 groups covering
    27 scenes. Camera motion (pan/zoom differs per scene) hides many repeats from a hash, so the visual list above is the fuller one.

| Fingerprint | Scenes | Starts (s) | What it is |
|---|---|---|---|
| 0f0f0707070f4d64 | 8, 16, 25, 39, 57, 81, 93 (+26, 79 merged by the hash) | 85, 184, 283, 437, 644, 919, 1052 | Blender "sea" stills: six separate renders that all show an empty sea; 26/79 are two pale pencil sketches the hash confuses with them |
| 39a92f4c229b8e37 | 14, 60 | 157, 679 | NYTimes 26 Feb 1873 clipping (also 66 by eye) |
| 2727773f1b0f0707 | 20, 73 | 227, 830 | 17th-century stone plaque, San Gregorio Armeno, Naples (wrong subject) |
| 1733333232eac8c8 | 21, 74 | 237, 840 | "Victoria Dei Gratia" statue (wrong subject) |
| 06140c9833646744 | 22, 75 | 248, 848 | Rock of Gibraltar sketch (Met) |
| cfc3c343d39ea626 | 23, 76 | 257, 859 | Gibraltar drawing |
| fffffc7e79393737 | 24, 77 | 268, 873 | "The Sortie Made by the Garrison of Gibraltar" (Met) |
| cb67663c3c3a3959 | 32, 85 | 363, 959 | "Sherlock Holmes - The Valley of Fear" |
| f0f9d974e6cf1f1f | 33, 86 | 372, 973 | AI drawing: captain's cabin |
| 4fcf87931b5367e7 | 40, 94 | 444, 1064 | AI drawing: ship at sea |

## Second finding: wrong-subject pictures (seen in the frames, confirmed in `assets`)
Seven scenes show a grey horse (15, 17, 19, 68, 69, 70, 72): Openverse "Mary Celeste - Thoroughbred", "Mary Celeste - Thoroughbred mare", "Mary Celeste" (x2), CC BY 2.0,
a racehorse. Also "Amazing! 132 years later the Mary Celeste crew turn up in a Brighton Gay Bar" (18, 71), "Victoria Dei Gratia" (21, 74, a statue matched on the ship
name Dei Gratia) and a Naples stone plaque (20, 73).

## Causes (code)
1. **Repeats (R1).** `run._produce_doc` waits for tomorrow's free pictures (`_wait_for_pictures`) only for lines in `_forced_art` (a film drawn on purpose). This film was
   not drawn on purpose (real pictures first, `art_style` unset). When the day's free Cloudflare allowance ran out (about 1,758 units were left that afternoon, about 16
   pictures), `aiart.generate` returned None and `footage.scene_images` fell back to its last step, "then reuse", in order: the second half replays the first. The
   variety top-up ("drawing more") could not draw either, and the film was rendered at 52% anyway. Not the cause: duplicate asset ids, a cache collision, the art cap
   (19 drawn of 28 allowed), retries or the renderer (each scene got exactly the picture the picker returned).
2. **Wrong subjects (R2).** `realmedia.Finder` sent only the items whose title did NOT name an anchor to the picture judge; a title that contained "Mary Celeste" or
   "Dei Gratia" was taken without being judged. The Commons path judged titles with categories and did reject e.g. "Rock of Gibraltar - Race Horse.jpg"
   (data/image_judge.json); none of the Openverse titles above was ever judged.
3. Blender: six "sea" scenes are different renders of the same empty-sea look; they read as one repeated picture. Not changed (a design point for blenderscenes).

## Fixes (uncommitted, tested)
- R1: after the top-up, a film still under MIN_VARIETY while today's free pictures are spent stops at the same checkpoint as a drawn film (`_wait_for_pictures`: script kept,
  pictures drawn so far cached, the try not counted) and continues after 00:00 UTC. Only when drawing is set up and the allowance is the reason, so no film waits forever.
  Tests: tests/test_picture_wait.py (+2: waits when spent; renders as before when drawing is still possible). Mutation check: with the floor removed the new test fails
  (the film reaches the renderer).
- R2: every item goes to the judge, named or not; a judge that cannot answer keeps every title (as before). Tests: tests/test_realmedia.py (+1 new, 1 updated with the reason).

## Not done / open
- The film was not re-rendered or redrawn (the owner gave the next free pictures to Seven Sleepers). It stays as it is: not approved, review "fail".
- Its SEO title "Mary Celeste: What Happened to Her Ten Missing Crew?" is wrong (ten people: the captain, his wife, their daughter and seven crew); must change before approval.
- The hash grouping is evidence, not proof: it misses repeats under different camera motion and merged two sketches with the sea stills; the visual list was made by eye
  from one frame per scene, not by watching the whole film.
