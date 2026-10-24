# Google production readiness (the "professional key")

What I read on 20 Oct 2026, from Google's own pages: [OAuth overview](https://developers.google.com/identity/protocols/oauth2), [Manage app audience / Publish app](https://support.google.com/cloud/answer/15549945), [sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification), [YouTube quota and compliance audits](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits), [videos resource](https://developers.google.com/youtube/v3/docs/videos).

## Where we stand
- The OAuth consent screen is in **Testing**. Google ends every login **7 days after consent** in that state (OAuth overview). Ours was created about **18 Oct 20:50 UTC** (the local `token.json` file's birth time), so it stops working about **Sun 25 Oct 20:50 UTC**. Uploads after that fail until you reconnect.
- The studio now checks the login every hour (`python run.py health`), shows a Risks row "YouTube login stays valid", and tells you at once when it fails (once a day), with the steps below.
- Quota: the default is 100 `videos.insert` calls a day (we use 2). An audit is only needed for more quota.

## The least-hassle path (your clicks; I cannot do these)
1. Google Cloud Console, your project, **Audience**, press **Publish app**. This moves the project to *In production*; any Google account can then authorize it.
2. Reconnect once: on your PC run `./start.sh`, open the **YouTube** page, press **Connect**. Because the app is not verified, Google shows an "unverified app" warning for the sensitive YouTube scopes: continue past it (you are the only user; unverified apps are capped at 100 new users for the project's lifetime, which does not matter here).
3. Copy the new login to the server: `scp token.json deploy@<server>:studio/`.
4. On the server tell the studio the new mode: `ssh deploy@<server> "cd studio && docker exec studio-worker python run.py youtube-login production"`.
5. Proof: the Risks row follows the login for more than 7 days. **The pages I read do not state refresh-token expiry for production apps (UNVERIFIED)**; if the login still dies after 7 days, the alert says so and we use the weekly reconnect instead.

## Do you need Google's verification?
No, not for a studio only you use: Google's own list of exceptions includes "the only user of your app or … a few users, all known personally to you". If you want it anyway (3 to 5 business days):
- A public home page and a privacy policy on a domain you verified in Google Search Console, the privacy policy on the **same domain** as the home page and linked from the consent screen. (GitHub's `github.com` address is not a domain you can verify, so this needs your own domain.)
- Consent screen: app name, support email, home page, privacy policy, developer contact.
- A demo video uploaded to YouTube Studio as *Unlisted*, in English, showing the consent screen with the app name, the OAuth client ID in the address bar, and what each sensitive scope does.
- A justification for each sensitive scope, including why a narrower scope is not enough. Drafts:
  - `youtube.upload`: "Story Studio is a single-owner tool that uploads the owner's own videos to the owner's own channel as private videos with a scheduled public time. Uploading requires this scope; there is no narrower scope that allows videos.insert."
  - `youtube.readonly`: "After each upload Story Studio reads the video back (videos.list) to confirm YouTube stored the title, privacy and scheduled time that were sent, and checks after the publish time that the video became public and has no claim or block. It also reads the channel's own counts to show progress. It never writes with this scope."
- App description draft: "A personal studio that researches, writes, voices, illustrates, schedules and checks history videos for one YouTube channel. One user, the channel owner. Data stays on the owner's server."

## What is already in place for Google's rules
Two scopes only, both justified above; the login file is owner-only (mode 600) and never committed; "Disconnect" deletes it; `PRIVACY.md` states the use, the Limited Use commitment and how to revoke (myaccount.google.com/permissions); nothing from Google is sent to an AI provider.

## Open items
- The private-upload rule for unaudited API projects is **CONFLICTING** (search results say uploads are locked private; the official videos page says they are not). The first video that reaches its public time settles it (Bell Witch, Wed 21 Oct 22:00 UTC); the safety check reports it if it stays private.
- Phone verification for custom thumbnails and videos over 15 minutes comes from third-party guides only (UNVERIFIED). A refused thumbnail is recorded and reported.

## Title changes (24 Oct 2026)
The owner's login now also asks for the `youtube` permission (`safety.WRITE_SCOPE`) when you press Connect YouTube on the PC, so the title test can change a title and put the old one back. It also allows editing or deleting videos, so the code never deletes anything and the scope audit accepts it only while `data/titletest.json` says `"mode": "apply"`. User studios never ask for it.
