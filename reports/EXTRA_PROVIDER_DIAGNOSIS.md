# Extra model provider: diagnosis, fixes and tests (20 Nov 2026, about 04:20 to 06:00 UTC)

## 1. Why the test said HTTP 429
- The proxy is FreeLLMAPI desktop 0.16.31 (`freellmapi-desktop`, port 31415, started from ~/Downloads). It needs the key (401 without it); the saved key works.
- `/v1/models` lists 331 models. `gemini-3.5-flash` and `gemini-3.6-flash` are there with exactly these names, both marked `execution_status: "exhausted"`.
- The proxy's own limits for these Google free-tier models: 10 requests a minute, **20 a day**. Its cooldown on both ends at **08:00 UTC** (midnight Pacific, Google's daily reset).
- The 429 reply (one test request, answered locally in 0.02 s, nothing sent to Google): `Retry-After: 12796`, `"All models exhausted ... Soonest reset ~4h"`, `retryAtMs` = 08:00 UTC.
- So: **daily quota used up, not a wrong model name and not a broken proxy.** On 19 Nov Google also returned 503 "high demand" and the proxy aborted some calls after 60 s.
- **Another client shares the quota:** the `opencode` CLI sent about 3,800 requests through the proxy on 19 Nov (the studio about 83), including the same Google models (gemini-3.5 and 3.6 flash, gemini-3-flash-preview 24, gemini-3.1-flash-lite 25). This is the owner's own tool and was not touched.
- Cloudflare: the proxy uses a different Cloudflare account from the studio's free pictures (checked by comparing the account IDs, never printed).
- The studio believed a Retry-After for at most 300 s (`freemodels.MAX_RETRY_AFTER`, kept by design), so it asked exhausted models again every 5 minutes.

## 2. Defects found
1. **The writer could judge its own script.** `gemini-3.6-flash` was on both the writer and judge lists. `auto` was a judge, and the proxy's `auto` once served the studio with `gemini-3.6-flash`.
2. **The writer was remembered only inside one process** (`llm._last_free`). `script_model` in the record is the *assigned* model, not the one that wrote.
3. Models the provider itself called exhausted were still asked.
4. The Test button asked only the first script model and showed a bare "429 Too Many Requests".

## 3. Changes (all in ~/studio, uncommitted; backups in `backups/extra-provider-20nov/`)
- `llm.py`:
  - `model_identity` compares one model under several names (`extra:x`, `vendor/x`, `x:free`).
  - `ROUTER_NAMES` and `judge_names_problem`: a judge is never `auto`/`fusion` or a writer; `extra_models("review")` also drops them from a hand-edited file.
  - `extra_catalog` / `extra_status` read the provider's `/models` once a minute; `exhausted`, `needsKey` and unavailable models are not asked. If the list cannot be read, behaviour is as before.
  - `extra_error` gives plain errors ("quota used up" or "rate limited", with the time to try again), key scrubbed.
  - `_served`, `begin_script`, `writers`, `_answered` record who really wrote, including what `auto` was served as.
  - `chat(..., avoid=)` and `_free_review(..., avoid=)`.
  - `LAST_REVIEW["served"]` records the judges' served models.
- `scriptgen.py`: Shorts and documentaries record `script_writers`; `_review_chat(prompt, avoid=)`.
- `reviewer.py`: the final AI review avoids the recorded writers, so it also works in another process.
- `dashboard.py` / `dashboard.html`:
  - Save refuses a judge that could be the writer.
  - Test reads the provider's status and asks one writer and one judge, with one line per model and the reason for each skipped model.
  - The judge field no longer suggests `auto`.
- Tests:
  - `tests/conftest.py`: no test reads a real provider's model list.
  - 11 new tests in `tests/test_extra_provider.py`, including a 429 fallback test (free model only, asked once, writer recorded, no paid model) and an all-fail test (plain error, bounded calls).
  - Single-argument fakes widened in test_fixer, test_prompt_cache and test_reviewer; one expectation in test_llm.
