---
name: model-license-and-data-policy
description: "Use when deciding whether a model, a dataset or a compute service may be used for the channel: model licences, non-commercial terms such as Kaggle's, private data that must never leave this PC, and content policy."
---

# Model license and data policy (Story Studio)

- Production needs a known licence on the list in `config/compute.json` (`licenses_ok_for_production`, matched by whole words: "Apache License" and "apache-2.0" are one licence); `licenses_never` (non-commercial, research-only) is refused everywhere.
- Unknown licence: usable only for public tests until checked. The owner's own fine-tunes carry their base model's licence: check it before production.
- Content policy: uncensored, abliterated, heretic or NSFW models are never used for channel work.
- Data classes: `production` (scripts, voice, unpublished video, private models) never leaves this PC for Kaggle or any third-party notebook.
- Kaggle: personal, non-commercial (Terms of Use, version 22 Jun 2025); BLOCKED_PENDING_TERMS_REVIEW until the owner confirms a task.
- This is a reading of licences and terms, not legal advice.
