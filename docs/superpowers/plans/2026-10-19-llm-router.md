# LLM Router (OpenRouter + local fallback + daily cap) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Steps use checkbox syntax.

**Goal:** Scripts, fact-checks, titles and ideas can run on stronger models through OpenRouter, chosen per job, with a hard daily spend cap and automatic fallback to the local Ollama model.

**Architecture:** New `llm.py` owns config (`llm.json`), usage and spend (`data/llm_usage.json`), the OpenRouter call and cost estimate. `scriptgen._chat(prompt, role)` delegates to `llm.chat`, which falls back to the old Ollama function. Roles: `script` (writing, news summary), `review` (fact-check, must differ from `script`), `cheap` (titles, tags, hooks, ideas).

**Tech Stack:** requests, stdlib json, pytest. OpenRouter chat completions (`response_format: json_object`, `usage: {include: true}`) and the public `/api/v1/models` price list.

## Global Constraints
- Off by default (`enabled: false`); no key means local only. Key lives in `settings.json` (or env `OPENROUTER_API_KEY`) and is never logged, returned by an API, or shown.
- Daily cap in USD (default 1.00, allowed 0.05 to 100); at or over the cap every call uses the local model.
- `max_tokens` per call (default 6000, allowed 500 to 16000).
- The `review` model must differ from the `script` model.
- A failed OpenRouter call (network, HTTP error, bad JSON after one retry) falls back to Ollama and records the reason; it never raises to the pipeline.
- No em-dashes in dashboard text. No git repo: "commit" = run the whole suite.

## Review Focus
- Key missing, model empty for a role, budget reached: local model used, nothing sent.
- Model returns JSON inside code fences or with chatter: parsed; garbage twice: fallback.
- Spend recorded per UTC day and survives a restart; a new day starts at zero.
- Cost missing from the response: estimated from the public price list, never recorded as 0 when tokens were used.
- Test connection never falls back silently (it must show the real error).

### Task 1: `llm.py` (tests in `tests/test_llm.py`)
Interfaces: `load_config() -> dict`, `save_config(cfg)`, `validate_config(raw: dict) -> dict`, `api_key() -> str`, `parse_json(text: str) -> dict`, `spent_today(now=None) -> float`, `record(...)`, `chat(prompt: str, role: str = "cheap", fallback=None, now=None) -> dict`, `decide(question: str, state: str, options: list[str], role: str = "cheap", fallback=None) -> dict`, `estimate(prices: dict, docs_per_day: float, shorts_per_day: float, days: int = 30) -> dict`, `model_prices() -> dict`, `test_call(role: str) -> dict`.
- [ ] Failing tests, then implement, then green.

### Task 2: Wire roles into the pipeline
- [ ] `scriptgen._chat(prompt, role="cheap")`; roles at call sites; update test fakes; suite green.

### Task 3: Dashboard Settings "AI models" panel
- [ ] `GET /api/llm`, `POST /api/llm/config`, `POST /api/llm/test`, panel with key field, three model inputs, daily cap, today's spend, cost estimate; verify in the browser.
