# Recording your narrator voice (23 Nov 2026)

Why: an expressive voice model can copy a voice from a short recording, with no training (zero-shot cloning: Chatterbox, MIT; Qwen3-TTS, Apache-2.0).
Only YOUR voice, or a voice whose owner gave written permission, may be used. Kaggle is not used for this (its terms allow personal, non-commercial use only).

## What to record
- A quiet room (no fan, no echo: a room with a bed, curtains or clothes is better than a bare room). Phone 20 to 30 cm from your mouth, not too close.
- Phone voice recorder or Audacity. Save as WAV if you can (otherwise the best quality your phone offers). One file per item below.
- Speak in your normal storytelling voice. Do not act more than you would in a real documentary.

1. `ref_neutral.wav` (the main one, 20 to 30 seconds): read slowly and calmly:
   "This is my own voice, recorded for my YouTube channel on the twenty-third of November. The sea was calm that morning, and the ship moved slowly across the water. Nobody on the shore could have guessed what the sailors would find. Some stories are told so often that the truth is almost forgotten."
2. `ref_warm.wav` (10 to 15 s): "Imagine waiting for someone you love, knowing they may never return. That is how the families must have felt."
3. `ref_tense.wav` (10 to 15 s): "Something was moving below the deck. Nobody knew what was waiting. And then, without warning, everything changed."
4. `ref_excited.wav` (10 s): "Against every expectation, they had finally found the missing evidence!"
5. `ref_laugh.wav` (optional, 5 to 10 s): say a line and laugh only if it comes naturally: "And the newspaper printed it as fact. Live chickens, on a ghost ship."

## Permission line (write it in your reply or a text file next to the recordings)
"I, the owner of this channel, recorded these files in my own voice and allow my studio to use them to make narration for my videos."

## What happens next
I check the files (noise, clipping, length), make the same ten test lines in each model with your voice, and give you the samples to listen to. Nothing goes into a video until you choose a sample. The Mary Celeste film is then re-voiced (all 104 lines) with the voice you pick.

## Where to put the files (added 23 Nov 2026, 17:30 UTC)
Put them in **`/home/fahad/voice-lab/recordings/`** (the folder exists and is empty):
- `ref_neutral.wav` (required; must be longer than 5 seconds, 20 to 30 s is best; the tool refuses a clipped or noisy file and says why)
- `ref_warm.wav`, `ref_tense.wav`, `ref_excited.wav`, `ref_laugh.wav` (optional, used to compare which reference gives the best acting)
- `PERMISSION.txt` with the permission line above, in your own words.
Then tell me "recordings ready". The first command only checks the files: `~/voice-lab/.venv/bin/python -I ~/voice-lab/tests/generate_samples.py --check`.
Files in other projects (~/video-studio/projects/voice/ref_voice.wav, ref_clean.wav and ~/AI_Video_Studio/cloud/colab_inputs3/ref_voice.wav) are NOT used: I do not know whose voice they are.