- `agenteval.py`: new case `case_a_judge_is_never_the_writer_even_through_the_owners_provider`, with 4 mutation checks: identity, filter, provider status, served model. The first version passed by timing (a raced loser was still running); it now waits with `llm.settle`.

## 4. Configuration (saved through the dashboard's own save code)
- Before (backup `backups/extra-provider-20nov/settings.json.bak`): writers `gemini-3.5-flash, gemini-3.6-flash, auto`, judges `gemini-3.6-flash, auto`.
- Now: writers `gemini-3.5-flash, gemini-3-flash-preview, minimaxaiminimax-m3.1-flash`; judges `gemini-3.6-flash, nemotron-3-ultra-550b`. The owner's first choices stay first.

## 5. Evidence from real calls (small, synthetic text: an invented lighthouse)
| Model (asked through the proxy) | Tiny JSON test | Writer test | Judge test (2 planted errors) |
|---|---|---|---|
| gemini-3-flash-preview | 200, 2.3 s | 6 lines, no invented number, 4.2 s | both caught, no false flag, 3.4 s |
| minimaxaiminimax-m3.1-flash | 200, 0.6 s | 6 lines, 1.8 s | both caught, 1.0 s |
| nemotron-3-ultra-550b | 200, 1.1 s | 6 lines, 10.7 s | both caught, 5.6 s |
| auto | no answer in 60 s (and 120 s in the dashboard test) | - | - |
| glm-5.3-flash | no answer in 60 s | - | - |
| gemini-2.5-flash, deepseek v4.1 flash | 404 (the proxy's catalog is stale) | - | - |
| gemma-4-31b | 429 (routed to the OpenRouter free pool) | - | - |

**End to end through `llm.chat`, in the worker container:**
- Script: written by `minimax-m3.1-flash` (3.4 s); the record shows it.
- Review: two judges, `nvidia/nemotron-3.5-super-vl:free` (OpenRouter) and `extra:nemotron-3-ultra-550b`. Neither is the writer. They flagged the planted line, risk 9.

**Dashboard Test (new code, real settings):** the exhausted models are skipped with "the provider says exhausted; not asked", `gemini-3-flash-preview` and `nemotron-3-ultra-550b` answered in 1.3 s each.

## 6. Tests actually run
- Full suite: **2681 passed, 0 failed, 11 skipped**.
- agenteval: **64/64**, run isolated; hashes of data/free_models.json and data/llm_usage.json were unchanged by it.
- Dashboard restarted while idle: no render running, healthz 200, user 1000:1000, the provider API still returns 401 without the login.
- The provider key appears in none of the 328 files in data/, logs/, reports/ or this session's scratch folder.

## 7. Limits and what is not verified
- The tests are tiny and synthetic: evidence that the models suit the job, not proof of quality on a 20-minute film. `gemini-3.5-flash` and `gemini-3.6-flash` could not be tested today (exhausted until 08:00 UTC).
- Several writers and judges are the same family (Gemini Flash, Nemotron). They are different model ids, which is what the rule checks; not truly independent minds.
- Whether the owner's Google project has billing off is not visible. The limits (20 a day) match the free tier. NVIDIA's API catalog terms for production use were not checked.
- A line rewritten later by the fixer in a separate process is not added to `script_writers`. Within the fixer's own process its writer is avoided.
- The Settings card was not clicked in a browser: the dashboard needs the owner's login. The endpoint code was run in the dashboard container.
- Model identity is by name. `gemma-4-31b` and `gemma-4-31b-it` count as different models.

## 8. Owner decisions
1. Whether opencode should keep sharing this proxy (it uses most of the Google free quota), or get its own keys or limits in FreeLLMAPI.
2. Commit and push of these changes (nothing is committed; the 20 Nov audit work is also still uncommitted).
3. Click "Test it" once in Settings to see the new result lines.
