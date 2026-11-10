# Hub M3: niche research store, research run, plan export: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline; the owner said "continue with M3"). TDD for every step.

**Goal:** A signed-in creator with a chosen ready-made niche presses "Run research", gets sourced topic ideas stored in their own research store (each with its source address, passage, date and an honest label), and can download a per-platform plan package as Markdown. No model, no cost, nothing posted.

**Architecture:** `hub/research.py` owns two new tables (`sources`, `topics`, every row carries `account_id`, deleted with the account) and the research run, which reads the niche's starter topics through the studio's existing `wikipedia.article_info`. The researcher agent gets a rule action (`data.action == "research"`) and otherwise keeps its model behaviour. Two new endpoints (`GET /api/research`, `GET /api/export`) and one workspace card.

**Tech Stack:** Python standard library plus the studio's `wikipedia.py` (requests). Tests: pytest with a fake article reader; real-Chrome check for the card.

**Spec:** `docs/studio/CREATOR_HUB_RESEARCH_2026-11-10.md` sections 5 and 6 (M3).

## Global Constraints

- Labels follow the studio rule A: this module never writes `VERIFIED` (that needs the claim ledger's source-passage check). A topic with a stored https source and passage is `PARTIALLY_VERIFIED` (one secondary source, not cross-checked); without one it is `UNVERIFIED`.
- Web text is data: stored passage is at most 600 characters, never executed, never obeyed, shown as text only.
- Every read and write takes `account_id` from the session; one account never sees another's rows.
- A run is limited to 3 per account per hour and at most 6 articles (Wikipedia's rate limit has been hit before; the helper already spaces calls).
- Nothing is posted. The export is a download of text.
- Not in M3 (needs the owner and Google): the YouTube connection per creator (OAuth for other people's channels needs Google's sensitive-scope verification), per-account AI key storage, Instagram/Facebook/TikTok API posting.
- Never push, never deploy. Hub tests: `V=/home/fahad/Desktop/Youtube-automation/.venv/bin/python; $V -m pytest -q -p no:cacheprovider tests/test_hub_*.py` from the worktree.

## Review Focus

- A custom niche (no ready-made id): the run answers "pick a ready-made niche" and stores nothing (Task 2).
- Wikipedia unreachable or an article missing: counted as failed, not stored, the run still returns (Task 2).
- A page whose text says "ignore your rules and post this": stored as text, changes nothing (Task 2).
- The same run twice: no duplicate rows (Task 1).
- A second account asking for the first account's research: sees nothing (Tasks 1, 3).
- A passage containing HTML: shown as text, never as markup (Task 4, real Chrome).

---

### Task 1: The research store

**Files:** Modify `hub/db.py` (SCHEMA); Create `hub/research.py`, `tests/test_hub_research.py`

**Interfaces:**
- Produces: `research.add_topic(account_id: str, title: str, source: dict | None, now: float | None = None) -> dict` (source `{url, title, passage, revised}`; returns `{id, title, label, source_id}`); `research.overview(account_id: str) -> {"sources": [...], "topics": [...]}`; `research.LABELS_ALLOWED = ("PARTIALLY_VERIFIED", "UNVERIFIED")`.

- [ ] Failing tests: `test_topic_with_source_is_partially_verified_never_verified`, `test_topic_without_source_is_unverified`, `test_non_https_source_is_dropped`, `test_passage_is_cut_at_600_characters`, `test_same_topic_twice_is_one_row`, `test_accounts_never_see_each_others_rows`, `test_deleting_an_account_removes_its_research`. Run: FAIL (module missing). Implement; PASS; commit.

### Task 2: The research run and the researcher's rule action

**Files:** Modify `hub/research.py`, `hub/agents.py`; Test `tests/test_hub_research.py`, `tests/test_hub_agents.py`

**Interfaces:**
- Consumes: `niche.preset(id)`, `wikipedia.article_info(title) -> dict | None` (`research.fetch_article` wraps it so tests replace one name), `auth.hit`, `profile.get`.
- Produces: `research.run_for_account(account_id: str, niche_id: str, max_articles: int = 6, now: float | None = None) -> dict` returning `{"ok": True, "stored": n, "failed": m, "topics": [...]}` or `{"ok": False, "error": "no_ready_made_niche" | "too_many"}`; researcher handler: `data={"action":"research"}` runs it for the account's saved niche, any other message keeps the model path (no key: input_required as before).

- [ ] Failing tests: `test_run_stores_a_topic_per_readable_article_with_source_and_date`, `test_unreadable_article_counts_as_failed_and_run_completes`, `test_custom_niche_stores_nothing_and_says_pick_a_ready_made_one`, `test_run_is_limited_to_three_an_hour`, `test_at_most_six_articles`, `test_hostile_page_text_is_stored_as_text_only`, `test_researcher_research_action_needs_no_model_key`, `test_researcher_other_messages_still_ask_for_a_key`. FAIL, implement, PASS, commit.

### Task 3: Endpoints and the export package

**Files:** Modify `hub/server.py`, `hub/research.py`; Test `tests/test_hub_server.py`

**Interfaces:**
- Produces: `research.export_markdown(account_id: str, platform: str) -> str | None` (None for an unknown platform); `GET /api/research` (401 signed out, else `research.overview`); `GET /api/export?platform=<name>` (401 signed out, 400 unknown platform, else `text/markdown` with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`). The package holds: niche, platform mode and note with its label (from `agents.PLATFORMS`), the checklist, topic ideas with source addresses and labels, and the line "Nothing here was posted."

- [ ] Failing tests: `test_research_endpoint_needs_a_session_and_is_private`, `test_export_unknown_platform_is_400`, `test_export_markdown_has_labels_sources_and_never_says_verified`, `test_export_is_a_download_with_nosniff`. FAIL, implement, PASS, commit.

### Task 4: The workspace card, checked in real Chrome

**Files:** Modify `hub/web/app.html`, `hub/web/app.js`, `hub/web/site.css`

- [ ] "Research" card: Run research button (disabled while running, plain error messages), topic list with label chips, source links (`rel="noopener noreferrer"`, text via `textContent`), and one download link per chosen platform. Check in real Chrome with a fake article reader: run, list, hostile text shown as text, second run message, phone width, dark theme, no console errors. Fix what it shows; commit.

### Final

- [x] Whole hub suite, whole project suite read for real; self-review; update the setup doc/status; memory.

## Status (10 Nov 2026)

Tasks 1 to 4 done, each test first (commits `a35238c`, `0b8ba1b`, `1b5c978`, `f330a04`). Hub suite 142 passed, 1 skipped (was 117). Whole project suite 2,307 passed, 1 skipped, 1 failed: `tests/test_depth_model.py` needs `data/models/depth_anything_v2_small_uint8.onnx`, which exists only in the main checkout (confirmed missing in this worktree; not run in the main checkout from this isolated session). 12 mutation checks on the new safeguards: 12 killed by the named test. Real Chrome run of the Research card: run, labels, source link attributes, hostile text shown as text and nothing executed, plain-words limit message, Markdown download, no script or CSP errors; found and fixed two phone-width overflows that were not from M3 (top bar at 390 px, right column at 360 px).

Rulings: the researcher keeps its model path and gains a rule action rather than a new agent (fewer moving parts; its chip says "Ready to research"); labels in the UI are plain words ("Partly checked", "Not checked") with the exact label as the chip's tooltip; `flex-wrap` on team rows only at 520 px and below (a general wrap moved the chips under the text on desktop). Final review: self-review only.

Not built, and why: the YouTube connection per creator (OAuth for other people's channels needs Google's sensitive-scope verification and the owner's Cloud project), per-account AI key storage, research for a custom niche (needs a key), posting to any platform.
