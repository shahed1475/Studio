---
name: free-api-provider-routing
description: "Use when a task should go to a free API model instead of the owner's own models: which free providers are on, the shared Cloudflare allowance, and never falling back to a paid model."
---

# Free api provider routing (Story Studio)

API providers are routed by `llm.py` (and `judges.py` for video reviews), not by the compute router.

- Paid models only when switched on in Settings (`llm.paid_allowed`); Free Mode refuses every paid call.
- Order for a judge: Google direct, the owner's provider (FreeLLMAPI), OpenRouter free models, then the judges that share the Cloudflare picture account (`llm.picture_sharing_models`, `shares_picture_allowance` in `config/judges.json`) last, and not at all while Cloudflare says the account's day is spent (`freeart.account_exhausted`, its answer 429 code 4006).
- The free pictures keep their allowance: text judges never use it first.
- `computerouter.providers_view` shows the state without any key.
