# Expressive voice test environment and agent integration (23 Nov 2026)

Owner approvals used: A (isolated Chatterbox-Turbo test environment), B (minimal skill references in playbooks/creator.md and playbooks/qa.md). No application code, provider, production setting or production asset was changed. Nothing committed. The Mary Celeste film and its assets were not touched (no job was running).

## Results
| Item | Status | Evidence |
|---|---|---|
| Isolated environment installed | PASS | `/home/fahad/voice-lab/.venv` (Python 3.11.17 via uv), outside ~/studio |
| Environment verified (load + speech, built-in voice) | PASS | `voice-lab/samples/smoke/smoke_report.json`: load 17.5 s, two clips, full decode ok |
| Five skills validated | PASS | `pytest -q tests/test_skills.py`: 68 passed; names, frontmatter, links, code names all checked |
| Skill defect fixed | PASS | human-like-tts-production: Turbo row (19 tokenizer tags, not 3) and "Turbo ignores exaggeration/cfg_weight" |
| Playbook references added (approved) | PASS | creator.md and qa.md, `## Tools`, one line each (diff below) |
| Agent loader passes the skill instructions to models | FAIL (by design of the loader) | `voice-lab/tests/loader_test.py`: 0 of 4 / 0 of 1 skill names in what models receive |
| Test plan ready | PASS | `voice-lab/plan/voice_test_plan.json`, generator `voice-lab/tests/generate_samples.py` |
| Generator refuses without the owner's voice | PASS | `--check` and `--approval`: "REFUSED: missing ...", exit 1, no clip made |
| Owner recordings | BLOCKED | `voice-lab/recordings/` is empty |
| Owner samples, listening, voice approval | WAITING FOR OWNER | needs recordings |

## Environment
- Path: `/home/fahad/voice-lab` (`.venv`, `hf` model cache via `HF_HOME`, `recordings`, `samples`, `plan`, `tests`).
- Versions: torch 2.6.0+cpu, torchaudio 2.6.0+cpu, chatterbox-tts 0.1.7 (MIT; installed without its optional gradio, pykakasi and spacy-pkuseg), transformers 5.2.0, diffusers 0.29.0, librosa 0.11.0, numpy 1.26.4, s3tokenizer 0.3.0, resemble-perth 1.0.1, setuptools 80.10.2.
- One install fault found and fixed: resemble-perth imports `pkg_resources`; uv venvs have no setuptools, so the watermarker was None and the model would not load. Fix: `setuptools<81` in the voice-lab venv only.
- Disk: 5.2 GB in total (venv 1.5 GB, weights 3.8 GB: `from_pretrained` downloads every safetensors file, both s3gen variants). Measured free space before/after: 256.27 GB -> 251.21 GB. My earlier 2 to 3 GB estimate was low.
- Hardware: CPU only. The GTX 1050 Ti has about 2.7 GB free beside the desktop; the weights alone are about 3 GB, so it was not used (not tested on GPU).
- Measured on CPU (6 threads, built-in voice): real-time factor 19.1 and 15.6 (3.4 s of audio in 65 s; 4.76 s in 74 s), peak RAM 5.98 GB. Estimates from that: the 24 test clips about 30 minutes; a 22-minute narration about 6 hours.
- Every output carries Resemble AI's PerTh watermark: detected 1.0 on both smoke clips.
- The smoke clips use the model's built-in voice and say only that the install works. No quality or emotion claim is made from them.

## Model facts (official card, tokenizer and code)
- Licence MIT (PyPI, GitHub LICENSE, model card). English only. Reference clip must be over 5 s.
- Tokenizer tags: style `[narration] [dramatic] [happy] [angry] [fear] [surprised] [whispering] [crying] [sarcastic] [advertisement]`; events `[laugh] [chuckle] [cough] [sigh] [gasp] [sniff] [groan] [shush] [clear throat]`. The README documents only laugh, chuckle and cough; the others are unverified until heard.
- Turbo ignores `exaggeration`, `cfg_weight`, `min_p` (its code logs this). Emotion comes from tags and from the reference clip's own style.

