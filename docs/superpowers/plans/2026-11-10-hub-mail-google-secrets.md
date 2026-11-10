# Hub mail, Google sign-in and a private place for their secrets: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the owner chose "do everything by you", inline). Steps use checkbox syntax.

**Goal:** The owner pastes their Gmail app password and Google Web client id into one terminal prompt; the hub stores them privately and uses them to mail sign-in codes and switch on Google sign-in, with no secret ever in chat, git, logs or a response.

**Architecture:** `hub/secretstore.py` keeps a mode-600 env-style file outside the repo (`~/.config/nightloom/hub.env`) and loads it into the process environment at hub start (a real environment variable wins). `hub/configure.py` (`python -m hub.configure`) is the terminal prompt: hidden input, atomic write, optional test mail to the owner's own address. `hub/mailer.py` is fixed first: its STARTTLS did not check the server certificate.

**Tech Stack:** Python standard library only (smtplib, ssl, getpass, os, tempfile). Tests: pytest, same style as `tests/test_hub_*.py`.

**Spec:** the owner's message of 10 Nov 2026, 06:25 (Bangladesh time): "do everything by you then provide me a terminal prompt so that i can paste those gmail ... id in there and store those in a secure place". Context: `docs/studio/CREATOR_HUB_RESEARCH_2026-11-10.md` section 7. No separate design document: the owner opted out of the questions; my calls are listed under Rulings.

## Global Constraints

