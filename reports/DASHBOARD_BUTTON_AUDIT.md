# Dashboard button audit (21 Nov 2026)

Every visible button, switch, checkbox, select and disclosure of the dashboard was clicked with a real mouse event in headless Chrome by `tools/dashboard_button_audit.py`, on a **copy** of the studio (no .env, token, client secret, settings or login files; `run.py` replaced by a stand-in that only records the job; every outside connection pointed at a dead proxy). The live studio was never clicked. Started 2026-11-21 11:50:34 UTC, 9.8 minutes.

## Result

- Controls clicked or checked: 251. Works: 198. Errors: **0**. Refused with a clear message: 3. Disabled (not clicked): 11.
- Phone widths 360 px and 412 px: no page scrolls sideways (all 14 sections, including Reports).
- Server tracebacks: 1, a BrokenPipeError when the browser left a page while /api/risk was still answering (the client hung up; not a fault).
- Jobs the buttons asked for (recorded, not run): 16: agent, autopilot, branding, channels, doc, ideas, make, research, review, trends.
- Videos opened: who-really-wrote-hong-gildong-the-case-for-h-kyun, what-lurked-beneath-knossos-the-minotaur-legend, what-did-ronaldo-do-in-2022-that-no-man-had-done.

## Findings

1. **Save AI settings refuses on the live studio too**: `llm.json` has the same model (google/gemma-4-26b-a4b-it:free) for the writer and the reviewer, and the save check (`llm.py`) refuses that. Reviews themselves are not affected (the free-model race keeps the judge different from the writer), but no AI setting can be saved until a different reviewer model is chosen. Owner's setting.
2. 'No visible effect' rows (19) were checked: an already-selected tab (Overview, Schedule, Rules, Videos, Suggestions, the Views chart), weekday selects that take effect with Save, and the bell and night switch on /now, /footage, /channels. The last two were clicked again by hand on all three pages: the theme flips and the notification panel opens, no errors. The audit watched only the page body, so it missed them.
3. Three 'Open' buttons on Videos were not found after reopening: an earlier click had left a list filter chosen (kept in the browser), so the list showed other videos. Each video page was opened directly instead.
4. Refused with a message (expected in a copy without keys): an empty task (Tasks), Save AI settings (finding 1), the extra provider address (no settings in the copy).

## Per place

| Place | Results |
|---|---|
| menu | works: 14 |
| top bar | works: 2 |
| home | works: 17, skipped (same handler, another item): 1 |
| live | works: 2 |
| videos | works: 6, not found after reopening the page (it depends on earlier state): 3, skipped (same handler, another item): 1 |
| autopilot / overview | no visible effect: 1, works: 9, skipped (same handler, another item): 1 |
| autopilot / schedule | works: 7, no visible effect: 1, skipped (same handler, another item): 1 |
| autopilot / rules | works: 17, no visible effect: 7, skipped (same handler, another item): 1 |
| autopilot / research | works: 20, skipped (same handler, another item): 1 |
| desk | refused with a message: 1, works: 1 |
| create | works: 11, skipped (same handler, another item): 1 |
| growth / overview | works: 6, no visible effect: 2, skipped (same handler, another item): 1 |
| growth / videos | works: 3, no visible effect: 1, skipped (same handler, another item): 1 |
| growth / ideas | works: 7, no visible effect: 1, skipped (same handler, another item): 1 |
| growth / research | works: 5, skipped (same handler, another item): 1 |
| growth / controls | works: 10, skipped (same handler, another item): 1 |
| activity | works: 3, skipped (same handler, another item): 1 |
| youtube | works: 3, disabled (not clicked): 2 |
| footage | works: 1 |
| reports | works: 2 |
| settings | works: 16, refused with a message: 2, disabled (not clicked): 3, skipped (same handler, another item): 1 |
| video page: who-really-wrote-hong-gildong-the-case-for-h-kyun | works: 6 |
| video page: what-lurked-beneath-knossos-the-minotaur-legend | works: 2, disabled (not clicked): 1 |
| video page: what-did-ronaldo-do-in-2022-that-no-man-had-done | works: 5 |
| page /now | works: 5, no visible effect: 2, skipped (same handler, another item): 1 |
| page /notifications | works: 6 |
| page /monitor | works: 1 |
| page /footage | works: 4, no visible effect: 2, skipped (same handler, another item): 1 |
| page /channels | works: 3, no visible effect: 2, skipped (same handler, another item): 1 |
| page /mail | works: 2, disabled (not clicked): 5 |
| phone 360px | works: 1 |
| phone 412px | works: 1 |

Raw rows: `reports/dashboard-button-audit.json` (not committed). Not covered: the live login itself (tests/test_dashboard_login.py), real outside services (Telegram, YouTube, OpenRouter tests from Settings), and anything that needs a person's eyes on the pictures.
