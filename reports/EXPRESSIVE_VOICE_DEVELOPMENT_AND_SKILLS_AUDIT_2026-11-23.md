# Expressive voice development and voice skills audit (23 Nov 2026)

Scope: read-only audit, legal and technical research, five new skills (skill files only). No application code, configuration, provider, agent or production asset was changed. Nothing committed.

## 1. Existing voice system (read from the code)
- Engine: Microsoft Edge online voices through `edge_tts` (`tts.py`). Channel voice `en-US-AndrewMultilingualNeural` (owner's choice, 30 Oct 2026).
- Emotion control today: none beyond rate and pitch. `tts.VOICE_STYLES["energetic"]` lifts rate/pitch for a Short's hook, questions, payoff and invitation (`tts.line_prosody`). Documentaries use the default calm voice.
- Pronunciation: `tts.PRONUNCIATION` respells names sent to the voice only (one entry: Amun).
- Recovery: per-line `lineNN.mp3` + `lineNN.json` (text hash, word timings), `.part` never used, `tts.LINE_TIMEOUT` 120 s per line, stage markers in `work/checkpoint.json`.
- Checks: `voicecheck.py` (an audio model transcribes without the script; differences show skipped or repeated words). Voice tests: test_tts_timeout, test_voicecheck, test_voice_record, test_voice_tail, test_voice_wiring.
- Recordings: none from the owner. Existing audio: Kokoro and Edge samples in ~/Music/voice-samples-22nov (built-in voices, not the owner's). Mary Celeste narration: 104 Edge lines, valid, kept.

## 2. Kaggle terms and suitability
- Kaggle Terms of Use (22 Jun 2025, read in the browser 23 Nov, quoted in reports/KAGGLE_GPU_RESEARCH_2026-11-23.md): "You will only use the Services for your own internal, personal, non-commercial use".
- A monetized channel is commercial. Training or adapting the channel's narrator on Kaggle, then using it on the channel, conflicts with that sentence however the weights are licensed. Verdict: NOT SUITABLE for this purpose; not used. (The owner's Kaggle competitions in ~/kaggle-work are personal use and unaffected.)
- Other facts (secondary sources, not re-read today): 30 GPU hours a week, 12 h sessions.

## 3. Model comparison (official model cards on Hugging Face, read 23 Nov)
| Model | Weights licence | Emotion | Vocal events | Cloning | Languages |
|---|---|---|---|---|---|
| ResembleAI/chatterbox-turbo (350M) | MIT | none by instruction | native [laugh], [chuckle], [cough] | zero-shot from a reference clip | English |
| ResembleAI/chatterbox (500M) | MIT | exaggeration and CFG settings | none listed | zero-shot | English |
| Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice | Apache-2.0 | natural-language instructions (emotion, tone, pace) | none listed | preset voices only | 10, no Bengali |
| Qwen/Qwen3-TTS-12Hz-1.7B-Base | Apache-2.0 | none (no instruction control) | none listed | 3-second clone; fine-tunable | 10, no Bengali |
| nari-labs/Dia-1.6B | Apache-2.0 | audio-conditioned | (laughs), (sighs), (gasps)... "might result in unexpected output" | audio prompt | English |
| zai-org/GLM-TTS | MIT (metadata) | not read | not read | zero-shot | zh, en |
| IndexTeam/IndexTTS-2 | no licence tag | not read | not read | | NOT usable until its licence is read |
Licences above are the model-card metadata; the full licence files and the training-data terms must be read before production use. No model lists Bengali.

## 4. Selected approach (pending the owner's ear)
No training. Zero-shot cloning of the owner's own recordings, run on this PC, with delivery notes from the director skill:
- First choice to test: Chatterbox-Turbo (MIT, the only one with documented native laughs/chuckles, small enough for this PC) for the owner's voice.
- Second: Qwen3-TTS-Base clone (Apache-2.0) for quality comparison; its emotion instructions only work on preset voices, so with the owner's voice emotion comes from pacing and text only, unless a later fine-tune (owner approval, local GPU too small: 4 GB GTX 1050 Ti) adds it.
- Dia-1.6B as a check of vocal events.
A real sample decides, not this table.

## 5. Recording requirements
reports/VOICE_RECORDING_GUIDE_2026-11-23.md: five short files (main 20 to 30 s neutral), quiet room, WAV if possible, plus a one-line permission statement. Status: NOT RECEIVED.

## 6. Training or adaptation progress
None run. Nothing installed. Status: WAITING FOR OWNER APPROVAL (dependencies) and BLOCKED (recordings).

## 7. Licences
See section 3. Training datasets of these models were not reviewed (not needed for inference from the owner's own voice; needed before any fine-tune).

## 8 and 9. Created skills (all in ~/studio/.claude/skills/)
| Skill | Purpose |
|---|---|
| expressive-voice-director (+ references/delivery-schema.md) | whole-script reading, line-level emotion, pace, pauses, emphasis, rare vocal events |
| human-like-tts-production | approval gate, what each model really supports, line-by-line generation that keeps valid lines |
| voice-emotion-evaluator | objective measurements kept apart from human listening; no invented scores |
| documentary-voice-acting | narration craft for history, mystery, suspense, tragedy, discovery, legend, endings |
| voice-recovery-and-checkpoint | resume rules matching the studio's line records and checkpoints |
Test: `.venv/bin/python -m pytest -q tests/test_skills.py` -> 68 passed (5 new skills included: `-k` selection, 5 passed).

## 10. Agent assignments: WAITING FOR OWNER APPROVAL
Fact: the worker's agents never read SKILL.md; they read only `playbooks/<agent>.md` (`playbook.py`). The new skills are discoverable today by Claude Code sessions started in ~/studio (the existing mechanism). Not by Autopilot.
Proposed change (not made): add one line to the `## Tools` section (not pasted into prompts, so the 1,500-character brief is unaffected) of playbooks/creator.md ("voice: skills expressive-voice-director, human-like-tts-production, voice-recovery-and-checkpoint") and playbooks/qa.md ("voice-emotion-evaluator"). Even then, a new voice engine needs a `tts.py` backend: application code, a separate approval.

## 11. Voice evaluation results
NOT TESTED: no approved model installed and no recordings. The evaluation lines are in the brief and the recording guide.

## 12. Autopilot integration
NOT TESTED for a new voice (no engine). Existing voice path: verified working today (104 lines made for the Mary Celeste film, resumed after a power cut with 143/143 fingerprints unchanged).

## 13. Mary Celeste
Film made (1181.5 s, BT.709), not ready: review unavailable (Gemini 503), 54 different pictures for 104 scenes, a wrong SEO title. Owner chose to re-voice after approving a sample. Current narration untouched.

## 14. Commands and outputs
- `pytest -q tests/test_skills.py`: 68 passed.
- Model facts: Hugging Face model cards (hf://models/<id>/README.md) and metadata, 23 Nov.

## 15. Outstanding approvals
1. Install a local test environment (a separate venv outside the studio, PyTorch + chatterbox-tts, about 2 to 3 GB; CPU or the 4 GB GPU).
2. The owner's recordings and permission line.
3. Playbook lines connecting the skills to agents (section 10).
4. Later: a `tts.py` backend for the chosen model (application code).

## 16. Limitations
Every capability above is from model cards, not heard. No listening test has been done. Bengali is not supported by the candidates. The 4 GB GPU limits fine-tuning; CPU inference will be slow (to be measured).
