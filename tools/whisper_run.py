"""Transcribe one audio file with faster-whisper (MIT, local, CPU) and print the text. Run as a separate process by voicecheck.whisper_text, because the project's own
filelock.py would otherwise hide the real `filelock` package that Hugging Face's downloader needs. The audio is decoded by ffmpeg to 16 kHz mono floats here (the PyAV
installed with faster-whisper rejects an argument its own code passes). Usage: python tools/whisper_run.py FILE.mp3 [MODEL]"""
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", sys.argv[1], "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, dtype=np.float32)
model = WhisperModel(sys.argv[2] if len(sys.argv) > 2 else "small.en", device="cpu", compute_type="int8")
segs, _ = model.transcribe(audio, language="en", beam_size=1, temperature=0, condition_on_previous_text=False)
print(" ".join(x.text.strip() for x in segs))
