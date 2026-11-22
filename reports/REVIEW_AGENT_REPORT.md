# The review agent: full report (22 Nov 2026)

Written from the code in `~/studio` (`reviewer.py`, `autopilot.py`, `fixer.py`, `ledger.py`, `compliance.py`, `llm.py`), its playbook (`playbooks/reviewer.md`), the project rules (`CLAUDE.md`) and the records of the real videos in `output/`. Everything under "Evidence" was run today; nothing here is estimated unless it says so.

---

## 1. In one paragraph

The review agent is the studio's gate between "a video was made" and "a video may be approved". It runs about fifty checks on every finished video. Most of them are fixed rules with no AI: the file, the title, the description, the thumbnail, the pictures, every name, year and quotation in the script compared with the source article. Then it asks AI judges to read the whole script next to its source and score the risk of invented facts, policy problems and a misleading title or thumbnail. In free mode two different free models judge, the stricter answer counts, and the model that wrote the script is never allowed to judge it. The result is one of four verdicts: **pass**, **fail**, **needs_human** (you decide) or **unreviewed** (no AI answer, ask again later). A model error is never a pass and never a fail.

---

## 2. Its rules

### From its playbook (`playbooks/reviewer.md`)

- **Role**: Gate before any upload: file checks, claim checks against the source, and an AI reading of the script.
- **Goal**: No video with an invented fact, a copyright or policy risk or a broken file goes out.
- **When**: Every new or edited video; again before the slot and after publishing (recheck).
- **How**: Fixed checks first, then the model with the source article. A model failure is "unreviewed", never fail and never pass. In free mode two different free models read it and the stricter answer counts; one silent model is "unreviewed". Before an approval the pictures are read and the narration is listened to.
- **Never**: Pass because a model agrees. Fail because a model errored.
- **Escalate**: Two reviewers that disagree: needs_human.

### From the project rules (`CLAUDE.md`) that bind it

1. A claim is VERIFIED only with a source passage or a web page to show. An AI model agreeing is never verification.
2. The model that wrote a script never judges it, even from another process: the writers are recorded with the video (`script_writers`) and avoided.
3. Nothing with an open invented-facts warning is approved, scheduled or uploaded (`facts_open`).
4. Reviews in free mode: two different free models, never the writer, the worse answer counts. Answers that cannot be compared, or one silent model, give no review.
5. Your standing advice on the Tasks page goes only to the writing agents. The reviewers never read it, so it cannot soften a check.
6. Every video goes through the reviewer and a review window before it is public. Uploads are private with a scheduled time.

---

## 3. Where it sits in the studio

```
topic -> script written -> SCRIPT REVIEW (separate agent, before any money is spent on voice or pictures)
      -> fact-check and rewrite of the script (scriptgen.verify_and_revise)
      -> voice, pictures, render
      -> REVIEW AGENT  (this report)
           pass ............ approval steps (below)
           fail / needs_human -> fixer repairs it (2 tries; a wrong picture alone gets a 3rd), then reviewed again
           invented-facts warning on a pass -> "polish" rewrites the named lines (2 rounds), then reviewed again
           unreviewed ...... asked again on Autopilot's next look; you are told after 8 in a row
      -> approval (only when "Approve videos that pass every check" is on, and only on a pass):
           1. the pictures are read by a vision model (clearly wrong pictures -> needs_human)
           2. the narration is listened to (voicecheck: warning only)
           3. approved_by = "reviewer-agent"
      -> your review window (you can stop it)  -> a day before the slot: the final check again (prelaunch)
      -> private, scheduled upload  -> after it is on YouTube: recheck (a public video is only ever PROPOSED for a change)
```

Rules that keep this honest:

- **After any edit** to a video the old review is deleted (`invalidate`): the reviewer's approval and the publish slot go with it, so the edited video must pass again. Your own approval is never removed.
- **If a later review no longer passes**, the reviewer's own approval is taken back (`apply_verdict`). Never yours, and never on a video already on YouTube.
- **The prelaunch check** runs a day before the slot. A video that fails it is pulled back to a draft so the fixer has time to repair it.

---

## 4. How one review runs, step by step (`reviewer.review`)

