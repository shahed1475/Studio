# Free model and provider audit (20 Nov 2026)

Status labels: PASS, FAIL, BLOCKED, NOT TESTED, MOCKED, INFERRED. Secrets are never shown here.

## 1. What is configured (read from settings and llm.json, no keys)
- Paid models: OFF (`llm.json` enabled false, free true, free_review true). OpenRouter balance read by the studio: -$0.06. `llm.free_only()` is true. PASS (read)
- The owner's provider (FreeLLMAPI 0.16.31 at 127.0.0.1:31415): writers `gemini-3.5-flash, gemini-3-flash-preview, minimaxaiminimax-m3.1-flash`; judges `gemini-3.6-flash, nemotron-3-ultra-550b`. Then OpenRouter's free roster (`:free` models, measured per role).
- Daily cap of free requests: 900 (`free_daily_limit`).

## 2. Routing that exists (code read and tests run)
| Requirement | What the studio does | Evidence | Status |
|---|---|---|---|
| Route by task | Roles `script`, `review`, `cheap`; each role ranks models by its own measured success, then speed (`freemodels.choose`) | tests/test_freemodels.py | PASS |
| Skip unavailable / exhausted | Provider status read once a minute; `exhausted`, `needsKey`, unavailable not asked (`llm.extra_status`) | tests/test_extra_provider.py; live: at 07:30 both Gemini models were skipped | PASS |
| Respect Retry-After | A 429 parks the model for the provider's Retry-After, capped at 5 min (by design; the proxy's own reset time is shown to the owner) | `freemodels.record`, tests | PASS |
| Circuit breaker | Per model: 3 failures in a row park it for 6 hours; a 429 is "busy", not a failure | `freemodels.MAX_FAILS`, `COOLDOWN` | PASS (per model). A breaker for a whole provider is NOT built: no evidence today of a whole-provider hang |
| Backoff with jitter | One sequential client per job; the race asks two models at once for scripts and reviews, no loops of retries | code read | INFERRED adequate; jitter NOT built |
| Timeouts | Free model 120 s (`free_timeout_s`), paid 240 s | code | PASS |
| Truncated output | A reply cut off by the output limit is asked once more with twice the room (up to 16,000 tokens) | tests/test_llm.py; live today: the proxy logged gemini-3-flash-preview "finish_reason=length" | PASS |
| No silent paid fallback | Free mode never reaches a paid model (agenteval case `case_free_mode_never_sends_a_request_to_a_paid_model_through_the_video_checks`; new test: a 429 falls to a free model only) | tests | PASS |
| Writer never judges own script | Judges by identity (`model_identity`), writers recorded per video (`script_writers`), avoided in later processes | agenteval case with 4 mutation checks | PASS |
| Two judges, worse answer counts | `llm.strictest` over two different free judges, never the writer | tests; live integration this morning | PASS |
| Metadata per job | `script_model`, `script_writers`, `LAST_REVIEW.served`, per-day usage by role (data/llm_usage.json) | records | PASS |
| Secrets never logged | Key scrubbed from errors (`llm.scrub`); key absent from 328 data/log/report files (checked this morning) | grep | PASS |

## 3. Live evidence today (bounded)
- 07:30 UTC: gemini-3.5-flash and gemini-3.6-flash "exhausted" (Google free tier, 20 a day per model; resets 08:00 UTC). The opencode CLI shares this quota.
- 08:00 UTC: both "ready" again but failed upstream (empty completion x2, then a timeout). Three requests in total; no more were sent.
- 08:27 UTC onward (the supervised Short): the proxy served gemini-3.5-flash, gemini-3.6-flash and nemotron-3-ultra-550b successfully; minimax returned 502 twice and gemini-3-flash-preview 502 once, and the router moved on. All calls cost $0.00 (llm_usage: usd 0.0).

## 4. Limits
- Free models are weaker judges than Claude; two of them, and the worse answer counts. Controls that need no model still apply (claim ledger, quote finder, licences, review window, private uploads).
- Several writers and judges are of one family (Gemini Flash, Nemotron): different models, not fully independent minds.
- Google's free quota is shared with the owner's opencode CLI on the same proxy (owner decision).
