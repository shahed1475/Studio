# Real photos and footage, credited; the Antikythera film and Short (10 Nov 2026, owner's order)

Owner's order (pasted 10 Nov): make one 8 to 10 minute documentary and one Short (35 to 58 s) on The Antikythera Mechanism with REAL photos and footage, upload both PRIVATE with a scheduled
US time, never make anything public directly. Owner decision in the same order: the licence check may accept CC0, public domain, CC BY, CC BY-SA, NASA media (no NASA logos) and the Pixabay
Content License, if every item keeps its address, licence and credit and the credits go in the description. This changes CLAUDE.md section D ("public domain, CC0, labelled AI art only"):
the change is the owner's, dated, and recorded there.

## Findings before building (all read, 10 Nov 2026)
- Server: studio on main b4d6663 (same as origin/main), no render running, Autopilot OFF (`enabled: false`), money $3.60 (daily cap $5.00, stop line $1.50), YouTube login works (production mode).
- Libraries (live test): Commons image and video, Met, Art Institute of Chicago, Cleveland, Openverse work; NASA and Pixabay answer but 0 items are accepted under today's rule; Internet Archive video and Smithsonian answered with no match for the test query; Pexels has no key (and is NOT in the owner's approved list).
- Tests on a clean checkout of origin/main: 2,165 passed, 1 failed (`test_depth_model`, needs a model file kept outside git).
- Antikythera is not used on the channel (`duplicates.topic_conflict` is null for film and Short; an old unapproved draft sits in output_old; the topic was restored to the list on 21 Oct).
- Why the studio never used real Antikythera photos: `footage.images_for` searches Commons only and only public-domain licences; the artifact's photos are mostly CC BY or CC BY-SA. `openmedia.py` reads libraries but nothing in the film or Short builder calls it.
- The film description holds Sources and Chapters but not picture credits; CC BY and CC BY-SA need the credit shown. `studiochecks` forbids the word "copyright", so NASA's "generally not copyrighted" credit and Pixabay's licence name would fail the gate.
- Channel data (API numbers, unmatched to Studio's screen): 13 Shorts 1,272 views, 66% mean viewed; 10 films 423 views, 38% mean viewed; best film Hong Gildong (184 views, 22% viewed, 42% at 30 s). Sleepless Historian (official API): median 21,660 views but two-hour videos; a handle guess for Boring History for Sleep resolved to a small channel (median 115 views, 8-hour videos): not confirmed to be the well-known one.

## Tasks (each test first; an agenteval case and a mutation check for every new rule)
1. `licences.py`: one rule for "may this licence be used" and "does it need a credit" (public domain, CC0, CC BY, CC BY-SA, NASA media, Pixabay Content License; never NC, ND, all rights reserved, fair use, Pexels). `footage_real.licence_ok`, `studiochecks.check_licenses` and `assetledger` use it.
2. `realmedia.py`: real pictures from every approved library, in order Commons, museums, Openverse, NASA, Pixabay; relevance by the film's anchors or the judge; public domain and CC0 preferred over credit-needing items, which are capped per video; each item keeps address, licence, credit, date. `footage.scene_images` gets an optional finder (default off: nothing else changes).
3. Credits in the description: the "Footage and image credits:" section that `compliance.final_description` builds from `footage.credit_lines` (credit-needing items in full, public domain and CC0 as a count); the gate checks that text.
4. agenteval case and mutation checks; CLAUDE.md section D updated with the owner's dated decision.
5. Clean-checkout run, push to main, `deploy/deploy.sh dry-run-first`, verify on the server.
6. Build the film and the Short on the server; reviewer, licences, ffprobe, captions, `run.py listen`, frames looked at; fix; upload both PRIVATE with US Eastern times (film 18:00 on the next free weekday slot, Short 12:30 the next day); read back; report Studio links with times in US Eastern and Dhaka.

## Limits
Money is $3.60: real photos instead of AI pictures keeps a film well under the AI-art cost, but repairs add up; stop and report at the first sign of overspend. A scheduled upload becomes public by itself at its time (YouTube's rule), which is what the owner asked for; nothing is made public directly.
