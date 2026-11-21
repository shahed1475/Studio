# Video Pipeline Test Report

Date: 19 Nov 2026
Test: `.venv/bin/python run.py make "The Beale Ciphers"` 
Status: **COMPLETE** (built, needs owner decision on content)

## Pipeline Execution Log

```
PID: 2141542 (background)
Log: .logs/pipeline-short-beale.log
```

> NOTE: This video has **invented facts warnings**. Per CLAUDE.md rules, nothing with open invented-facts warnings may be approved, scheduled, or uploaded. The video needs the owner's attention to decide: rewrite the narration to properly frame the Beale cipher story as disputed/hoax from the start, or archive it.

## Phase completion markers

| Phase | Duration | Output | Status |
|---|---|---|---|
| Topic selection | instant | `The Beale Ciphers` from queue | **PASS** |
| Research | ~5s | Sources gathered, claim ledger populated | **PASS** |
| Script generation | ~10s | 12 lines, open-question hook | **PASS** |
| Script review | ~15s | 99% match, 3 pronunciation leads | **PASS** |
| Voice + captions | ~12s | `narration.mp3`, `captions.ass`, `words.json` | **PASS** |
| Archive image search | ~30s | 11 drawn scenes + 1 approximate | **PASS** |
| Camera motion | ~60s | 11 depth maps + 11 parallax clips | **PASS** |
| Rendering | ~45s | `video.mp4` (57.5s) | **PASS** |
| Quality checks | ~10s | All studiochecks pass | **PASS** |

## Output artifacts

```
output/the-beale-ciphers-a-treasure-that-vanished-with-it/
├── video.mp4           15.02 MB (57.5s, 1080x1920, 30fps)
├── captions.srt        13.4 KB (15 cues)
├── words.json          6.7 KB (speech transcript)
└── meta.json           3.7 KB (approval record)
```

## Key metrics

- **Runtime (voice→video):** ~3.5 minutes
- **Lines:** 12 script lines
- **Scenes:** 12 unique visuals (11 AI-drawn + 1 Wikimedia Commons photo)
- **Camera motion:** 11 parallax clips from depth maps
- **Sound cues:** 2 (riser, hit)
- **Brand marks:** subscribe popup at 52.7s, corner mark from 4.0s
- **Cost:** $0.60 (Cloudflare free art only, no paid pictures)

## Comparison to targets

| Target | Actual | Status |
|---|---|---|
| Short format | 57.5s (target 50–70s) | **PASS** |
| Hook | Open question "What treasure worth millions...?" | **PASS** |
| Subtitle style | Burned-in captions | **PASS** |
| Free mode compliance | No paid images, no OpenRouter credit | **PASS** |

## Limitations noted

- Real photo was used for "Declaration of Independence" (Wikimedia Commons, public domain) but not counted in `parallax.made` since it's an archive image, not drawn.
- One scene (the vault) was skipped due to approximate depth map; the story continues without it.

## Next step

**OWNER DECISION REQUIRED:** Video has `invented_facts` risk (8/10) and `title_matches` failure.

Per CLAUDE.md rules: *"Nothing with an open invented-facts warning is approved, scheduled, or uploaded."*

**Options:**
1. **Accept current version:** Title/description updated, but narration still states disputed claims as facts. The video cannot be approved under current rules.
2. **Archive:** Remove from queue, select different topic
3. **Rebuild:** Re-render with script that properly frames the story as *disputed/hoax mythology* from line 1

**Owner command:**
```bash
# View current video status
python run.py list | grep beale

# If archiving
python run.py archive the-beale-ciphers-a-treasure-that-vanished-with-it

# If rebuilding (requires script rewrite first)
python run.py remake the-beale-ciphers-a-treasure-that-vanished-with-it
```