# Delphi rebuilt by Autopilot, and Google production readiness: Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native). Steps use checkbox syntax.

**Goal:** (1) Autopilot rebuilds the Delphi documentary from scratch, at the time it has room, with no manual step. (2) The studio is ready for a Google "In production" login with the least hassle, and an expiring login is caught before an upload fails.

## Evidence (20 Oct 2026, 18:40 UTC)
- Autopilot is idle: no render running, plan empty. Nothing is being built for 21 Oct: the 21 Oct documentary slot is Bell Witch (already on YouTube) and the 21 Oct Short slot is the Korean Short (needs a title repair, not a new video). Next work starts after the money cap resets (00:05 UTC): three Short repairs and Pied Piper's polish.
- Old Delphi: its topic "Prophecy or Performance" made the writer invent a debate the source never states; the polish then made the narration repetitive; two pictures are wrong (194 s with a Louvain mark, 272 s). A fresh grounded script under the new controls is cleaner than a third patch.
- Topic choice: `run._best_topic` ranks the queue by research signals, so a topic put at the front is not guaranteed to be picked. A pinned topic must be consumed first.
- Timing without any manual step: Pied Piper's polish (after 00:05 UTC) frees its slot and Autopilot gives it the earliest slot, Thu 22 Oct 19:00 UTC. The next documentary slot, Fri 23 Oct 22:00 UTC, becomes due Thu 22 Oct 10:00 UTC (36 h before); the new Delphi is made then and is finished a day before its slot. If the polish does not happen, Thursday's slot becomes due Wed 07:00 UTC and Delphi takes it. Either way Autopilot decides; the old video is moved to `output_old` (never deleted).
- Money: $4.51 left, about $3.3 a day while repairs ran; cap returns to $1.50 a day at 00:05 UTC. A documentary costs about $0.9 (script, up to 16 pictures at $0.034, reviews). Below $1.50 left, AI pictures switch off by themselves: the owner should top up before Thursday.
- Google (official pages read 20 Oct): Testing + external users: logins expire 7 days after consent. "Publish app" moves the project to In production; an unverified production app is capped at 100 new users for its lifetime (irrelevant for one owner). Verification needs a website and privacy policy on a verified domain, a demo video and scope justification, 3 to 5 business days, and has a personal-use exception. The pages do not state refresh-token expiry in production (UNVERIFIED: proved by watching a login age past 7 days). Default quota: 100 `videos.insert` calls a day (we use 2). Our login was created about 18 Oct 20:50 UTC (local `token.json` birth time), so it expires about Sun 25 Oct 20:50 UTC. `safety.check` returns early when no published video is due, so an expired login would only be noticed by a failed upload.

## Tasks
### Task 1: pinned topics and `remake`
**Files:** Modify `topicqueue.py`, `run.py`, `fixer.py`; Tests `tests/test_topicqueue.py`, `tests/test_fixer.py`.
**Interfaces:** `topicqueue.pin(topic, fmt)`, `topicqueue.pop_pinned(fmt) -> str | None` (file `data/pinned_topics.json`, locked, atomic; never returns a topic twice); `run._best_topic(fmt)` takes a pinned topic first and removes it from the queue; `fixer.remake(slug, topic=None, now=None) -> dict` (archives the folder to `output_old`, pins the topic in the video's format, writes an Activity event); `python run.py remake <slug> [--topic "..."]`.
- [ ] Tests first for each, run suite, commit.

### Task 2: login health
**Files:** Create `ytlogin.py`, `tests/test_ytlogin.py`; Modify `risk.py`, `run.py` (`health`), `dashboard.py` (`yt_connect` stamps the consent time), `tests/test_risk.py`.
**Interfaces:** `ytlogin.status(now) -> dict` (`consented_at`, `mode` testing or production, `days_left`, `level`), `ytlogin.stamp(now, mode=None)`, `ytlogin.check(now, creds=None) -> dict` (forces a token refresh; `ok`, `error`; tells the owner once a day when it fails); Risks row `login` "YouTube login stays valid".
- [ ] Rules: Testing mode: watch at 2 days left, act at 1 day or when the refresh fails; production mode: only the refresh result counts. A failed refresh is reported at once by the hourly `health` job, with the exact reconnect steps.
- [ ] Tests first, run suite, commit.

### Task 3: Google production pack and docs
**Files:** Create `docs/GOOGLE_PRODUCTION.md`; Modify `PRIVACY.md` (say what `youtube.readonly` is also used for), `README.md`, `CLAUDE.md` (eleven risks).
- [ ] The pack: the owner's exact clicks (Publish app, reconnect, copy the token), drafts of the scope justifications and app description, the verification path if ever wanted, what stays unverified.

### Task 4: live
- [ ] Deploy; seed the login stamp (labelled an estimate from the token file); run `remake` on the Delphi folder with the topic "The Oracle of Delphi: Myth, Sanctuary and Excavation"; simulate Autopilot's plan at the times above and report; report the money plainly.

## Limits
- The consent date is an estimate until the next reconnect stamps it.
- Whether production removes the 7-day expiry is not stated by the pages read; the Risks row will show the first real answer.
- Autopilot cannot click in Google Cloud Console; those steps are the owner's.
