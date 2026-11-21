# Free-model infrastructure (2026-11-20)

## What already exists (inspected, kept)
- **Registry** (`freemodels.py`, `data/free_models.json`):
  - The **live** OpenRouter list, refreshed daily: free price only, text output, at least 16k context, image/audio/embedding/guard models skipped.
  - Each model gets a capability score: +3 for `response_format`/`structured_outputs`, plus context size, plus known families.
  - Per model and role it keeps: valid answers, invalid JSON, slow answers, `finish_reason` and the median of the last 9 timings.
  - Failure cool-down: 3 failures give 6 hours. A 429 counts as "busy": 10 minutes, or Retry-After capped at 5 minutes on the owner's proxy.
  - Daily quota: OpenRouter's `/key` endpoint, with 5 requests always kept in reserve.
- **Routing per task** (`llm._free_chat`, `_race`, `_ask_free`):
  - The owner's own provider is asked first; it uses none of OpenRouter's allowance.
  - Then `freemodels.choose(role)`: context large enough for the role (32k for scripts), not cooling, not busy, ranked by reliability for that role, then speed.
  - Scripts and reviews **race the top two** models.
  - A reply cut off by the output limit is asked once more with twice the room, up to 16,000 tokens.
  - When every model is only busy, the call waits for the first one to come back.
- **Independent judging** (`free_review`): two different free models, never the writer, and the worse answer counts (`llm.strictest`).
- **Mechanical work is code, not a model**: claim ledger, quote finder, licence checks, caption timing, ffprobe and decode checks, the duplicate check and the schedule.

## Defects found and fixed today
| # | Defect | Fix | Evidence |
|---|---|---|---|
| 1 | **Free Mode reached paid models.** `thumbscore.score` (automatic, `anthropic/claude-sonnet-5.5`), `voicecheck.listen` (automatic before an approval, `google/gemini-3.1-flash-lite`) and `videoinspect.gemini_analyze` (`google/gemini-3.1-pro-preview`) checked only the daily dollar cap, never the paid-models switch. OpenRouter refused them only because the credit is −$0.05. | New `llm.paid_allowed()`: paid models only while `llm.json` `enabled` is true. All three refuse before any request. Local Whisper listening stays allowed. | `tests/test_free_mode_no_paid_checks.py` (4). A mutation of each of the 3 gates fails a test. New agenteval case `case_free_mode_never_sends_a_request_to_a_paid_model_through_the_video_checks` plus its mutation test. |
| 2 | `llm.parse_json` (a live edit) counted braces without reading strings, so a fenced reply holding "a { in text" was rejected and the call wasted a retry. | `json.JSONDecoder.raw_decode` tried at each `{`. | 7 new cases in `tests/test_llm.py`. The old code fails 2 of them. |
| 3 | **Invented test data in real files.** Tests and the daily agent evaluation wrote fake models (`a/m1:free`, `b/m2:free`, `b/slow:free`) into `data/free_models.json` and a fake day into `data/llm_usage.json`. This erased the learned reliability and timings of the real free models (seen in the 19 Nov and 20 Nov backups, and again during today's test runs). Cause: `llm._race` leaves the losing request running, and it recorded its result after the redirect was undone. `agenteval.isolated()` also never redirected these two files. | `llm.settle()` waits for unfinished race requests. `agenteval.isolated()` redirects `freemodels.FILE` and `llm.USAGE_FILE` and settles before restoring. `tests/conftest.py`: a session-wide safety net, plus redirects of `freemodels.FILE`, `videoinspect.MODALITY_CACHE` and `llm.PRICES_FILE`. | `tests/test_race_settle.py`: the protection, plus the mutation that reproduces the pollution. Hashes of the real files stay the same across `test_llm`, `test_freemodels`, `test_agents_training` and a full `agenteval.run()`. |
| 4 | Data repaired | `data/free_models.json` restored from the 19 Nov backup without the 3 invented models: 15 models, history for 8. `data/llm_usage.json` restored from the 20 Nov 09:30 backup without the invented day. The calls counted between 09:30 and 09:38 today are lost; today's spend is $0. | Polluted copies kept as `backups/removed-competitor-20nov/*.polluted-20nov.bak`. |

## Real availability (measured 20 Nov, about 03:40 UTC)
| Provider | Result |
|---|---|
| Owner's proxy `127.0.0.1:31415` (`extra:gemini-3.6-flash`, `extra:gemini-3.5-flash`) | Up, but **429 Too Many Requests** on both, at once |
| OpenRouter free allowance (`/key`) | 1,000 a day, 0 used today |
| OpenRouter free roster (live refresh) | 13 models with ≥16k context. Top: gemma-4-26b, gemma-4-31b, nemotron-3.5-super-vl, ernie-5.5-flash, dots-3-note |
| One tiny request to the top two | **429 "temporarily rate-limited upstream" (Google AI Studio)** |

So right now, free text generation is blocked upstream on the best models. The router handles this correctly: busy is not broken, it tries the next model and waits for the first to come back. Free tiers give no guarantee of when that happens.

## Not built, and why
- **Extra registry fields** (tool calling, modalities, last success): `refresh()` already reads `supported_parameters` and `architecture`, and uses JSON support in the score. Studio prompts use no tool calling, so storing it would add nothing a decision reads.
- **A second, parallel router:** not built. `llm.chat` is the single entry point (`tests/test_model_routing.py`), and a second router would split the one place where Free Mode is enforced.
- **Local Whisper for the narration check:** `faster_whisper` is not installed on the host or in the worker. In Free Mode the listen check is now skipped (warning-only). Installing it is a dependency and a model download, so it needs the owner's yes.

## Owner decisions
- Whether to install `faster-whisper` in the worker image, so Free Mode also listens to every narration.
- The proxy's free quota is used up: check its provider limits, or add a second free provider in Settings.
