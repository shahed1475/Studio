---
name: model-checkpoint-recovery
description: "Use when a model job was cut by a power cut, a restart, a lost server or an expired notebook session: resume from its checkpoint without repeating finished items or starting a duplicate."
---

# Model checkpoint recovery (Story Studio)

- Every finished item is saved with `computejobs.checkpoint` (CHECKPOINTED); the job file is written atomically in `data/compute/jobs/`.
- After a restart: `python run.py compute recover` (`computerouter.recover`): jobs left in PREPARING, MODEL_LOADING, RUNNING or CHECKPOINTED become INTERRUPTED, then RECOVERY_PENDING, and local ones resume item by item.
- A Kaggle job: within one session the notebook skips ids already in its `results.jsonl`; a NEW session starts empty, so it resumes only from the finished ids saved in the job's checkpoint (fetching a session's partial `results.jsonl` back is not built yet). `computejobs.interrupted` never declares a remote Kaggle job dead.
- A finished job is never re-run silently (`computerouter.execute` returns it). A duplicate request returns the existing job.
- Protocol errors (`computejobs.JobError`) are raised, never recorded as an interruption.
