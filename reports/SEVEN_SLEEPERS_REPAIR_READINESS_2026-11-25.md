# Seven Sleepers: repair readiness (25 Nov 2026), NOT READY to execute; nothing drawn or rendered

## Verified state (today)
- **Film:** `output/doc-did-seven-sleepers-hide-in-a-cave-and-awaken-/video.mp4`, sha256 `d885501e6a77deac…`, identical to the backup in `output_old/doc-did-seven-sleepers-v2-d885501e-before-repair-25nov/`. The record says hold true, approved false.
- **No `scenes.json` in the film folder yet:** it is written at the next render. The reconstructed mapping is in `data/rescript/scene_map_v2/`.
- **Spending since the render:** the Cloudflare count for today is still 4,376.4 Neurons (the 00:02 render's 42 drawings). No drawing, render, approval, upload or schedule has happened since.

## 1. The `scenes.json` safeguard: what it does and does not do (VERIFIED by reading `scenemanifest.py`, `footage.py`, `run.py`, `reviewer.py` and running the tests)
| Question | Answer |
|---|---|
| Written atomically? | Yes: `.tmp` then `os.replace`. The previous file is kept as `scenes.prev.json`. |
| Records source image, type, query, fallback, scene id, line, hash? | Scene id (from the narration text), index, the narration's first 160 characters, the visual note, `how` (forced_named, forced_drawn, line_search, art_first, **reserve**, drawn, **reuse**, missing, then real_footage, blender or animated when a later step replaced it), the query, the file path, its SHA-256, and what a later step replaced. **Not recorded per scene:** credit or licence (still only in the record's credit list) and the scene's duration. |
| Tells drawn, real, Blender and reused apart? | Yes, through `how` and the stage that replaced it. A `line_search` hit may be a Commons file or a library item; the path tells which (`cache/` or `cache/real/`). |
| Detects assignment changes after script edits? | Yes, when a previous `scenes.json` exists: `changed` (same line, other picture), `stale` (revised line, old picture), `moved`, new and removed lines. |
| Detects missing or stale files? | Stale: yes (diff). **Missing: no.** A missing file gets `sha256: null`, and `check()` does not flag it (at render time a missing picture fails earlier; INFERENCE). |
| Can the reviewer see fallback use? | Yes: `scene_sources` names reserve scenes and runs of 3 or more. |
| Fails closed when provenance is missing? | **No.** A film without a manifest gets no row, and a manifest that failed to write gives a **warning**. With Autopilot's auto-approve on, a warning does not stop approval. |
| Can it rebuild an old film's provenance? | No. That was done once for this film by frame matching (`data/rescript/ss_scene_map.py`: 103 of 109 HIGH, 6 by record). |
| Are the tests meaningful and independent? | 12 unit tests reproduce the root cause with the real `footage.scene_images` (only the Commons search is faked); an agenteval case with 3 mutation checks proves they fail when the rule breaks. **Limits:** the same author wrote code and tests, and there is no end-to-end test through `run._produce_doc`. |

**What it prevents:** losing which picture each scene got; silent reassignment after edits; reserve runs going unnoticed.

**What it does not prevent:**
- a reserve picture being chosen at all;
- a `line_search` picture that names the subject but not the line;
- a film with such pictures being auto-approved (warn severity).

**Proposals** (NEED APPROVAL, they change Autopilot behaviour):
- make `scene_sources` severity `human` for documentaries with a reserve run, a missing or errored manifest, or a missing file;
- add per-scene credit and licence;
- add an end-to-end test.