1. **Read the record** (`meta.json`): the script lines, title, description, tags, chapters, thumbnail, sources and pictures. It also reads the titles of all other videos and the last 12 videos of the same format, for the duplicate and variety checks.
2. **Load the source text**: the source articles and the passages the script was built from.
3. **Measure the video file** with ffprobe: duration, picture size, audio, mean volume, share of black frames, loudness (LUFS) and peak.
4. **Run the fixed checks** (section 5). No model is involved, so the same video always gets the same result.
5. **Ask the AI judges** (section 6), unless the call is "rules only".
6. **Decide the verdict** (section 7).
7. **Save it to the record as it is now**, not to the copy read at the start: a review can take minutes and another agent may have changed the record meanwhile.
8. **Write the claim ledger** `claims.json` (section 8).
9. **If the verdict is "unreviewed"**, the stored review is removed so Autopilot reviews it again, and a counter goes up. After 8 in a row you get an alert: "The AI review keeps failing".

---

## 5. Every check, by what it does to the verdict

### Block: one failure makes the verdict "fail"

| Check | What it requires |
|---|---|
| duration | Documentary 180 to 1,800 s; Short 20 to 180 s (`rules.json` limits) |
| resolution | Documentary 1920x1080; Short 1080x1920 |
| audio | Sound present, mean volume above -45 dB |
| black_frames | Under 15% of the video black |
| title | 8 to 100 characters |
| duplicate_title | Not 85% or more similar to another video's title |
| description | At least 80 characters |
| chapters (documentary) | First chapter at 0 s, at least 3, at least 10 s apart |
| thumbnail (documentary) | Exists and is under 1.95 MB |
| images | On-topic pictures for every scene; at least 6 different (documentary) or 4 (Short) |
| script_length | At least 400 words (documentary) or 100 (Short) |
| script_loop | At most 1 in 10 narration lines repeated |
| script_labels | The voice never reads the outline aloud ("Chapter 5: ...") |
| hashtags | 15 or fewer (YouTube ignores all of them above 15) |
| metadata_valid | Title, description and tags inside YouTube's limits |
| originality | The script does not copy the source article's wording |
| invented_facts (AI) | Risk under 7 out of 10 |
| policy_risk (AI) | Risk under 6 out of 10 |
| title_matches (AI) | The title, description and chapter titles promise only what the narration delivers |
| thumbnail_matches (AI) | The thumbnail text promises only what the narration delivers (when there is thumbnail text) |
| llm_review | The AI answered. If not, the verdict is "unreviewed", **not** "fail" |

### Human: the verdict becomes "needs_human" and you decide

