# Mail and alerts from the main dashboard (13 Nov 2026)

**Goal:** the owner saves a Gmail app password and a Telegram bot token in the main dashboard's Settings; the hub's sign-in codes go out through that Gmail, and the studio's important events reach the owner on Telegram. No secret ever passes through chat or comes back to a browser.

**Research:** the dashboard already saves keys into `settings.json` (mode 600) and shows only "saved" (`/api/key/save`); the repo has no notify integration but desktop `notify-send` (useless on the server). The hub is a separate container (`~/hub`) that cannot read the studio's files and reads its mail settings once at start. Telegram: Bot API `getMe`, `getUpdates` (find the chat id after the owner messages the bot), `sendMessage`; the token travels in the URL path by Telegram's design, so it is never logged. Gmail: smtp.gmail.com:587 STARTTLS with a verifying context (host is fixed: no arbitrary host can receive the password).

**Design:** `alerts.py` (validate, save, remove, test, find chat, push with dedupe and a daily cap) + dashboard endpoints and a "Mail and alerts" card + a bridge file `data/hubmail/mail.json` (mode 600) that the hub container mounts read-only and reads at every send (no restart, no copy of the secret in two places by hand) + `agentlog.event` pushes `notify` and error events to Telegram.

**Constraints (security-discipline):** secrets write-only (never in a response, log or error text); every endpoint behind the dashboard login; fixed SMTP host; saving is refused unless the secret passes a shape check and, for Telegram, `getMe` accepts it; test buttons send only to the owner's own address and chat; alerts deduped (6 h) and capped (20 a day).

**Not tested without the owner:** a real Gmail login and a real Telegram message (the owner presses the Test buttons).
