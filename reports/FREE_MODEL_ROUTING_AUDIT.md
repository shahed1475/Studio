# Free model routing audit (21 Nov 2026)

Sources read: `llm.py`, `freemodels.py`, `llm.json` (switches only, no keys), `data/free_models.json` (measured outcomes), tests. No model was called for this audit.

## 1. Mode on this server (read from llm.json)
`enabled: false` (paid models off), `free: true`, `free_review: true`, `free_daily_limit: 900`, `free_art: true` (Cloudflare FLUX, 9,000 Neurons a day), `ai_art: false`. Paid calls are gated by `llm.paid_allowed()` (thumbscore, voicecheck, videoinspect gated on 20 Nov). Free Mode cannot fall back to a paid model: tested in `tests/test_llm.py` and agenteval `case_free_mode_never_sends_a_request_to_a_paid_model_through_the_video_checks`.

## 2. What exists (verified in code and tests)
| Requirement | How it is done | Where |
|---|---|---|
| Real model ids only | OpenRouter's `/api/v1/models` list, free models only (13 listed at 11:26 UTC 20 Nov); the owner's proxy models from its own list | `freemodels.refresh`, `llm.extra_models` |
| Per-job routing | roles `script`, `review`, `cheap`; ranked per role by measured reliability, then median speed of the last nine answers | `freemodels.choose`, `record` |
| Health / circuit breaker | 3 failures in a row: the model cools down; a 429 parks it for its Retry-After (capped 300 s) | `freemodels.record`, `available` |
| Bounded waiting | all models busy: wait for the first to come back, at most 150 s; 3 rounds with 20/40 s pauses | `llm._free_chat`, `FREE_WAIT_LIMIT` |
| Exhaustion | the day's free requests are counted; at the limit no request is sent (`_NoAllowance`); cheap jobs keep a share free for scripts and judges | `llm._ask_free` |
| Concurrency | at most two requests per call (a race of the two best for scripts and reviews); a 6 s gap between calls to one proxy model | `llm._race`, `_pace_extra` |
| Timeouts | 120 s per free call (paid 240 s); a total request deadline | `llm.json free_timeout_s` |
| Structured output | JSON parsed; a reply cut off by the output limit is asked once more with twice the room (up to 16,000) | `llm._ask_free` |
| Independent judging | the writer never judges: writers are recorded with the video (`script_writers`) and avoided under any name (`model_identity`); two different free judges, the stricter answer counts; one silent judge gives no review (`unreviewed`, never a pass) | `llm._free_chat`, `llm.strictest`, `scriptgen._review_chat` |
| Who did the work | `script_writers` in the record, `LAST_REVIEW` (models and what was served) in the review note | `llm.writers`, `reviewer` |

## 3. Defect found today and fixed
**A router judge could be the writer.** `openrouter/free` is OpenRouter's own router: it hands each request to some free model. On 20 Nov it answered 73 reviews. What it served was recorded only for the owner's proxy, and the writer-is-never-the-judge filter compared requested ids only. So when `nvidia/nemotron-3.5-super-vl:free` wrote a script, `openrouter/free` could pass the review to that same model and nothing would notice.
- Fix: every free reply's `model` field is recorded (`llm._served`); after a judge answers, `_served_a_writer` refuses the answer when the router served one of the script's writers, notes it, and asks the next judge. A router that served another model is still a fair judge. A router used as a writer now adds what it served to the writers.
- Tests: `test_a_router_judge_answered_by_the_scripts_writer_is_not_used_and_another_judge_is_asked`, `test_what_a_router_served_as_a_writer_is_recorded_so_it_never_judges_the_same_script`. Mutations (no served-writer check; served model recorded only for the proxy) fail them.
- Not checked: whether any review on 20 Nov was in fact served by its writer. The served model of those calls was never recorded, so this cannot be known.

## 4. Models that actually answered (data/free_models.json, 20 Nov 2026; 779 OpenRouter free requests that day)
| Model | Role | Answers ok | Failures | Note |
|---|---|---|---|---|
| nvidia/nemotron-3.5-super-vl:free | script | 120 | 1 | main writer, about 10 s an answer |
| extra:minimaxaiminimax-m3.1-flash (owner's proxy) | script | 9 | 0 | |
| particle-ai/particle-1:free | review | 79 | 0 | |
| openrouter/free (router) | review | 73 | 31 (23 not JSON) | see section 3 |
| extra:nemotron-3-ultra-550b (owner's proxy) | review | 5 | 4 | slow (50 to 100 s) |
| baidu/ernie-5.5-flash-preview, dots-3-note-preview, recursive/flint-v1.0, liquid/lfm-3-1.7b | review/script | 0 | 3 to 5 each | cut off by the output limit, or timed out |
| google/gemma-4-26b / 31b, inclusionai/ling-3.2-flash | - | - | parked by 429 | |
The owner's Gemini models on the proxy were out of Google's free quota (20 a day per Flash model, reset 08:00 UTC) on 20 Nov (`EXTRA_PROVIDER_DIAGNOSIS.md`).

## 5. Limits
- Free judges are weaker than a paid model; a review by them is labelled as free in its note.
- Routing is by measured reliability and speed per role, not by a declared capability table; a new model starts at a neutral score.
- Prompt caching applies only to `anthropic/` models (paid, off now).
- The race spends one extra request per script part or review.
