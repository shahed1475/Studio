# Production readiness (21 Nov 2026)

| Question | Answer | Why |
|---|---|---|
| Can Autopilot make a Short on free models by itself? | **Yes, with review holds working** | two Shorts made end to end; one passed after a repair, one held for real content problems |
| Can it make a 20 to 25 minute documentary? | **Not yet reliably** | the film finished at 19.1 min (the word rate is now fixed for the next one) and failed its fact review; it needed three tries because of two code defects, now fixed |
| Does it survive load-shedding? | **Yes for state; mostly for work** | state files survived a real cut; scenes, voice lines, final parts and the sound resume; the brand overlay pass repeats after a cut; one resume re-rendered 59 of 81 scenes (cause under diagnosis) |
| Will it publish something wrong by itself? | **No** | these runs never approve; a failed or held review blocks; but Autopilot itself has `auto_approve: true`: switching Autopilot on would let it approve and schedule passing videos (the owner's standing setting) |
| Is it free? | **Yes** | paid models off; free OpenRouter models, the owner's proxy, Cloudflare free pictures, edge-tts, Blender on the CPU |

## Before switching Autopilot on (owner)
1. Decide `auto_approve` (on today) and `pause_scheduling` (off today).
2. Decide what happens to the held videos: Seven Sleepers (fact flags, `run.py repair`), Raijin and Fujin (`run.py repair ... --extra` or set aside), and the older approved-but-unsent ones.
3. Commit the uncommitted work (20 and 21 Nov) after reading the diffs.

## Tests
Full suite after every fix of 21 Nov: see the result appended to YOUTUBE-AUTOMATION-MASTER-REPORT.md (21 Nov section).
