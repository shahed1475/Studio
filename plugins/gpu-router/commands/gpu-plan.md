---
description: Decide where a render or inference job should run before starting it
---

Ask for the job's estimated duration if it wasn't given, then run
`gpu-router plan --minutes <N>` (add `--tpu`, `--cpu` or `--interactive` as
appropriate) and explain the decision in one or two sentences. If the job needs
splitting across sessions, say how many sessions and remind about checkpointing.
