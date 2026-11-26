# Own avatar channel: research (23 Nov 2026)

Owner's ask: from a video of himself with his voice, make a YouTube channel presented by his own AI avatar (cloned face and voice, perfect lip-sync, professional studio background), using Kaggle's free GPU.

## Licences (Hugging Face metadata read 23 Nov 2026)
| Job | Model | Licence | Note |
|---|---|---|---|
| Voice clone | ResembleAI/chatterbox | MIT | multilingual, voice cloning |
| Voice clone | microsoft/VibeVoice-1.5B | MIT | long-form speech |
| Voice clone | IndexTeam/IndexTTS-2 | none shown | not usable until checked |
| Lip-sync on real footage | ByteDance/LatentSync-1.6 | OpenRAIL++ | commercial allowed with use restrictions |
| Lip-sync on real footage | TMElyralab/MuseTalk | MIT | real-time class |
| Avatar from photo | MeiGen-AI/InfiniteTalk | Apache-2.0 | Wan 2.1 based, any length, in Wan2GP |
| Avatar from photo | Wan-AI/Wan2.2-S2V-14B | Apache-2.0 | speech to video |
| Avatar from photo | BadToBest/EchoMimicV3 | Apache-2.0 | 1.7B, light |
| Avatar from photo | fudan-generative-ai/hallo3 | MIT | |
| Avoid | MiniMax H3 (Ref2VA, audio-to-video) | MiniMax H3 Community | excludes US/EU/UK/Korea incl. outputs |
| Avoid | tencent/HunyuanVideo-Avatar | none shown here | not checked |

## Findings
- Technically possible: clone voice, then either re-sync the lips of real footage (most realistic) or animate a still photo (more freedom, more AI look). No open model is "perfect": long videos need chunking; teeth, hands and colour drift over a minute are known weak spots (InfiniteTalk FusionX LoRA colour shift over 1 min, third-party review).
- T4 speed for these models: no benchmark found; needs a test.
- Kaggle: a monetized channel is commercial use; Kaggle terms (22 Jun 2025) allow "internal, personal, non-commercial use" only. Testing is fine; production needs a GPU whose terms allow commercial use.
- YouTube (third-party sources only, official page not read): own face and own cloned voice are reported as monetizable with the altered or synthetic content disclosure; mass-produced or repetitive AI content risks demonetization of the whole channel.

## Test plan (when the owner sends the footage)
1. Footage: 1-2 min, face the camera, even light, quiet room, plain wall or green screen, 1080p; plus 30-60 s of clean speech.
2. Voice: Chatterbox clone, compare with the real voice.
3. Avatar A: LatentSync 1.6 and MuseTalk re-syncing the real footage to the cloned speech.
4. Avatar B: InfiniteTalk from one frame of the footage.
5. Background: green-screen key or matting onto a studio plate drawn on the free Cloudflare account.
6. Judge side by side: lip-sync, teeth, eyes, identity, colour, speed per minute of video on 2 x T4.
Owner's footage is private: kept on the PC or a private Kaggle dataset, never in git or a public place.
