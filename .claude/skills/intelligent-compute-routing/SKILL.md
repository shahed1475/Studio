---
name: intelligent-compute-routing
description: "Use when choosing which of the owner's models runs a task and where (this PC's GPU or CPU, a VPS, Kaggle): capability, quality, licence, content policy, memory fit, GPU load, quota, privacy and terms."
---

# Intelligent compute routing (Story Studio)

Model, compute and API provider are three different choices.

- `computerouter.route(req)`: req has `task`, `data_class` (production or public-test), `context`, `min_params_b`, `prefer`, `max_latency_s`.
- Order: capability (kind) -> content policy (no uncensored or NSFW model for channel work) -> licence (`computerouter.licence_ok`: unknown refused for production) -> file unchanged -> per environment: paid compute refused, memory fit, busy GPU skipped, Kaggle gate (`computerouter.kaggle_gate`), session start time against the latency limit.
- Rank: preferred model, then quality (parameters), then measured speed class.
- Result: ROUTED (model, environment, verdict, every rejection with its reason), BLOCKED, or BLOCKED_PENDING_TERMS_REVIEW (only Kaggle could run it and its terms are not cleared for the task).
- Try it: `python run.py compute route production` or `python run.py compute route public-test 30`.
