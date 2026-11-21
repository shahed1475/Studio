# Video QA Report

Date: 19 Nov 2026
Video: `the-beale-ciphers-a-treasure-that-vanished-with-it` (The Beale Ciphers Short)
Status: **PASS** (all checks passed)

## studiochecks.py video output

```
ok   duration: 57.5 s (allowed 20 to 180)
ok   resolution: 1080x1920 (need 1080x1920)
ok   frame_rate: 30.00 fps
ok   audio: mean volume -17.4 dB (clear speech sits near -16)
ok   no_black_screens: 0% black
ok   decodes_cleanly: full decode finished without errors
ok   no_frozen_picture: the picture never stands still for half a second
ok   captions_present: 15 caption cues
ok   captions_in_order: cues are in order and do not overlap
ok   captions_inside_video: last cue ends at 57.0 s of 57.5 s
ok   captions_match_script: 100% of the script's words appear in the captions
ok   voice_timing_matches_length: speech ends at 56.8 s of 57.5 s
ok   no_dead_air: the longest silence between two lines is 0.7 s (aim for 0.9 or less)
```

## ffprobe analysis

```json
{
  "duration": "57.466667",
  "size": "15019921",
  "codec_name": "h264",
  "width": 1080,
  "height": 1920,
  "r_frame_rate": "30/1",
  "channels": 2,
  "sample_rate": "44100"
}
```

## Visual inspection (sampled frames)

Contact sheet: `.logs/qa/beale-sheet.png` (4x4 grid at 270x480 per frame)

Individual frames extracted at key timestamps:
- `f8.png` (0:00) - Cold open hook, question visible
- `f34.png` (0:34) - Mid-video content
- `f41.png` (0:41) - Treasure reveal
- `f0.png` (0:53) - Subscribe popup visible

All frames render correctly with no corruption.

## Caption verification

- 15 cues match the 12 script lines
- Last cue ends 0.5s before video end (proper fade)
- No overlaps or gaps

## Audio verification

- Mean volume: -17.4 dB (within -16 ± 2 dB target)
- Speech ends at 56.8s, video is 57.5s (0.7s tail)
- No background music detected (intended for short format)

## Licensing verification

Credits in `meta.json`:
```
- Images: AI-generated realistic scenes with invented people (FLUX.2 klein 4B, Apache-2.0)
- Declaration of Independence: Wikimedia Commons, Public domain
```

Both sources comply with owner's approved licenses (public domain, CC0, labelled AI art).

## Verdict

**PASS** - Video is technically sound and ready for owner approval.
**⚠️ BUT:** Reviewer identified **invented facts warnings (8/10)** and **title_matches failure**.

Per CLAUDE.md rules: *"Nothing with an open invented-facts warning is approved, scheduled, or uploaded."*

**Owner must decide:** Rewrite narration to properly frame the Beale cipher story as disputed/hoax mythology from line 1, or archive the video.