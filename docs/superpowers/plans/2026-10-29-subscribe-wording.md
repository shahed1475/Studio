# Plan: say "subscribe", never "follow" (29 Oct 2026)

**Problem.** The owner heard a Short say "follow" near its end (about 48 s in). On YouTube people subscribe; "follow" is the wording of other apps.

**Root cause (found, not guessed).** `scriptgen.short_prompt` told the writer: "The last line is a short invitation to follow for the next story." Nine writer-made Shorts on the server end with a line like "Follow for the next story." Shorts cut from a documentary (`clipper`) end with "...is on our channel" and are not affected; documentaries have no closing invitation (the reviewer warns on one).
Also: `tts.INVITE`, `reviewer.FOLLOW`, two tests and one eval case use "follow" as sample wording (they stay correct because they match both words, but the samples are changed).

## Where the 9 old Shorts stand (server, 29 Oct)
| State | Videos | What this change does |
|---|---|---|
| Public on YouTube | Korean dragon king, Skinwalker, Voynich, Knossos, Thunderbird legend | Nothing. A public video is never changed without the owner's yes, and YouTube cannot swap the audio of an uploaded video. Owner decision. |
| Uploaded, private, on hold | Thunderbird (a name), Thunderbird (spirit), Cambyses 50,000 | Nothing. Same reason (a new voice means a new upload and deleting the old one). Owner decision. |
| Local drafts, never uploaded, on hold | Cambyses sandstorm, Kitsune, Tortoise and Hare | Nothing now (the voice and the captions are burned into the file; a re-render costs money and the credit is $2.24). When any of them is re-rendered (`run.py redo-short`, the fixer), the new rule rewrites the line first, so it is voiced and captioned as "subscribe". |

## Changes
1. **Prompt** (`scriptgen.short_prompt`): the last line invites the viewer to *subscribe*; say so in the prompt and forbid "follow".
2. **Deterministic fix** (`scriptgen.subscribe_invitation`): only the LAST line of a Short, only when it is a short invitation (it has an invitation cue such as next, more, story, channel and a "follow" used as a command). "Follow for the next story" becomes "Subscribe for the next story"; "Follow along, and I'll tell you..." becomes "Subscribe, and I'll tell you..."; "follow us" and "follow this channel" are handled. Story lines ("the children follow the piper", "Mammy Water will follow") are never touched. Idempotent.
3. **Where it runs**: `scriptgen.script` (a new script) and `run._produce_short` (every render path: new, redo, repair, clipper), so voice and captions are always built from the corrected text.
4. **Reviewer** (`reviewer.generator_checks`): new warning `invite_wording` on a Short whose closing invitation still says follow. Warning only, like the other generator rules.
5. **Agent rules**: creator playbook (one phrase, Never section stays whole), new `agenteval` case with a mutation check, tests.
6. **Samples**: tests and the eval case use "Subscribe".

## Out of scope (stays as it is)
- Public and uploaded videos (owner approval).
- `tts.INVITE` and `reviewer.FOLLOW` keep matching "follow" so old videos still get the invitation delivery and the payoff check.
- The 8 to 14 minute documentary target, money, Autopilot switches.

## Verification
- New tests first (they fail), then code, then the whole suite (`.venv/bin/python -m pytest -q`).
- `deploy/clean_check.sh`, commit named files only, `git pull --rebase origin main`, push, `deploy/deploy.sh dry-run-first`.
- On the server: the prompt text and the fix function are the deployed ones; no render is running; nothing on YouTube is touched.
- Unverified until a new Short is written: that the AI writer obeys the prompt (the deterministic fix is the safety net) and how the new wording sounds in the voice.
