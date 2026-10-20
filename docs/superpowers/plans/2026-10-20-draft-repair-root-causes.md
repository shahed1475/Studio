# Why two documentaries stay drafts, and what is fixed (2026-10-20)

Owner's question: the Delphi and Pied Piper documentaries are still drafts ("Needs your eyes"). Why, is Autopilot working, and make it right.

## Evidence (read from the VPS at af682ca, 20 Oct 15:40 UTC)
- Containers healthy, worker ticks every ~30 min with exit 0, no errors in the last tick. Autopilot is on.
- Both drafts are **parked by design** (docs/AUTOPILOT.md): the next documentary slot is Thu 22 Oct 19:00 UTC, so repairs start Wed 21 Oct 07:00 UTC. Delphi takes that slot (it has one repair try), Pied Piper the next (Fri 24 Oct 14:00 UTC, starts Thu 23 Oct 02:00 UTC).
- Delphi, why it would still fail when repairs resume (attempt 1 of 2 is used):
  1. **Leaked headings in the narration**: the voice reads "Chapter 5: The Temples of Apollo" and "Chapter 6 examines the artifacts..." (the writer copied the "Story so far: Chapter n" notes). No review rule catches it and the fixer has no remedy.
  2. **Two wrong pictures** (vision review): a Roman photo (Temple of Apollo Sosianus) at 210 s and a blurry unrelated close-up at 333 s. The fixer's only picture remedy is `art_first`, which is already on, and `art_first` still takes a search hit before drawing, so the same wrong photos came back. A second try would change nothing and waste one of two tries.
  3. The reviewer also says the ending repeats itself (the same museum line 4+ times).
- Pied Piper: last visual reading is from 02:35 UTC (before the newer remedies), 0 repair tries used. Nothing wrong with the flow; it waits.
- Money: $3.95 spent today, $2.66 of it on AI pictures; about $5.3 left. A blanket redraw of 16 scenes costs about $0.55, two scenes cost about $0.07.
- Browser: the dashboard answers at http://100.123.254.63:8913 (the name vps-ai does not resolve in Chrome) and asks for the owner's sign-in. I do not enter the password, so the page-by-page visual check needs the owner to sign in first.

## Fixes (each test-first, one change at a time)
1. `scriptgen.strip_labels`: remove "Chapter N:" style prefixes, drop lines that are only a heading or "Chapter N examines..." and re-map the chapter start lines. Used when a script is written and by the fixer.
2. Reviewer rule `script_labels` (blocks): no narration line may start with a chapter, part or section label.
3. Fixer remedy for `script_labels`: clean the lines and re-render.
4. Targeted picture repair: the vision review records the seconds of each WRONG picture (`visual_check.wrong_at`); the fixer maps them to narration lines with the voice's word timings (`words.json`) and stores those lines in `meta.redraw_lines`; `footage.scene_images` draws an illustration for exactly those scenes (searching is skipped for them, they do not count against the art cap). This runs before the blanket `art_first`, so it is cheaper and does not repeat itself.
5. Seed Delphi's `wrong_at` from its saved vision reading (`data/research/.../analysis.json`), so the new remedy applies to it.

## Done means
- Full test suite passes (quote the count).
- New tests fail before each change and pass after.
- Deployed with `deploy.sh` without restarting the worker while a render runs.
- Delphi: the fixer run produces a script with no label lines, a redrawn picture at the flagged scenes, and a new review; the result is reported as it is, not as hoped.

## Not done / limits
- The vision reading samples 10 frames, so other wrong pictures can exist.
- Repeated narration at the end is only reported by the reviewer; it is not rewritten by this change.
- Browser walk-through of every dashboard page waits for the owner's sign-in.
