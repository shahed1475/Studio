---
name: review-judge-compact
description: Use when a video's AI review in free mode is slow, stuck at "unreviewed", passes something it should not, or costs too many tokens, or when changing which models judge, the compact rubric or the source excerpts. Covers the judge cascade (judges.py, config/judges.json), the source slicer (sourceslice.py) and their tests and eval cases.
---

# The judge cascade and the compact rubric

The owner's order of 22 Nov 2026. In free mode (`llm.json` `free` and `free_review`) the AI review of every video is read by two judges of
DIFFERENT model families. The stricter answer counts, and no model that wrote the script ever judges it, under any provider's name for it.
Only `reviewer.llm_review` uses the cascade (it marks the call with `judges.for_video`). The title check and the script fact-check keep the
older two-free-model review (`llm._free_review`). Paid mode (Claude) is unchanged.

## Who judges, in order
- **Slot A** (full prompt, full source, title reasons and better titles for the fixer):
  `gemini:` models (Google AI Studio, only when `GEMINI_API_KEY` is in `.env`), then `extra:` Gemini, Qwen and GLM on the owner's FreeLLMAPI,
  then the owner's judges from Settings, then one OpenRouter free model as a last resort.
- **Slot B** (another family than slot A's judge, compact rubric): one OpenRouter free model with source excerpts. It gets 25 s and no retry.
  A 429, 5xx or used-up allowance makes the cascade skip OpenRouter for 60 minutes (`freemodels.provider_cooling("openrouter", now)`) and move on
  at once to FreeLLMAPI Qwen and GLM (full source), then the owner's judges.
- Never a judge: a writer (`script_writers`, the `script_model` label, the owner's writer list, this process's writers), a router (`auto`,
  `openrouter/free`, `*-auto`), or an answer the provider says another model gave (`body.model`) when that model is a writer or of slot A's family.
- `llm.model_identity` treats one model under several names as one: `nvidia/nemotron-3-ultra-550b-a55b:free` = `extra:nvidianemotron-3-ultra-550b-a55b`
  = `extra:nemotron-3-ultra-550b`. `llm.model_family` groups lines by maker (Gemini and Gemma are both Google).

## The compact rubric and the excerpts
- Output: `{"invented_facts": 0-10, "policy": 0-10, "title_accurate": bool, ["thumb_accurate": bool], "strict_note": "<= 12 words"}`.
  A score in text is read, a half point rounds up, and anything else (missing field, "low", 11) means no judge, so the next one is asked.
  `judges.to_full` maps it onto the full review's fields for `llm.strictest`.
- The title test covers exaggeration: a name, answer, secret, "truth" or "solved" mystery that the narration calls unknown, lost, disputed
  or only a theory (the Teotihuacan case). The same wording is in the full review prompt and in `reviewer.title_ok`.
- `<think>`, `<thinking>` and `<reasoning>` blocks are removed before any JSON is read (`llm.strip_think` inside `llm.parse_json`). A draft verdict
  written while thinking is never the answer.
- `sourceslice.slice_source(source, narration)`: the article's lead, then a greedy cover of every passage holding a name, date, number or quoted
  word of the narration, then keyword-matching passages up to 6,000 characters. The cap is 9,000 characters, tried once more at 12,000.
  `lossless` is True only when every such term the source has is still in the excerpts. A lossy slice never goes to OpenRouter: slot B then
  reads the full source on FreeLLMAPI.

## Steps
1. See who would judge a video now, asking no model: `python run.py judges <video folder>`.
2. Review without saving anything: `.venv/bin/python -c "import reviewer, config; print(reviewer.review(config.OUT / '<folder>', persist=False)['verdict'])"`.
   The `invented_facts` check's note names both judges and their families. `llm.LAST_REVIEW["tried"]` lists every model asked or skipped and why.
3. Change models, timeouts, the cooldown or the caps in `config/judges.json` (shipped, no secrets; a bad file falls back to the defaults and
   says why). Keys stay in `.env` or Settings, never in this file.
4. After any change run `.venv/bin/python -m pytest -q tests/test_judges.py` and the two eval cases
   (`case_two_judges_of_different_families_never_the_writer_and_a_busy_openrouter_is_tried_once_then_skipped`,
   `case_a_judges_reasoning_is_never_its_verdict_and_excerpts_keep_every_checkable_fact`). A new rule needs a new case AND a mutation check.

## Limits (say them when you report)
- Free judges are weaker than the paid Claude review. Two families and the stricter answer reduce that risk; they do not remove it.
- Excerpts keep terms, not every unmarked sentence. A fact with no name, date or number is kept only if its passage shares words with the narration.
- Measured on 20 real videos (22 Nov 2026): source text 59% shorter on Shorts and 62% on documentaries, the whole prompt 55% and 46%
  (the narration is never cut). 3 of 10 documentaries were lossy even at 12,000 characters, so they go to FreeLLMAPI with the full source.
- From 1 Dec 2026 Google routes `gemini-2.5-flash` to `gemini-3.5-flash-lite` (Google's model page, read 22 Nov 2026).
- Gemini limits are per Google project. A new key from the project FreeLLMAPI already uses adds no capacity.
