---
name: human-like-tts-production
description: "Use when narration is generated with an expressive voice model: one approved speaker for the whole video, delivery notes turned into the model's real controls, pronunciation, only failed lines redone, valid lines kept. Never used for production before the owner approved a sample."
---

# Human-like TTS production

## Responsibility
Make narration from a script plus delivery notes (expressive-voice-director) with the ONE voice the owner approved.

## Gate (all must be true, or stop and ask)
1. The owner heard a real sample and approved the model and the voice in writing.
2. The speaker is the owner's own recorded voice, or a voice with written permission ([the recording guide](../../../reports/VOICE_RECORDING_GUIDE_2026-11-23.md)).
3. The model's weight licence allows commercial use, read on its official model card.
4. Nothing is trained or run for the channel on Kaggle (its terms: personal, non-commercial use only).

## What each candidate can really do (official model cards, read 23 Nov 2026)
| Model | Weights | Controls that exist | Vocal events |
|---|---|---|---|
| ResembleAI/chatterbox-turbo (350M) | MIT | zero-shot clone from a reference clip (needs one); its tokenizer (added_tokens.json) also has style tags `[narration]` `[dramatic]` `[happy]` `[angry]` `[fear]` `[surprised]` `[whispering]` `[crying]` `[sarcastic]` `[advertisement]`, NOT documented in the README: effect unverified until heard | README: `[laugh]`, `[chuckle]`, `[cough]`; tokenizer also `[sigh]` `[gasp]` `[sniff]` `[groan]` `[shush]` `[clear throat]` |
| ResembleAI/chatterbox (500M) | MIT | zero-shot clone, exaggeration and CFG | none listed |
| Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice | Apache-2.0 | natural-language emotion and pace instructions, preset voices only | none listed |
| Qwen/Qwen3-TTS-12Hz-1.7B-Base | Apache-2.0 | 3-second clone, fine-tuning; no instruction control | none listed |
| nari-labs/Dia-1.6B | Apache-2.0 | audio-prompt clone, dialogue | `(laughs)`, `(sighs)`, `(gasps)` and more, "might result in unexpected output" |
None lists Bengali. A control not in this table is not claimed.

Every Chatterbox output carries Resemble AI's imperceptible PerTh watermark (README); YouTube's altered or synthetic content disclosure still applies.

## Mapping for Chatterbox-Turbo (to be confirmed by listening, line by line)
Turbo ignores `exaggeration`, `cfg_weight` and `min_p` (chatterbox-tts 0.1.7 `tts_turbo.py` logs that they are not supported); its reference clip must be longer than 5 s. For an exaggeration control use the 500M Chatterbox instead.
emotion fear -> `[fear]`, surprise -> `[surprised]`, happiness/excitement -> `[happy]`, sadness/grief -> `[crying]` only at a scene's peak and only if it sounds restrained, suspense/serious -> `[dramatic]` or `[narration]`, whisper -> `[whispering]`; vocal_event laugh/chuckle/sigh -> the tag of the same name. A tag that does not change the audio, or overacts, is dropped and the delivery is carried by pauses and pacing.

## Steps
1. Map each delivery note to a control the chosen model really has (an instruction, an exaggeration value, a tag, a pause). Anything else is done by pauses and pacing, and reported as not supported.
2. Generate line by line. Each line is saved with its text hash and settings (the studio's pattern in `tts.py`: a line file plus a record), so a cut keeps every finished line (voice-recovery-and-checkpoint).
3. Apply respellings only to the text sent to the voice; captions keep the real spelling.
4. After each line: duration, peak level, silence at the ends; a line that fails is redone once with the same settings, then reported. Never redo a valid line.

## Safety
No production run before the gate. Same speaker in every line of a video. No paid service without the owner's approval. Never overwrite a video's existing narration; a new narration goes in a new folder until approved.
