---
name: remote-model-execution
description: "Use when submitting, monitoring or collecting a model job on this PC or a remote worker: the job protocol, statuses, verified outputs and failure handling."
---

# Remote model execution (Story Studio)

- Submit with `computejobs.submit` (model, task, input reference, environment, resources, timeout, priority, data class). The id is a hash of the request and the environment: asking twice gives the same job.
- Statuses: QUEUED, PREPARING, MODEL_LOADING, RUNNING, CHECKPOINTED, COMPLETED, FAILED, INTERRUPTED, BLOCKED, BLOCKED_PENDING_TERMS_REVIEW, RECOVERY_PENDING; only the moves in `computejobs.NEXT` are allowed.
- A payload that looks like a key or token is refused (`computejobs.SECRET`): workers read their own credentials.
- Run a local job with `computerouter.execute`: Ollama (`computerouter.OllamaAdapter`, GPU or CPU only), every item checkpointed, the output file hashed; an empty answer is FAILED, never COMPLETED.
- Remote: `computerouter.KaggleAdapter` (see the kaggle-gpu-worker skill). VPS: none since 17 Nov 2026.
