---
name: youtube-copyright-check
description: Use to check the rights behind a finished video: every picture credit's license, Wikipedia text attribution, AI-illustration labels and any music, before approval or upload.
---

# Copyright and licensing check

Run before approving any video: `.venv/bin/python .claude/skills/youtube-copyright-check/scripts/check_licenses.py <slug>`.

## What it verifies
- Every picture credit names Public domain, CC0, PDM or AI-generated. "All rights reserved", "fair use", NonCommercial, NoDerivatives or no license at all fails.
- CC BY pictures need attribution; the credit lines in the description provide it.
- AI illustrations are credited as AI-generated, and uploads carry `containsSyntheticMedia`.
- Wikipedia text is credited with CC BY-SA 4.0 (title and link in the description sources).
- Music: the studio uses none by default. If `music/` has tracks it must hold a `LICENSE.txt` stating the permission.

## Risks to tell the owner
- Reused-content risk: scripts are retold in our own words and pictures come from public-domain archives; never copy another channel's script, footage or title.
- Public-domain claims on Wikimedia are the uploader's; spot-check unusual items.
- A passing check means the credits are consistent, not that every rights question is settled by a lawyer.
