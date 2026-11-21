# Dashboard interaction test (real Chrome)

Date: 19 Nov 2026 · Evidence: `reports/ui-audit.json`, screenshots in `reports/shots/`, driver `tests/browserdrive.py`, audit script `reports/audit_ui.py`.
Server: `python3 dashboard.py` in `/home/fahad/studio` on `127.0.0.1:8913` (the owner's real data folder).

## How the session was authorised — no credential change

The dashboard password, `data/auth.json`, the login email and every credential file were left untouched. The audit used a server-side session created with the studio's own `webauth.make_token(webauth.owner_email())` and injected as the `studio_session` cookie through CDP. The token lives in `.logs/test-token` and is revoked at the end of the audit.

## Coverage and result

| Area | What was done | Result |
|---|---|---|
| 13 SPA sections | `home, live, videos, autopilot, desk, create, growth, activity, youtube, footage, channels, downloads, settings` opened in turn; each measured for visible buttons, inputs, alerts, console errors and a screenshot | **PASS** (0 console errors on every section) |
| 6 standalone pages | `/now`, `/competitor`, `/notifications`, `/monitor`, `/footage`, `/channels` | **PASS** |
| Theme switch | `toggleTheme()` light→dark→light, persisted | **PASS** |
| Notification bell | real mouse click opened the panel (47 events, 5 tabs, "Waiting for you" list) | **PASS** |
| Autopilot segmented control | overview, schedule, rules, research each shown and `aria-selected` correct; schedule renders 21 rows | **PASS** |
| Escape closes overlays | panel closed on Escape | **PASS** |
| Mobile widths | 360 px and 412 px: `scrollWidth == innerWidth` on every section and page (no sideways scroll) | **PASS** |
| Auth enforcement | `/api/state`, `/api/now`, `/api/risk`, `/api/autopilot` without a cookie → **401** | **PASS** |
| Host header check | `Host: evil.example` → **403** | **PASS** |
| Origin check on POST | `Origin: https://evil.example` → **403** | **PASS** |
| POST without a session | → **401** | **PASS** |
| Unknown job | `POST /api/job {"cmd":"definitely-not-a-command"}` → **400 {"error":"unknown job"}** | **PASS** |

## Defects found and fixed in this session

1. **Autopilot page did not render at all** (highest severity).
   - Symptom: `TypeError: Cannot read properties of undefined (reading 'length')` at `dashboard.html:1025`; the page stayed on its skeleton.
   - Root cause: `channelwatch.latest()` returned the newest file in `data/channels/`, which is now `craft.json` (the craft-learning advice written daily). That file has no `ideas` or `channels` keys, so the Autopilot view dereferenced `undefined`.
   - Fix (root cause): `channelwatch.latest()` reads only weekly digests (`????-W??.json`). The research agent's ideas and `topicrank`'s reference-channel signals were being emptied by the same bug.
   - Fix (defence in depth): the view uses `(A.channels.digest.ideas||[])`.
   - Test: `test_latest_reads_the_weekly_digest_and_never_the_craft_advice` plus an autouse fixture that stops any test from writing the owner's `data/channels/craft.json`.
   - Verified live: `/api/autopilot` now returns `week 2026-W47, ideas 5, channels 22` and the page renders (audit above).

2. **`/competitor` page failed with `TypeError: Failed to fetch`.**
   - Root cause: the route called `competitor_view()`, which does not exist (`AttributeError`), so the handler returned no response.
   - Fix: `/api/competitor` returns `competitor.generate_insight_report()` — the shape the page reads (`channels`, `competitor_channels`, `generated_at`, `research_proposals`).
   - Verified live: **200**, 29,745 bytes, 22 competitor channels, 5 proposals; page loads with 10 buttons and no console errors.

3. **`/api/competitor/approve` could never work.**
   - It was registered in the GET handler and read the request body there (`UnboundLocalError: b`), while the page POSTs to it.
   - Fix: moved to `route()` (the POST path). Test: approving changes only that proposal's status to `competitor_research_approved`.

4. **A competitor proposal could enter the news queue before approval.**
   - `competitor.research_approval_check()` existed but nothing called it; the queue endpoint accepted any topic.
   - Fix: competitor proposals are now labelled `source: "competitor"`; `/api/news/queue` refuses such a topic until its status is `competitor_research_approved` (400 with a plain reason). Ordinary news proposals queue exactly as before (test added).

## Minor findings (not changed)

- `POST /api/queue/add` with an empty topic answers `{"ok": true}` while adding nothing. Cosmetic; the queue is unchanged.
- The Settings page shows free-model noise as alert text (`extra:gemini-3.6-flash: HTTPError 429/502`, one truncated reply retried with 12,000 tokens). This is honest reporting of provider failures, not a defect, but it is noisy on the page.
- The container `studio-dashboard` publishes port 8913 inside a Docker Desktop VM that the host cannot reach; the host address is served by the host `python dashboard.py` process. This is an architecture discrepancy, reported in the master report; it was not redesigned.

## Limits

- One browser (Chrome via CDP), one viewport family (1440×900 plus 360/412 px). No Firefox/Safari.
- The audit clicks only safe controls: it never approves, uploads, deletes or saves settings.
- Screenshots are evidence of what rendered at that moment, not proof that every later interaction works.

## Dashboard Visibility Note

The Beale Ciphers Short video (built, `output/the-beale-ciphers-a-treasure-that-vanished-with-it/`) has `approved: false` due to `invented_facts` risk (8/10). Per rules, it cannot be approved until the owner decides on content changes. The video **should be visible** in the dashboard's "Ready for Review" section, pending owner review and potential rewrite of the narration to properly frame the Beale cipher story as disputed/hoax from the start.