# Nightloom hub: real sign-in emails and Google sign-in (10 Nov 2026)

Plan and tests: `docs/superpowers/plans/2026-11-10-hub-mail-google-secrets.md`. Branch `feature/hub`, worktree `~/Desktop/Youtube-automation-hub`. Not pushed, not deployed.

## What you need (two things, both yours to create)

1. **A Gmail app password** (for the sign-in code emails).
   - Needs 2-Step Verification on that Google account. Google's help page: https://support.google.com/accounts/answer/185833 (read 10 Nov 2026).
   - It is 16 characters, shown once, usually in four groups with spaces (the prompt removes the spaces).
   - Not available if the account is a work or school account, uses 2-Step Verification with security keys only, or has Advanced Protection (same page). Google's other page also says app passwords "aren't recommended"; this is a stopgap for sign-in codes, not the final mail setup (a mail service on your own domain is, before many creators join).
   - Google revokes an app password when the account password is changed (same page): make a new one and run the prompt again.
2. **A Google Web client id** (for "Continue with Google").
   - Google Cloud Console, Clients, Create client, application type **Web application** (https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid, read 10 Nov 2026).
   - Authorized JavaScript origins: that page says to add both `http://localhost` and `http://localhost:<port>`, so add `http://localhost` and `http://localhost:8931`. The page never mentions `127.0.0.1` (UNVERIFIED), so open the site at **http://localhost:8931**.
   - Redirect URIs are not needed: the button opens a popup and hands the page a credential (`ux_mode: "popup"` in `hub/web/signin.js`). The hub checks that credential with the client id only; it uses no client secret, so do not paste one anywhere.

## The terminal prompt (paste your values here, not in chat)

```
cd ~/Desktop/Youtube-automation-hub
~/Desktop/Youtube-automation/.venv/bin/python -m hub.configure
```

It asks three questions in order. Enter skips a question, or keeps a value that is already stored.

| Question | What to type | What happens |
|---|---|---|
| Gmail address | the address that will send the codes | shape-checked |
| Gmail app password | the 16 characters (typing is hidden) | spaces removed; anything not 16 letters or digits needs you to type `yes` |
| Google Web client id | the id ending `.apps.googleusercontent.com` | shape-checked, three tries |

Then it saves, offers **one test email to your own Gmail address** (you answer `y` or Enter for no), and prints what is switched on.

- Stored in `~/.config/nightloom/hub.env` (folder mode 700, file mode 600), outside the repository. Saving inside any git work tree is refused. The write is atomic: a power cut leaves the old file or the new one, never half.
- Nothing is saved until all answers are in; Ctrl-C or closing the terminal changes nothing.
- Nothing you type is printed back; the test email is the only thing that sends your password anywhere (to `smtp.gmail.com`, over a TLS connection whose certificate is now checked).
- See what is set (never the values): `~/Desktop/Youtube-automation/.venv/bin/python -m hub.configure --status`
- Start the hub: `HUB_INSECURE_DEV=1 ~/Desktop/Youtube-automation/.venv/bin/python -m hub.server` (the `HUB_INSECURE_DEV=1` is only for local http), then open http://localhost:8931. The first lines it prints say plainly whether mail and Google sign-in are on.
- A real environment variable always wins over the file. A file that other users can read, that belongs to another user or that is a link is ignored, and the hub says why.

## What was checked (10 Nov 2026) and what was not

- **A real bug found and fixed first:** the mailer's STARTTLS did not verify the mail server's certificate (Python's default for that call, measured on this machine: `verify_mode 0`, `check_hostname False`), which would have let someone on the network read the Gmail app password. It now uses a verifying context, and port 465 is supported.
- **Tests that ran:** 112 hub tests passed, 1 skipped, in the worktree (the same suite had 61 before this work; 51 new tests). The 1 skipped needs the official A2A client (`HUB_A2A_SDK_PYTHON`).
- **A real pseudo-terminal run** with fake values: the password was not echoed (the visible answers were, so the check can see an echo), file mode 600, folder 700, the hub started from the file, `/api/config` said Google sign-in is on, and no HTTP response held the password.
- **16 mutation checks** (breaking one safeguard at a time: certificate check, file mode, permission check, newline check, repo refusal, owner check, environment precedence, symlink, space removal, leaks in messages, end of input, startup report): each turned a named test red. A first run gave false results for six of them (one mutation left a file in the worktree that failed the same test every time); that was found, the stray test file removed, and the run repeated.
- **Not tested, because it needs your secrets:** a real email delivered by Gmail, and a real Google sign-in. Both stay unverified until you run the prompt and press through the test email and the Google button. No secret has passed through the assistant.

## Limits and risks

- Gmail's daily sending limit for a personal account: **UNVERIFIED** (the Google page I could read covers Google Workspace only: 2,000 messages a day per user; going over blocks sending for up to 24 hours).
- Mail from a Gmail address to strangers can land in spam; a domain with its own mail service fixes that (research doc section 7).
- The file protects against other users of this PC, not against someone who is logged in as you or has root.
- Using it on the VPS later means copying the file there with `scp` and `chmod 600` (never through git). Not done; deploying needs your yes.