## Agent integration
Diff (the only playbook changes):
```
creator.md, ## Tools:
+Voice skills (.claude/skills/): before narration expressive-voice-director and documentary-voice-acting; when lines are made or resumed human-like-tts-production and voice-recovery-and-checkpoint.
qa.md, ## Tools:
+Voice skill (.claude/skills/): voice-emotion-evaluator when checking generated narration.
```
Loader test (`~/studio/.venv/bin/python -I ~/voice-lab/tests/loader_test.py`, read-only):
```
creator: references in playbook Tools: True; problems(): none
  sent with every model call (inject, Role+Never, 650 chars): 377 chars, skills named: []
  long brief (Role, Goal, How, Never, 1500 chars): 1487 chars, skills named: [], ends with Never intact: True
qa: references in playbook Tools: True; problems(): none
  sent with every model call (inject, Role+Never, 650 chars): 196 chars, skills named: []
  long brief (Role, Goal, How, Never, 1500 chars): 455 chars, skills named: [], ends with Never intact: True
IF in Role: inject carries the names: True; long brief 1495 chars keeps the whole Never section: False
```
Why integration through playbooks cannot work:
1. `playbook.inject` sends only Role + Never (650 chars) with each model call; `brief` (Role, Goal, How, Never) is used only by escalate, seo, scriptreview and doctor prompts. `Tools` never reaches a model.
2. Putting the line in Role would carry the names but cut the creator's Never section out of its brief (1,495 chars), breaking the existing safety check (test_agents_training).
3. Even a name in a prompt is not the skill: the worker's models cannot open files.
4. The narration step (`tts.py`) makes no model call at all, so no agent instruction can change the voice today.
Today the skills work in Claude Code sessions started in ~/studio (the existing discovery mechanism), and the playbook line tells a person or a session which skill belongs to which agent.

Smallest additional change that would make it real (application code: needs the owner's approval, best done once a voice is chosen):
- A voice-direction step in the documentary producer: one model call as the creator agent, with the expressive-voice-director skill text and the script, writing `delivery.json` (the shared schema); and a voice backend that reads it (tags, pauses) for the approved engine. Per CLAUDE.md it needs tests, an agenteval case and a mutation check. Not started.

## Recordings (missing)
Place in `/home/fahad/voice-lab/recordings/`: `ref_neutral.wav` (required, over 5 s, 20 to 30 s best), optional `ref_warm.wav`, `ref_tense.wav`, `ref_excited.wav`, `ref_laugh.wav`, and `PERMISSION.txt`. Texts are in reports/VOICE_RECORDING_GUIDE_2026-11-23.md (a "Where to put the files" section was appended). Three older files named ref_voice.wav / ref_clean.wav exist in ~/video-studio and ~/AI_Video_Studio: not used, speaker and permission unknown.

## Test plan (ready, not run)
12 emotions (neutral, excitement, happiness, sadness, empathy, suspense, fear, curiosity, surprise, whisper, laughter, reflective), each made twice ("plain" and with its tag) from the same owner reference, so a listener can hear whether a tag changes anything. Per clip: text, intended emotion, tag, model and package version, temperature, reference sha256, sha256, objective measurements (duration, peak and RMS dBFS, lead/tail silence, words per minute, pitch range in semitones, clipping) and an empty listening form. Approval subset: neutral, excitement, sadness, suspense, laughter. Clips are written .part then renamed and kept on resume (voice-recovery-and-checkpoint).

## Commands run
- `pytest -q tests/test_skills.py` -> 68 passed (after the skill fix)
- `pytest -q tests/test_agents_training.py tests/test_skills.py` -> 157 passed (with the playbook edits)
- `generate_samples.py --check` / `--approval` -> REFUSED, exit 1
- smoke test -> exit 0 (second run, after the setuptools fix; first run failed on the watermarker import)

## Remaining blockers and approvals
1. BLOCKED: the owner's recordings and permission file.
2. WAITING FOR OWNER: listening to the approval samples and choosing (or rejecting) the voice.
3. WAITING FOR OWNER: the voice-direction step and voice backend (application code), after a voice is chosen.
4. Limits: CPU only (slow); English only; tag effects unverified; watermark present in every clip.
