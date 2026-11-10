"""The model call for one account: its own OpenRouter key and model, with caps, behind the `llm(prompt) -> str` the agents take.

OpenRouter: chat is `POST https://openrouter.ai/api/v1/chat/completions` with `Authorization: Bearer <key>` (the studio's own llm.py does the same in production); the free key check
is `GET https://openrouter.ai/api/v1/key` (openrouter.ai/docs/api-reference/limits, read 10 Nov 2026). The creator pays OpenRouter directly, so the hub only bounds the damage a loop
could do: 60 calls a day per account, at most 700 output tokens, the prompt cut at 6,000 characters, 60 seconds. The key is read once from the key store, goes only into the
Authorization header, and is never put in a prompt, a log or an exception (errors carry a reason word, and the original exception is dropped)."""
import requests

from . import auth, keystore

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
CALLS_PER_DAY, MAX_OUTPUT, MAX_PROMPT, TIMEOUT = 60, 700, 6000, 60
REASONS = {401: "key_rejected", 403: "key_rejected", 402: "no_credit", 429: "rate_limited"}


class LLMError(Exception):
    """A model call that did not give an answer. `reason` is one of key_rejected, no_credit, rate_limited, daily_cap, unavailable."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def make_llm(account_id: str):
    """The account's model callable, or None when it has no readable key."""
    stored = keystore.get(account_id)
    if not stored:
        return None
    key, model = stored["key"], stored["model"]

    def call(prompt: str) -> str:
        if not auth.hit(f"llm:{account_id}", CALLS_PER_DAY, 86400):
            raise LLMError("daily_cap")
        try:
            r = requests.post(CHAT_URL, timeout=TIMEOUT, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Nightloom"},
                              json={"model": model, "max_tokens": MAX_OUTPUT, "messages": [{"role": "user", "content": str(prompt)[:MAX_PROMPT]}]})
        except requests.RequestException:
            raise LLMError("unavailable") from None
        if r.status_code != 200:
            raise LLMError(REASONS.get(r.status_code, "unavailable"))
        try:
            return str(r.json()["choices"][0]["message"]["content"] or "")
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("unavailable") from None

    return call


def check_key(key: str) -> dict:
    """Ask OpenRouter whether a key is valid (a free call). Only a refusal (401/403) is a rejection: trouble reaching OpenRouter is 'unreachable'."""
    try:
        r = requests.get(KEY_URL, headers={"Authorization": f"Bearer {key}"}, timeout=15)
    except requests.RequestException:
        return {"ok": False, "reason": "unreachable"}
    if r.status_code == 200:
        return {"ok": True, "reason": ""}
    if r.status_code in (401, 403):
        return {"ok": False, "reason": "key_rejected"}
    return {"ok": False, "reason": "unreachable"}
