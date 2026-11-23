# Line-level delivery schema (shared by the voice skills)

One JSON object per narration line, in script order. The script text is never changed by this layer.

```json
{
  "line": 12,
  "text": "Her cargo of alcohol was intact.",
  "scene_context": "the boarding party finds the ship deserted",
  "emotion": "curiosity",
  "emotion_intensity": 0.4,
  "delivery_style": "calm, intriguing",
  "speaking_rate": "moderate",
  "pause_before": 0.2,
  "pause_after": 0.6,
  "emphasis": ["intact"],
  "pronunciation": {"Dei Gratia": "DAY-ee GRAH-tee-ah"},
  "vocal_event": null,
  "speaker_id": "owner-v1",
  "audio_path": null,
  "evaluation": null
}
```

## Allowed values
- `emotion`: neutral, curiosity, suspense, fear, sadness, empathy, surprise, excitement, happiness, calm, reflective, serious. One per line.
- `emotion_intensity`: 0.0 to 1.0. Documentary default 0.3; above 0.7 only for a scene's single peak.
- `speaking_rate`: slow, moderate, brisk.
- `pause_before` / `pause_after`: seconds, 0 to 1.5.
- `vocal_event`: null, laugh, chuckle, sigh, breath, whisper. Only where the model card lists it as supported (see human-like-tts-production) and the scene justifies it; never in tragic or serious scenes.
- `speaker_id`: the one approved voice for the whole video. Never changes inside a video.
- `audio_path`, `evaluation`: filled by production and evaluation, never by the director.
