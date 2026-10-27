# Problems, ranked (25 Oct 2026)

Sources: `docs/AUDIT_2026-10-24.md`, `docs/AUDIT_2026-10-24b.md` (open items), and what happened on 24-25 Oct. Severity is my judgment.

| # | Problem | Evidence | Impact | Severity | Root cause |
|---|---|---|---|---|---|
| 1 | Policy exposure: about 10 videos in 7 days, a quarter share one structure | `risk.py`; YouTube monetization text names mass-produced content | channel limited or demonetized | High | no weekly cap chosen (`max_videos_per_week` is 0 = off) |
| 2 | No growth engine yet: 3 subscribers, no income, about $2.5 a day spend | Analytics; usage file | money runs out (credit $8.43) | High | audience and packaging unproven; only Bangladesh showed as a country (unverified why) |
| 3 | Saved records are written by many modules without one safe writer | grep of `write_text` on `meta.json` (recheck, fixer, controls, autopilot); a stale-write bug was found on 24 Oct | a lost edit or a corrupt record | High | no single record API; each module read-modify-writes |
| 4 | No tests in the cloud | repo has no CI | "worked on my PC" before a deploy | Medium | tests run by hand before deploy |
| 5 | The safety check can pause Autopilot by mistake | 25 Oct 18:15 UTC: a held or deleted video paused it and stopped uploads; fixed in `26cf53d`; the owner switched Autopilot on again at 19:24 UTC 25 Oct (status: resolved) | uploads stop until the owner switches it on | Medium | the check judged a held video as published |
| 6 | The picture judge accepted a roller coaster as a myth picture | public Short `y6Cyujv7vZg` (now private) | a wrong picture on a public video | Medium | it saw only file names; fixed `d3782cd` (categories now read) |
| 7 | Backups are on the same disk | `backups/` | a disk or server loss loses the records | Medium | off-server copy is a manual `scp` |
| 8 | Engine is built for one kind of channel | about ten modules assume one Wikipedia article and public-domain pictures | a second channel type needs a profile layer first | Medium | design for one channel |
| 9 | Measurement gap: no click rate or retention in code | the API refuses impressions | titles and thumbnails tuned blind | Medium | read by hand in Studio |
| 10 | Old caption ghosting in two public Shorts (Knossos, Skinwalker) | frame check 21 Oct | looks poor | Low | fixed in code; the old uploads stay until the owner approves a replacement |
| 11 | Leftover items on the server | three render folders without `meta.json`, the old Thunderbird records | clutter | Low | deletion needs the owner's approval |
| 12 | A third-party tool (`ecc` plugin) is loaded and not vetted | hooks run on every tool call; 87 scanner findings, mostly text | unknown side effects | Medium | installed on 24 Oct without a scan; the owner had it uninstalled on 25 Oct (status: resolved) |

## The five that hurt most
1. **Policy exposure (1)** and **no audience or income (2)**: they are the main reason the project could fail, more than any bug.
2. **No safe writer (3)** and **no cloud tests (4)**: the next big changes (profiles, new channels) touch every module that saves a record.
3. **Autopilot (5)** was off for about an hour on 25 Oct and is on again.