## 2. Repair plan review (manifest `reports/SEVEN_SLEEPERS_SCENE_MANIFEST_2026-11-25.md`; corrections today)
| Scene | Plan said | Checked today | Now |
|---|---|---|---|
| 31 (stone coffin, Marseille) | NEEDS_HUMAN_REVIEW | The photo's own Flickr page: "Stone Coffins", description **"St Mary's Abbey, York"**, CC BY 2.0. It is in England, not Marseille. | **REPLACE**: a verified photo of the Saint-Victor sarcophagi, or a drawn stone coffin in an abbey crypt with **no writing** |
| 50 (Golden Legend dates) | NEEDS_HUMAN_REVIEW | Source drawing seen at 960 px: an open book covered in letter-like pseudo-writing | **REDRAW**: a closed book, or pages too distant to read, NO writing |
| 65 (sarcophagi inside the Amman cave) | NEEDS_HUMAN_REVIEW (move the CC0 interior photo only if placed at Amman) | Commons record: "inside cave of seven sleepers", category "Images from Wiki Loves Earth 2024 in **Jordan**", CC0, no GPS. Jordan is established; ar-Rajib near Amman is an INFERENCE (the well-known Jordanian site). | stays **NEEDS_HUMAN_REVIEW** (owner decides) |
| 68 (move the real wall photo) | MOVE | Commons category **Amman**, CC0 | unchanged; must not be presented as the Kufic inscription |
| 34 (move the "Surah al-Kahf 18" roundel) | MOVE | Commons: PD (uploader's release), category Al-Kahf, text "سورة الكهف" with 18 | unchanged; the PD claim is the uploader's |
| 38 (Tropenmuseum Qur'an page) | MOVE after a second reader | not re-read | still needs a second reader of Q 18:1–2 |

- **Licences of every moved file** (PD, CC0, CC BY-SA 3.0 and 4.0) are on the owner's list. Their credits must move into the description with the new route.
- **Repetition after the moves:** Russian icons at 3, 8, 9, 32 and 33 (five different files) and Amman photos at 61, 63, (65), 66 and 68 (all different files).
- **Optional new pictures:** 46, 56, 81, 91, 105 and 106 are low priority and could be skipped to save Neurons.

**Budget, updated** (FLUX.2 klein 4B, 104.2 Neurons per 1024x576, price page read 25 Nov):
- **Drawings:** 44 at most (42 + scenes 31 and 50).
- **Neurons:** about **4,585** if each works first time, about **7,398** with two tries for text-prone scenes, and about **6,356** for high priority only.
- **Caution:** the account is shared with FreeLLMAPI text models, so read the real figure in the Cloudflare dashboard first.
- **Cost:** no paid fallback (`aiart.paid_enabled` False, `free_only` True, checked 25 Nov).

## 3. Two-family picture review (design; BLOCKED until built and both families answer)
- **Input per scene:** the exact narration line, the visual note, one frame from the middle of the scene at 960x540, and the scene's `scenes.json` entry (how and source). The two judges never see each other's answer.
- **Judges:** two genuinely different families, chosen from the studio's free cascade with vision support. For example, a Gemini model through the owner's FreeLLMAPI or Google AI Studio free tier, and a Qwen-VL or Llama-4 vision model through OpenRouter free. Which free vision models answer today is **UNVERIFIED**. The writer of a picture is never its judge.
- **Structured answer, per judge:**
  - `illustrates_line` (yes / partly / no);
  - `historical_fit`;
  - `religious_context_ok`;
  - `invented_text` (none / small / large / presented-as-sacred);
  - `misleading`;
  - `real_person_depicted`;
  - `near_duplicate_of` (scene numbers, given the sheet of all frames);
  - `needs_human`;
  - `confidence` (0–1);
  - `evidence` (one sentence);
  - `model` (id and version);
  - `family`.
- **Aggregation:**
  - the stricter answer counts;
  - disagreement is kept, never averaged away;
  - **one family missing, or any request that failed, means BLOCKED** for that scene, never a pass;
  - a text-only review never counts as a picture review.
- **Cost and Neurons:**
  - about 109 scenes x 2 judges, batched 4 scenes per request, about 56 free requests;
  - Neurons are spent only if the FreeLLMAPI route runs on Cloudflare, so the Cloudflare route is used for judging only **after** the drawings, or not at all on a drawing day.
- **Tests (when built):** a scene with fake Arabic is flagged; a mismatched icon is flagged; one family down gives BLOCKED; a failed request is never a pass; a mutation check of the aggregation.

## 4. Proposed documentary fallback rule (NEEDS APPROVAL before any change)
For a documentary scene, in this order:
1. **A real picture that fits the line:** its own search, where the picture's title, description or categories share a distinctive word with the line's visual note or text (not only the film's subject or anchors). Licence on the owner's list; provenance recorded.
2. **Otherwise a new drawing** of the line, with no writing, no fake manuscripts and no inscriptions, under the art limit and the free Neuron budget.
3. **Never** the general subject pool just because a search returned something. The pool may be offered to the owner as suggestions, not placed automatically.
4. **If neither is possible** (budget spent): the film waits for the next free day, as `_wait_for_pictures` already does, rather than reusing or guessing.
5. **Every scene's choice goes into `scenes.json`.** A documentary with any reserve or reused scene goes to the owner, not to auto-approve.

**Consequences:**
- more drawings per documentary (this film: about 46 more), so more Neurons and longer drawing days;
- fewer real archive pictures in films whose lines are specific;
- Shorts are not affected unless chosen.

This changes the owner's 10 Nov rule "real pictures first, drawn only where nothing real fits" by tightening what "fits" means.

## 5. Readiness verdict
**NOT READY.** Needed first, each with its own approval:
1. the scene plan, with today's corrections (31 REPLACE, 50 REDRAW, 65 owner's call);
2. the budget, after a dashboard check;
3. two small, opt-in code changes (ending hold and fade; library asset records kept on the exact-picture route), with tests;
4. the two-family picture review built and both families answering;
5. a second reader for the Tropenmuseum page (scene 38).

Rendering, drawing, approval, upload and scheduling are all out of scope until then.
