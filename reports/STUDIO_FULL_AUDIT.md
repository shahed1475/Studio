# Studio full audit (20 Nov 2026, supervised Autopilot mission)

Labels: PASS (seen working on real data today), TESTED (unit and behaviour tests pass, not exercised live), INFERRED, BLOCKED, NOT TESTED. Details: AGENT_CAPABILITY_MATRIX.md, FREE_MODEL_PROVIDER_AUDIT.md, BLENDER_INTEGRATION_AUDIT.md, AUTOPILOT_PRODUCTION_TEST.md, SHORT_PRODUCTION_REPORT.md, DOCUMENTARY_PRODUCTION_REPORT.md, FAILURE_AND_PERMANENT_FIXES.md.

## Infrastructure (measured)
- PC: 6 cores, 23 GB RAM, swap 7.4 of 8 GB used at the start (tight), 250 GB free disk. GPU present but its driver does not load (kernel 7.3.4): everything renders on the CPU.
- Containers: studio-worker (3 CPUs, 3 GB limit) and studio-dashboard, image rebuilt today with Blender's two libraries and recreated while idle; user 1000:1000; healthz 200; the API answers 401 without the owner's login.
- No render ran twice at once: one supervised make at a time under the Autopilot lock.

## Components
| Component | Verdict | Evidence |
|---|---|---|
| Topic discovery and selection | PASS | topicrank chose both topics, logged with scores |
| Research (sources) | PASS, fixed | source text now scales with the owner's length (3 articles, about 25,600 characters for the film) |
| Script writing (free models) | PASS after fixes | Short in 17 s of writing; film: 8 runs, root causes fixed one by one (FAILURE rows 19-33) |
| Fact-check (two free judges, never the writer) | PASS, with limits | chunked, patient, judges barred by identity; free judges missed one overclaim (new rule-based check added) |
| Script review gate | PASS | held the film for an unfinished line; that led to the whole-sentence rule |
| Voice (edge-tts) | PASS | 11 lines (Short), 81 long lines (film, about 20 s a line) |
| Pictures (Cloudflare FLUX, archives) | PASS | 11 + 70 drawn; the daily 9,000 Neuron cap is the binding limit for a 20-26 minute film (about one and a third days) |
| Blender | PASS | headless in the worker; Ephesus globe clip rendered and checked by eye; stills tested |
| Motion (2.5D parallax) | PASS (Short) | 11 clips with depth maps, 0 failed; film pending |
| Music | PASS (Short) | CC0 bed, ledger, licence check row passes |
| Render, captions, branding, sound cues | PASS (Short) | ffprobe, decode, loudness -14.0 LUFS, no black frames, captions match the script 100% |
| Packaging and SEO | PASS (Short) | title, tags, description inside YouTube's limits |
| Review and claim ledger | PASS | 35 checks; ledger now records written centuries |
| Fixer (repair) | TESTED | overclaim repair tested; live repair of the Short after 00:00 UTC |
| Doctor (self-repair) | PASS (read live) | names Blender, music, the waiting film with its resume step, set-aside scripts |
| A2A hand-overs | PASS (script, voice stages live) | `a2a.handoff` in the producer |
| Checkpoints and recovery | PASS | saved draft resumed (runs 6 and 8), picture checkpoint stopped and kept 70 pictures, set-aside of short scripts, held script recovered |
| Dashboard registration | PASS (server side) | `dashboard.videos()` lists the Short as "needs review"; the page itself needs the owner's login (not clicked) |
| Free model router | PASS after fixes | thinking budget, total deadline, atomic health file, sticky writer |
| Publishing | NOT TESTED by design | owner rule: no approval, schedule or upload |

## Tests
Full suite 2,738 passed, 0 failed, 11 skipped (10: the Flannan spec exists only in the off-limits workshop and was never committed; 1: the MCP package lives in its own venv by design). agenteval 67 of 67, with 3 new cases today and mutation checks for each.

## Not done or limited
- The documentary waits for tomorrow's free pictures (11 scenes); its render, review and file checks follow after 00:00 UTC.
- The Short's repair (one line) also after 00:00 UTC.
- The dashboard UI was not clicked: it needs the owner's login, which was not touched.
- The GPU driver is not loaded; Blender is CPU-only (a 12-second globe takes about 10 minutes).
- Free judges are weaker than paid ones; fixed-rule checks back them up but do not replace a person's review.