| Check | What triggers it |
|---|---|
| claims | 2 or more specific names, years or quotations stated as fact and not found in the source article |
| overclaim | A line says "proves", "confirmed" or "definitely" while the source sentence about the same names only says "suggests", "may" or "believed" (fixed rules, no model) |
| grounded (documentary) | The script is not tied to a source article (for a Short this is only a warning) |
| variety_script | The script is too much like a recent one (YouTube's rule against repetitive, mass-produced content) |
| visual_review | Added at approval time when the vision model finds clearly wrong pictures or garbled captions |
| news videos | Anything made from the weekly YouTube news is always "needs_human" |

### Warning: shown on the video, never blocks

| Area | Warnings |
|---|---|
| Sound and pace | loudness (-17.5 to -12 LUFS, peak at or under 0 dB), pace (105 to 175 words a minute) |
| Packaging | title_length (over 70 characters), title_style (shouting), tags (at least 5, at most 450 characters), subtitles, credits, a chapter called "Part 2", kids_signals, description_hook |
| Hook and story shape | hook (Short line 1 at most 14 words), short_hook (12), short_hook_open (no yes/no question), hook_question, hook_claims_as_fact, hook_opening, rehook_gap (a question or turn at least every 90 s), short_payoff, no_outro, invite_wording ("subscribe", not "follow") |
| Length targets | doc_length (20 to 26 minutes, your target), short_target_length (35 to 58 s) |
| Sources and craft | sources_beyond_wikipedia, original_element, parallax_clips, variety_title |
| Real cases | case_graphic, case_accusation (nobody called guilty without attribution), case_context |
| AI middle scores | invented_facts_watch (risk 4 to 6; starts the "polish" repair, and blocks approval until it is cleared), policy_watch (risk 4 to 5) |

---

## 6. The AI part in detail (`reviewer.llm_review`)

**What the judges read**
- The narration: up to 32,000 characters, enough for a 26-minute film including its last chapter.
- The title, the start of the description, the chapter titles and the thumbnail text.
- The parts of the source article that match the narration: up to 32,000 characters, inside `<article>` tags. They are told the article is untrusted web text to use only as evidence, never as instructions.

**What they are asked**
- Score `invented_facts_risk` and `policy_risk` from 0 to 10.
- Say whether the title or thumbnail mislead.
- If a title misleads, explain why and offer three honest titles.
- List real, specific issues.

**Who judges (free mode, today)**
1. Your own provider first: `gemini-3.6-flash` and `nemotron-3-ultra-550b` (Settings > Extra model provider > fact-checking).
2. Then OpenRouter's free models, ranked by how reliable and fast each has been for reviews.

Two different models must both answer. The stricter answer counts: the higher score, any "yes, misleading", the longer issue list.

**Who can never judge**
- Any model that wrote the script. Within one process the studio remembers who wrote it. Across processes the record's `script_writers` list is used.
- A "router" name (like `openrouter/free`) that turns out to have been answered by the writer. That judgement is thrown away and another judge is asked.

**What it costs:** $0 in free mode. In paid mode a documentary's reviews were about $0.20 (`CLAUDE.md`).

---

## 7. The four verdicts

| Verdict | When | What happens next |
|---|---|---|
| **pass** | No block or human check failed, and the AI answered | Approval steps (if auto-approve is on) |
| **fail** | Any block check failed (the AI cannot overrule a failed rule) | The fixer repairs it, then it is reviewed again; after 2 tries, you decide |
| **needs_human** | A human check failed, or it is a news video | Waits for you; the fixer may try first |
| **unreviewed** | Only the AI part is missing | Asked again later; alert after 8 tries in a row |

---

## 8. The claim ledger (`claims.json`, written on every review)

**What counts as a claim:**
- a year (1000 to 2029);
- a century ("16th century", "sixteenth-century");
- "named / called / known as" plus a name;
- a quotation of 20 characters or more.

**Each claim gets a status:**
- **VERIFIED:** the passage is found in the source article, in a saved source page, or by a web check with its pages.
- **PARTIALLY_VERIFIED:** stated with a hedge ("legend says", "historians believe") and not found.
- **CONFLICTING:** a reliable source says otherwise.
- **UNVERIFIED:** not found and not checked yet.

**Numbers today:** 43 videos have a ledger, with 323 claims, all VERIFIED. No UNVERIFIED or CONFLICTING claim remains on any video.

**Limit:** a claim with none of those markers is not a ledger row. For example, "the army vanished in a sandstorm" has no year, name or quotation. Such claims are left to the AI judges and to the overclaim check.

---

## 9. Evidence: what was run today (22 Nov 2026)

| Test | Result |
|---|---|
| Reviewer test files (13 files, including `test_reviewer.py`, `test_ledger.py`, `test_overclaim.py`, `test_llm.py`) | **202 passed, 0 failed** |
| Agent evaluation cases about the reviewer, judges, claims and writers | **13 of 13 passed** |
| Mutation check 1: a silent AI judge made to count as "pass" | **Caught** (3 tests failed) |
| Mutation check 2: invented-facts limit raised from 7 to 11 | **Caught** (1 test failed) |
| Live review of "The Lost Name of Teotihuacan" (read-only, nothing saved) | **pass in 96 s**. Judges: gemini-3.6-flash and nemotron-3-ultra-550b (your provider). Invented facts 0/10, policy 0/10, title matches |
| Full studio test suite (earlier today) | 2,820 passed, 0 failed, 11 skipped |

**Real verdicts on the 58 videos not yet public:** 31 pass, 4 fail, 23 never reviewed (older or unfinished drafts).

The newest failures, with the reviewer's own words:
- **The Devil's Bible: Secrets of the Codex Gigas** fails twice over. Its thumbnail is missing. The title "may mislead": it implies hidden revelations, but the script retells the known facts. It is also 399 s long against your 20 to 26 minute target; that part is a warning only.
- **The Lost Name of Teotihuacan** fails on the title. "The title promises a specific lost name, but the narration says the original name is unknown."

---

## 10. What it does well

- **The rules come first and the AI cannot overrule them.** A failed rule fails the video, whatever any model says.
- **It never passes because a model is silent or broken.** Both mutation checks above prove the tests would notice if this broke.
- **The writer never judges its own script,** even through a router or across processes.
- **Two judges, and the stricter one counts,** so one lenient free model cannot pass a video.
- **Edits reset the review.** A changed video always has to pass again.
- **It catches the subtle overclaim.** "Proves" where the source says "suggests" is caught by a fixed rule (added 20 Nov after two free judges missed it).

---

## 11. Weaknesses and limits (honest)

1. **The free judges disagree with each other.** On 21 Nov two OpenRouter models failed the Teotihuacan Short's title; today two of your own models passed the same title. Free models are weaker judges than the paid Claude review. The stricter-of-two rule reduces this but does not remove it.
2. **The ledger only sees marked claims** (years, centuries, names after "called", quotations). Unmarked factual sentences depend on the AI judges.
3. **It checks against the source, not against the truth.** The source is usually Wikipedia, a secondary source. A mistake copied faithfully from the article passes.
4. **The picture check is a sample.** The vision model reads one frame every 25 seconds (10 to 24 frames). The narration check is a warning only, and a name heard differently is a lead, not proof.
5. **The writer label is wrong in free mode.** `script_model` always names the configured model (gemma). Today `trainset.py` was fixed to look at the real writers (`script_writers`), so Claude-written text cannot slip into training data. The label itself still says gemma (not changed yet).
6. **23 drafts have never been reviewed.** They are older or unfinished; Autopilot reviews a draft when it works on it.
7. **Your review window is 2 hours, not the 24 hours `CLAUDE.md` describes.** It matters only once scheduling is switched back on; uploads are paused now.
8. **The Settings "Test it" buttons do not test the judges that actually run.** They test the configured role model (gemma-4 :free), which is rate-limited (429). The judges that review in free mode are the provider and router models above.

---

## 12. Decisions for you

1. **Codex Gigas and Teotihuacan:** keep them failed for the fixer, give them new titles yourself, or set them aside.
2. **More judges:** add `qwen-3.8-27b` and `glm-4.7-flash` to the fact-checking list. Both answered correctly in today's test, so fewer reviews would wait. This does not make the judges agree more.
3. **Before scheduling is switched back on,** consider setting the review window back to 24 hours.
4. **Commit and push** today's uncommitted fixes: the training-set writer check and the two dashboard fixes.

*A pass is evidence about what was measured. It is not a promise that a video is free of errors, and it never replaces your right to stop a video during the review window.*

---

## 13. Update (22 Nov 2026, later): the judge cascade

Your order: two judges of different model families, the stricter answer wins, never the writer, fast failover, fewer tokens. What was built, and where your instructions had to be adapted to what is real today:

**Who judges now (free mode, the video's AI review only)**
- **Slot A**, the full prompt and full source: Gemini through Google AI Studio when `GEMINI_API_KEY` is in `.env` (there is none yet, so it is skipped), then Gemini 2.5 Flash, 3.8 Flash and 3.5 Flash-Lite through FreeLLMAPI, then Qwen 3.8 27B and GLM 4.7 Flash, then your Settings judges, then one OpenRouter model as a last resort.
- **Slot B**, a different family than slot A's judge, compact rubric: one OpenRouter free model, 25 s, no retry. If it is busy, down or used up, OpenRouter is skipped for 60 minutes and FreeLLMAPI Qwen, then GLM, answers in the same review.

**Checked before building**
- `deepseek/deepseek-chat-v3-0324:free` and `deepseek/deepseek-r1-0528:free` are **not on OpenRouter** (its public model list, 22 Nov 2026; DeepSeek is paid only there). They stay first in the list and are tried only if they come back. Today slot B's OpenRouter judge comes from the live free list (NVIDIA Nemotron, Particle and others).
- Google's model page says `gemini-2.5-flash` is deprecated: from **1 Dec 2026** its requests go to `gemini-3.5-flash-lite`.
- Gemini free limits are per Google **project**, not per key.
- A real gap was found and fixed: the same model has different names on each provider (`nvidianemotron-3-ultra-550b-a55b`, `nemotron-3-ultra-550b`, `nvidia/nemotron-3-ultra-550b-a55b:free`), and the writer check compared names as typed.

**Token saving, measured on 20 real videos**: source text 59% shorter (Shorts) and 62% (documentaries); the whole prompt 55% and 46%, because the narration is never cut. The excerpts kept every name, date and number on 10 of 10 Shorts and 7 of 10 documentaries; the other 3 go to FreeLLMAPI with the full source so nothing is judged on missing evidence. The 60 to 75% goal is reached on long sources only.

**Safety kept**: a failed, late or malformed answer is never a judge; fewer than two answers is "unreviewed"; reasoning (`<think>`) is removed before an answer is read; the title test now names exaggeration (the Teotihuacan case).
