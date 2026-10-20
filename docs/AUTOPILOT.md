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

## Quality and safety
- Every video is reviewed by Claude (never a free model); if Claude cannot answer, the video is "not reviewed yet" and asked again, never failed and never passed.
- A video is approved only after the reviewer passes it and a vision check of its pictures passes. Your own approval always wins, and a video you hold is never touched.
- Uploads are private with a scheduled time. At most 2 uploads a day. Autopilot never makes a video public by itself outside that schedule.
- Money: a daily cap (reviews may use 50 cents past it), paid models switch off when credit is low.

## What you see
The Autopilot page: **Next videos** (each slot, what fills it, and when Autopilot starts on it), **Working on now**, **Needs you** (only what Autopilot cannot repair), **Scheduled**. The folder `ready/` lists approved videos named by post time.