- Secrets never appear in: chat, git (the file lives outside the repo; saving inside the repo is refused), logs, audit rows, HTTP responses, exception text, test output.
- Only these names are stored: `HUB_SMTP_HOST`, `HUB_SMTP_PORT`, `HUB_SMTP_USER`, `HUB_SMTP_PASSWORD`, `HUB_MAIL_FROM`, `HUB_GOOGLE_CLIENT_ID`.
- Gmail SMTP (VERIFIED, developers.google.com/workspace/gmail/imap/imap-smtp, 10 Nov 2026): host `smtp.gmail.com`, port 587 STARTTLS or 465 implicit SSL, authentication required.
- App password (VERIFIED, support.google.com/accounts/answer/185833): needs 2-Step Verification, 16 characters, not available for work or school accounts, security-key-only 2SV or Advanced Protection.
- Google web client id (VERIFIED, developers.google.com/identity/gsi/web/guides/get-google-api-clientid): application type Web application; origins `http://localhost` and `http://localhost:<port>`; `127.0.0.1` is not mentioned there (UNVERIFIED). Our code verifies ID tokens with the client id only and uses no client secret.
- Not verified: the daily sending limit of a personal Gmail account (the page read covers Google Workspace only).
- Hub tests: `V=/home/fahad/Desktop/Youtube-automation/.venv/bin/python; $V -m pytest -q -p no:cacheprovider tests/test_hub_*.py` from the worktree `/home/fahad/Desktop/Youtube-automation-hub`.
- Never push, never deploy (owner's rule).

## Review Focus

- A secrets file readable by group or others: ignored, with the reason shown, nothing loaded (Task 2).
- A file path that is a symlink, or a save target inside the repo: refused (Task 2).
- A password containing `=`, `#`, quotes or spaces round-trips exactly; one containing a newline is refused (Task 2).
- Gmail shows the app password in four groups with spaces: stored without them (Task 4).
- Enter on a prompt keeps the old value; Ctrl-C or end of input midway writes nothing; a power cut mid-write never leaves a half file (Tasks 2, 4).
- A failed test mail shows a reason and never the password (Task 4).

---

### Task 1: Mailer checks the server certificate (found by reading the code)

**Files:** Modify `hub/mailer.py`; Create `tests/test_hub_mailer.py`

**Interfaces:**
- Produces: `SMTPMailer.send(to, subject, body)` unchanged; port 465 uses `smtplib.SMTP_SSL`; any other port uses `SMTP` then `starttls(context=ssl.create_default_context())` before `login`. `from_env()` raises `ValueError("HUB_SMTP_PORT is not a number")` for a bad port instead of an unreadable traceback at send time.

- [ ] **Step 1: Write failing tests** with a fake `smtplib.SMTP`/`SMTP_SSL` recorded through `monkeypatch`: `test_starttls_gets_a_verifying_context` (context `verify_mode == ssl.CERT_REQUIRED`, `check_hostname` true), `test_starttls_happens_before_login`, `test_port_465_uses_implicit_ssl_with_verifying_context`, `test_message_has_to_from_subject_and_never_the_password`, `test_from_env_without_host_is_the_outbox`, `test_from_env_with_host_is_smtp_with_defaults_port_587`, `test_bad_port_is_a_clear_error`.
- [ ] **Step 2:** run `tests/test_hub_mailer.py`; Expected: FAIL (context is None today).
- [ ] **Step 3:** implement in `hub/mailer.py`; Expected after: all pass.
- [ ] **Step 4:** full hub tests green; commit `hub mailer: verify the mail server's certificate (STARTTLS used an unverified context), support port 465`.

### Task 2: The private secrets file

**Files:** Create `hub/secretstore.py`, `tests/test_hub_secretstore.py`; Modify `.gitignore` (add `hub.env`)

**Interfaces:**
- Produces: `ALLOWED: tuple[str, ...]` (the six names); `default_path() -> Path` (`$HUB_SECRETS_FILE` or `~/.config/nightloom/hub.env`); `save(values: dict[str, str], path: Path | None = None) -> Path` (merges with the existing file, atomic: temp file created `O_EXCL` mode 0600 in the same folder, fsync, `os.replace`; folder 0700; refuses unknown names, values with CR/LF/NUL or over 512 characters, a symlink target, and a path inside the repository); `load(path: Path | None = None, environ=None) -> dict` returning `{"loaded": [names], "ignored": reason or ""}` (sets only names not already in `environ`; ignores a file with any group/other permission bit or another owner); `status(path=None, environ=None) -> dict[str, bool]` (names only, never values).

- [ ] **Step 1: Write failing tests**: `test_save_makes_private_file_and_folder` (0600 / 0700), `test_roundtrip_with_equals_hash_quotes_spaces`, `test_newline_value_refused`, `test_unknown_name_refused`, `test_save_merges_and_keeps_other_keys`, `test_group_readable_file_is_ignored_with_reason`, `test_real_environment_wins`, `test_symlink_refused`, `test_path_inside_repo_refused`, `test_status_has_no_values`, `test_failed_write_leaves_old_file_intact` (monkeypatch `os.replace` to raise).
- [ ] **Step 2:** run; Expected: FAIL (module missing).
- [ ] **Step 3:** implement; **Step 4:** pass; commit `hub: a private secrets file (mode 600, outside the repo, atomic, loaded at start)`.

### Task 3: The hub loads the file at start and says what is on

**Files:** Modify `hub/server.py` (`main`); Test `tests/test_hub_server.py`

**Interfaces:**
- Consumes: `secretstore.load`, `secretstore.status`.
- Produces: `server.startup_report(environ=None) -> list[str]` of plain lines ("Mail: Gmail SMTP on", "Mail: local outbox only", "Google sign-in: on/off", "Secrets file ignored: <reason>"); never a value; `main()` calls `secretstore.load()` before `make_server` and prints those lines.

- [ ] **Step 1:** failing test `test_startup_report_names_never_values` (set fake secrets in `environ`, assert each line lacks the secret text and mentions on/off), plus `test_main_loads_the_file_before_binding` through `startup_report`. **Step 2** fail, **Step 3** implement, **Step 4** pass, commit.

### Task 4: The terminal prompt `python -m hub.configure`

**Files:** Create `hub/configure.py`, `tests/test_hub_configure.py`

**Interfaces:**
- Produces: `main(argv=None, ask=input, ask_secret=getpass.getpass, out=print, send_test=None) -> int`. Flags: `--status` (on/off per name and library check, no values), `--no-test`. Asks: Gmail address (shape-checked), app password (hidden; spaces removed; not 16 letters asks for a typed `yes`), Google Web client id (shape `<digits>-<letters/digits>.apps.googleusercontent.com`). Enter keeps an existing value. Stores `HUB_SMTP_HOST=smtp.gmail.com`, `HUB_SMTP_PORT=587`, `HUB_SMTP_USER`, `HUB_MAIL_FROM`. Optionally sends one test code to the owner's own address after an explicit `y`; on failure prints the exception class and a plain hint, never the password. Exit codes: 0 saved or status shown, 1 nothing saved, 2 refused input.

- [ ] **Step 1: Write failing tests** with injected `ask`/`ask_secret`/`out`: `test_spaces_removed_from_app_password`, `test_enter_keeps_existing_value`, `test_eof_midway_writes_nothing`, `test_output_never_contains_the_password`, `test_bad_client_id_shape_refused`, `test_non_16_letter_password_needs_yes`, `test_status_shows_on_off_only`, `test_failed_test_mail_shows_class_not_password`, `test_no_test_flag_sends_nothing`.
- [ ] **Step 2:** fail; **Step 3:** implement; **Step 4:** pass; commit.

### Task 5: Real check, docs, mutation checks

**Files:** Create `docs/studio/HUB_MAIL_AND_GOOGLE_SETUP.md`; Modify `docs/studio/CREATOR_HUB_RESEARCH_2026-11-10.md` (section 7 pointer)

- [ ] **Step 1:** drive `python -m hub.configure` in a real pseudo-terminal (fake values, `HUB_SECRETS_FILE` in the scratch folder): the file is 0600, nothing echoed. Start `hub.server` with it and read `/api/config` (client id appears there by design, being public; the password appears nowhere in any response).
- [ ] **Step 2:** mutation checks: remove the verifying context, the 0600 mode, the group-bit check, the newline check, the space stripping, the atomic replace; each must turn a named test red.
- [ ] **Step 3:** write the setup document (steps for the owner, sources, labels, limits). Commit.

### Final

- [ ] Whole hub suite and the project's full suite (`$V -m pytest -q -p no:cacheprovider`) run; read real results. Self-review against the Global Constraints (no fresh reviewer: no subagent was asked for). Update the memory note and the plan status line.

## Rulings (my calls, to be shown to the owner)

- Store location `~/.config/nightloom/hub.env`, not the studio's `.env`: separate product, separate secret, and the hub can be deployed without the studio's keys.
- Google sign-in needs only the client id (public); it is stored in the same file for one place to look.
- Gmail with an app password is a stopgap for sign-in codes: Google itself says app passwords "aren't recommended"; a domain mail provider is the real answer before many creators join (research doc section 7).
