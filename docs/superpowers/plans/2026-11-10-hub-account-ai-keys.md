# Hub: per-account AI key storage: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline; the owner said "continue with per-account AI key storage"). TDD for every step.

**Goal:** A creator adds their own OpenRouter key and model once; it is stored encrypted for their account only, and the five writing agents use it (and only it) for that account's calls, with caps that stop a loop from spending their money.

**Architecture:** `hub/keystore.py` encrypts with Fernet (the `cryptography` library, already installed) under a server master key in a mode-600 file; the row binds the ciphertext to its account. `hub/llm.py` turns a stored key into the `ctx.llm(prompt) -> str` callable the agents already take. Three endpoints and one workspace card. Nothing ever returns or logs the key.

**Tech Stack:** Python, `cryptography` (Fernet), `requests`. Fakes for the network in tests. A real key is never used by a test or by me.

**Spec:** `docs/studio/CREATOR_HUB_RESEARCH_2026-11-10.md` sections 5 and 7 ("each creator brings their own OpenRouter key").

## Global Constraints

- The key never appears in: any HTTP response, log, audit row, exception text, test output, git, or this conversation.
- Stored only as Fernet ciphertext; the database file holds no plaintext key. The ciphertext is bound to its account id (a row copied to another account does not decrypt).
- Master key: `data/hub/keystore.key` (mode 600, created exclusively), or `HUB_KEYSTORE_KEY` in the environment for a server. Losing it means keys must be added again; nothing else breaks.
- OpenRouter (VERIFIED): key check `GET https://openrouter.ai/api/v1/key` (docs page read 10 Nov 2026); chat `POST https://openrouter.ai/api/v1/chat/completions` with `Authorization: Bearer <key>` (the studio's own `llm.py` already does this in production). The studio has no default model, so the creator types a model id (`vendor/name`).
- Caps per account: 60 model calls a day, at most 700 output tokens, prompt cut at 6,000 characters, 60 s timeout, 10 key changes an hour.
- A creator pays OpenRouter directly; the page says to set a spending limit on the key. The hub shows no cost figure it cannot back.
- Never push, never deploy. `cryptography` is installed but not in `requirements.txt`: add it.

## Review Focus

- A key pasted with spaces, newlines or quotes: trimmed, shape-checked, refused if wrong (Task 1).
- Another account's session asking for or deleting a key: sees nothing, changes nothing (Task 2).
- OpenRouter answers 401 / 402 / 429 or the network fails: a plain message, never the key (Task 3).
- A prompt-injection page text that asks the model for "the API key": there is nothing in the prompt to leak; the key is never put in a prompt (Task 3).
- A key removed: agents go back to asking for one at once (Task 3).

---

### Task 1: The key store
**Files:** Create `hub/keystore.py`, `tests/test_hub_keystore.py`; Modify `hub/db.py` (table `account_keys`), `requirements.txt`
**Interfaces:** `keystore.set_key(account_id, key, model, now=None) -> None` (ValueError for a bad shape); `keystore.get(account_id) -> {"key", "model"} | None` (internal only); `keystore.status(account_id) -> {"set": bool, "model": str, "added_at": float | None}` (never the key); `keystore.remove(account_id) -> bool`.
- [ ] Failing tests: `test_roundtrip`, `test_database_holds_no_plaintext`, `test_ciphertext_copied_to_another_account_does_not_decrypt`, `test_wrong_master_key_returns_none_not_a_crash`, `test_shape_is_checked_and_whitespace_trimmed`, `test_model_shape_is_checked`, `test_status_never_contains_the_key`, `test_audit_rows_never_contain_the_key`, `test_remove_and_account_delete_cascade`, `test_master_key_file_is_private_and_created_once`. FAIL, implement, PASS, commit.

### Task 2: The model caller
**Files:** Create `hub/llm.py`, `tests/test_hub_llm.py`
**Interfaces:** `llm.make_llm(account_id) -> Callable[[str], str] | None` (None without a key); `llm.LLMError(reason)` with reasons `key_rejected`, `no_credit`, `rate_limited`, `daily_cap`, `unavailable`; `llm.check_key(key) -> {"ok": bool, "reason": str}` (the free key check).
- [ ] Failing tests with a fake `requests.post/get`: `test_call_uses_the_accounts_own_key_and_model`, `test_prompt_and_output_are_capped`, `test_key_is_never_in_the_prompt_or_in_error_text`, `test_http_errors_map_to_reasons`, `test_network_failure_is_unavailable`, `test_daily_cap_is_sixty`, `test_no_key_means_none`, `test_check_key_401_is_rejected_and_network_trouble_is_not_a_rejection`. FAIL, implement, PASS, commit.

### Task 3: Endpoints and agents
**Files:** Modify `hub/server.py`, `hub/agents.py`; Test `tests/test_hub_server.py`, `tests/test_hub_agents.py`
**Interfaces:** `GET /api/key` (401 signed out; `{ok, set, model, added_at}`); `POST /api/key` `{key, model}` (needs `X-Hub`; 400 `bad_key|bad_model|key_rejected`; 429 after 10 an hour; verifies with `llm.check_key`, stores anyway with `verified: false` only when OpenRouter was unreachable); `POST /api/key/remove`. `Hub.llm_for = llm.make_llm`; model agents turn `LLMError` into a plain task message.
- [ ] Failing tests: `test_key_endpoints_need_a_session_and_never_echo_the_key`, `test_other_account_cannot_see_or_remove_a_key`, `test_rejected_key_is_not_stored`, `test_unreachable_check_stores_unverified`, `test_key_changes_are_limited`, `test_agent_uses_key_then_asks_again_after_removal`, `test_llm_errors_become_plain_messages`. FAIL, implement, PASS, commit.

### Task 4: The workspace card, real Chrome
**Files:** Modify `hub/web/app.html`, `hub/web/app.js`
- [ ] "Your AI key" card (password field, model field, Save, Remove, status line, plain notes about paying OpenRouter directly and setting a spending limit); team chips switch to "Ready" when a key is set. Check in real Chrome with a fake OpenRouter: save, status, remove, a wrong key message, the key not in the page or any response, phone width, dark theme.

### Final
- [ ] Mutation checks on the safeguards; whole hub and project suites; self-review; status, memory.
