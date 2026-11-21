# Dashboard audit, real dashboard (2026-11-20)

## The live dashboard (`studio-dashboard`, http://127.0.0.1:8913)
- Restarted once on the new code at about 04:00 UTC, after a check that nothing was rendering. The worker was not touched.
- `/healthz` 200. No error or traceback in the log after the restart.
- **Permissions without a login:** `/` gives 303 to the login, `/login` 200, `/api/state` and `/api/autopilot` give **401**. The password, login email and `data/auth.json` were not touched (file time 2026-11-19 18:05, unchanged).

## Clicked in a real Chrome against the real code and the real data
Method: a second instance of the same code, inside the same container, reading the same files, on 127.0.0.1:8931 only, with the login off in memory.
- **Every POST refused by the server**, except `/api/rules/doc-length`.
- **Every POST also blocked in the page** by a fetch guard. Confirm, alert, prompt and window.open were neutralised.
- So no button could change anything. Afterwards the audit server was stopped, and the setting files were confirmed unchanged by their file times.

| Page | Buttons clicked | Script errors on open | Script errors after clicks | Notes |
|---|---|---|---|---|
| Home | 19 | 0 | 0 | |
| Live | 2 | 0 | 0 | Shows the real 19 Nov ffmpeg failure (errors are visible, as they should be) |
| Videos | 1 | 0 | 0 | |
| Autopilot | 10 | 0 | 0 (5 refused POSTs, e.g. Turn on, Run one pass now) | Documentary length control present |
| Tasks | 2 | 0 | 0 | |
| Create | 40 of 128 | 0 | 0 (39 refused POSTs, e.g. Create video, Create Short) | |
| Growth | 10 | 0 | 0 | |
| Activity | 1 | 0 | 0 | Same real error visible |
| YouTube | 5 | 0 | 0 (Make avatar and banner refused) | |
| Settings | 16 | 0 | 0 (Remove key, Save AI settings refused) | Keys not shown |
| Footage | 1 | 0 | 0 | |
| Channels | 0 | 0 | 0 | |
| Downloads | 0 | 0 | 0 | |
| Niche | 0 | 0 | 0 | Owner studio, by design |

- **POSTs the clicks tried, all refused:** `/api/agent/config`, `/api/agent/profile`, `/api/channels/remove`, `/api/desk/advice`, `/api/desk/task`, `/api/job`, `/api/queue/remove`, `/api/autopilot/config`, `/api/extra-llm/save`, `/api/extra-llm/test`, `/api/llm/config`, `/api/llm/test`, `/api/sources/test`. Each one has a route that answers in the real dashboard.
- **Phone (360×780):** 0 px of sideways scroll on all 9 main pages, and no script errors.
- Screenshot: `/tmp/audit/autopilot.png`.

## Save, reload and restart: the documentary length
1. The Rules section showed 20 and 26.
2. I saved 20 and 26 from the page (the value already in force).
3. The server logged `ALLOWED POST /api/rules/doc-length`. `data/rules_state.json` now holds benchmarks 20/26 and history `p-20261120-02` "approved" (rules version 1.0.1). A backup of the file before this is in `backups/removed-competitor-20nov/`.
4. After a reload the page showed "20, 26 … about 84 to 100 lines and 2,939 words".
5. **After a full restart of the server process**, `/api/autopilot` still returns `doc_length` 20 to 26.
6. In the worker, `scriptgen.DOC_MINUTES` is (20.0, 26.0) (see `TASK_AUTOPILOT_AUDIT.md`).

## Not covered
- The Create page has 128 buttons; the crawl clicks up to 40 per page.
- Video detail and review views were opened only through the Videos list's single button, so each detail panel was not clicked.
- Only existing pages were checked. There is no separate "A2A monitoring" or "job history" page: A2A tasks live in the agent bus, shown in Activity and Tasks; jobs are on the Live page and in `logs/`.
- **Worker to dashboard registration of a new video:** not tested, because no new video was made (see `END_TO_END_VIDEO_TEST.md`).
