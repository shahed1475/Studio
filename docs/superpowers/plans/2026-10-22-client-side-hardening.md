# Client side (user studios): hardening, test of every button, desktop icon

> The owner's request, 22 Oct 2026: fix the YouTube feature (a user studio must never show or use the owner's main channel), test every feature and button of the client side in a browser, bring over what was fixed for the owner's studio where it matters, deploy, and put an icon on the desktop. Less token use: small steps, tests first for code, the browser only for what tests cannot see.

## What I could verify about "it shows my main account's channel"
No user studio was running on the server (the demo was archived), so the owner can only have seen it in (a) the local test copy I started on this PC, which carried the owner's channel pictures (avatar and banner in "Channel look"), or (b) their own browser being signed in to Google as the main account when a Google sign-in opens. Both are real leaks of the same kind, so all of these are fixed:
1. A user studio never carries the owner's branding pictures, token or text (`tenant.sh` already left them out; the local copy did not).
2. Google sign-in always shows the account chooser (`select_account consent`), so a browser signed in as the owner can never silently connect the owner's channel.
3. A channel that is the owner's, or is already connected to another studio, is refused with a plain message and the login is discarded. The owner's channel id and the claims of other studios are checked by the server, not by the user's browser.
4. The YouTube page says plainly which channel is connected, with "Not your channel? Disconnect".
5. The desktop sign-in button does not exist in a user studio (it would open a browser on the server).

## Roadmap
| Step | What | Check |
|---|---|---|
| R1 | Channel guard, account chooser, plain "connected as" panel, no desktop flow for users (`ytweb.py`, `dashboard.py`, tests) | unit tests; the YouTube page in the browser |
| R2 | Owner-only text out of the client side: "Bangladesh" times become the user's own time zone, risks that do not apply are hidden until the plan is confirmed | tests for the data, browser for the pages |
| R3 | Every page and button of a client studio in a real browser (Home, Videos, Create, Niche, Autopilot, Growth, Activity, YouTube, Settings, sign out), fix what breaks | browser pass with notes |
| R4 | What was fixed for the owner's studio and matters here: the sidebar "Working" state, the long "autopilot is working" message, the honest cost text (already shared code); a list of anything that only the owner's copy has | diff of behaviours |
| R5 | Deploy, one client studio for the owner to try (`test`), the proxy, the invite, the desktop icons | live check from the public address |
| R6 | The Google Web client (only the owner can create it; I try it in the browser first and stop if it is blocked) | sign-in with a second account |

## Limits
- Google sign-in for users stays unproven until a Web application OAuth client exists.
- All user studios share one browser address (see docs/USER_STUDIOS.md).
