# Autopilot Short production (21 Nov 2026)

Both Shorts were made and repaired by the Studio's own commands (`run.py autopilot make short` = Autopilot's make step + reviewer; `run.py repair` = the fixer under Autopilot's lock). Nothing approved, scheduled or uploaded.

## 1. "Tenali Rama Stories: Who Was the Real Scholar?" (`output/the-true-story-of-tenali-rama`, made 20 Nov)
| Step | Result |
|---|---|
| Open issue from 20 Nov | review `needs_human`: line 9 said dedications "prove" what the source says they "suggest" |
| Repair 1 | fixer said "rewrote 1 line", re-rendered, reviewer flagged the same line again. **Bug**: the free writer rewrote line 3 instead; any edit was accepted and counted |
| Fix | only flagged lines may be edited; a flagged line still over-certain is softened by rule; only real fixes counted (tests + 2 mutation checks) |
| Repair 2 | line 9 now "Yet textual dedications suggest he served later ruler Venkatapati Raya."; **verdict pass**, `approved: false`, no video id |
| File | 57.3 s, 1080x1920, 30 fps, H.264/AAC, 0 decode errors, -14.0 LUFS; hand-overs script/voice/visuals/render all passed |
| Looked at | frames at 3 s (hook question on screen), 25 s, 50 s (caption "SUGGEST HE", the corrected word). The picture under line 9 is a stylised bird drawing that does not show its subject: a picture-relevance point for the owner |
| Blender | none, correctly: the source has no coordinates and no line names a place a template can show truthfully |

## 2. New Short: "Raijin and Fujin: Storm Brothers of Japanese Myth" (`output/raijin-and-fujin-the-storm-gods`)
| Step | Result |
|---|---|
| Topic | "Raijin and Fujin, the Storm Gods", from the Studio's own queue (topicrank) |
| Script | free model `nvidia/nemotron-3.5-super-vl:free`; judged by different free models |
| Pictures | 10 different archive pictures, 0 drawn; one download broke mid-way (network) and was skipped safely |
| First review | **fail**: `title_matches` (the opening's "Japan's oldest temple gate" is not supported), `variety_script` (ending like a recent video). Not flagged but seen by the engineer: line 8 narrated our prompt's own word: "The payoff: ..." |
| Fix (code) | story-shape words ("The payoff:", "Hook:", ...) now count as narrated labels, cut mechanically and blocked by the reviewer (test) |
| Repair 1 | new honest title and description, ending varied; reviewer then blocked the narrated label |
| Repair 2 | label cut ("They are twin storm gods enshrined side by side in Japan."); still **fail**: `title_matches` (block) on the unsupported "oldest temple gate" opening; invented-facts watch 4/10 |
| Bug found | the varied ending cut the topic mid-name ("... Raijin and Fujin, the Storm. More on our channel.") and dropped "subscribe": fixed in `clipper.closing_subject` and the closings (test). This Short still carries the old ending until it is re-voiced |
| State | held, `approved: false`, 2 repair tries used. Owner's choice: `python run.py repair raijin-and-fujin-the-storm-gods --extra` (re-voices with the fixed ending; the "oldest temple gate" opening still needs a rewrite) or set it aside |

## Recovery on Shorts
Both Shorts went through the Short checkpoint path (`work/checkpoint.json`, `data/pending_short.json`) and the new Short hand-overs. No cut happened during them; the cut behaviour is covered by tests and the recovery drill.
