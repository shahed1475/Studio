# How Autopilot behaves

This is the contract. The code, the tests and the dashboard follow it; change it here first.

## The timing rule: prepare just in time, never days ahead
- A video is posted at a **slot** (a publish time in the audience's New York time zone). Documentaries and Shorts have their own slots.
- It must be **finished and approved 24 hours before its slot** (the review window: your time to stop it). It is uploaded to YouTube as private with its public time set, about 2 hours before the slot.
- Autopilot starts preparing a slot's video **12 hours before that 24-hour window opens** (36 hours before the slot, both numbers are settings). Before then it does not make, and does not repair, anything for that slot.
- A slot that is already less than 24 hours away can no longer take a new video; it is shown as "too soon".

## Who fills a slot that is due, in this order
1. A video that already **passed every check** takes the earliest empty slot (scheduling it costs nothing).
2. Otherwise the **best unfinished draft** is repaired (closest to passing first, a documentary before a Short).
3. Otherwise a **new video** is made from the best topic (research and growth signals, source article must exist).
Drafts whose slot is not due yet stay parked and cost nothing.

## One video at a time
Autopilot finishes the video it works on (repair, review, approve, schedule) before it starts the next. Nothing new is made while a due draft can still be repaired. A video gets two repair tries; after that it waits for you (Needs you) and Autopilot moves on.

## The final check, a day before the slot
When a scheduled video's 24-hour review window opens (27 hours before its slot), Autopilot checks the real file and the written rules again: duration, size, audio, black frames, captions against the script, sources, licenses, claims. No upload happens without a passed final check. If a video the reviewer approved fails, it goes back to being a draft (no approval, no slot) and the fixer repairs it while there is still time. A video you approved yourself is never pulled back: you are told and decide.

## Polish before approval (the invented-facts warning)
A video the reviewer passes can still carry a moderate invented-facts warning (risk 4 to 6 of 10), with the specific details the reviewer named (a debate the source never mentions, a description that misdates the evidence). Before such a video is approved or scheduled, Autopilot does one polish:
- Only the narration lines and the description the reviewer named are rewritten, from the source article only (no new numbers). The old script is saved as `script_before_polish.json` in the video's folder.
- The video is made again only if narration changed; then the reviewer decides again (it may still warn: one try only, then it goes on as it was).
- Never a video you approved, held or that is already on YouTube; never inside the last 30 hours before its slot; not when the day's money cap is spent (the video is not held up by that); at most one polish per 30-minute tick, soonest slot first.
- The outcome (what changed, or why nothing did) is kept in `meta.json` under `polish_done` and shown in the activity feed.

## Quality and safety
- Every video is reviewed by Claude (never a free model); if Claude cannot answer, the video is "not reviewed yet" and asked again, never failed and never passed.
- A video is approved only after the reviewer passes it and a vision check of its pictures passes. Your own approval always wins, and a video you hold is never touched.
- Uploads are private with a scheduled time. At most 2 uploads a day. Autopilot never makes a video public by itself outside that schedule.
- Money: a daily cap (reviews may use 50 cents past it), paid models switch off when credit is low.

## What you see
The Autopilot page: **Next videos** (each slot, what fills it, and when Autopilot starts on it), **Working on now**, **Needs you** (only what Autopilot cannot repair), **Scheduled**. The folder `ready/` lists approved videos named by post time.
