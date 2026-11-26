# Kaggle GPU + MiniMax H3 notebook: test and research (23 Nov 2026)

Owner's ask: use the Kaggle notebook "MiniMax H3 + Open-H3 Regenerate 2K" (AIQUEST) as the studio's GPU for video clips, keep it always live, studio uses it when needed. The owner's PC GPU (GTX 1050 Ti, 4 GB) cannot be upgraded.

## Test (done, 23 Nov 03:04 UTC)
- Account `shahedalfahad` (Browser 1): phone and identity verified; GPU 8:28 of 30 h used this week before the test.
- Notebook run had downloaded 41.1 GB of weights in 3 min (MiniMax-H3 FL2VA pruned INT8 21.1 GB, Qwen3-VL-32B GGUF 14.6 GB, video VAE 2.8 GB, audio VAE 0.6 GB, PDMD 4-step LoRA 1.4 GB, latent upscaler 0.7 GB, Open-H3 refiner LoRA converted to INT8 3.1 GB) into `/kaggle/tmp` (wiped when the session ends). Engine load 161 s on 2 x T4.
- Test prompt (no people): misty hilltop at dawn, 1867 Mexico, stone wall, slow dolly. Result: 672x384, 5.2 s, seed 213090323, **112 s** (prompt 8 s, denoise 82 s at 20.6 s/step, VAE + audio 21 s). File `/kaggle/working/outputs/h3_preview_20261123_030444_seed213090323.mp4` (on Kaggle, not downloaded).
- Seen: the first frame only (dry hilltop, rock wall, scrub trees, overcast sky; matches the prompt). Not seen: motion, audio, the rest of the clip. Not tested: 720p/1080p/2K upscale.
- The Gradio UI is public on a trycloudflare.com address with **no login**: anyone with the link can spend the account's GPU quota.

## Blocker 1: Kaggle Terms of Use (version 22 Jun 2025, active; read in the browser 23 Nov)
> "You will only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party"

A monetized YouTube channel is commercial use. Using Kaggle compute to make the channel's clips conflicts with this sentence, whatever else Kaggle is used for. Breach is grounds for termination ("Kaggle has the sole right to decide whether you are in violation"). Same finding as 21 Nov (AI Factory: Kaggle switched off in policy.json).

## Blocker 2: MiniMax H3 Community License (LICENSE in MiniMaxAI/MiniMax-H3, 2 Aug 2026)
- "Excluded Territories" = the European Union, the United Kingdom, the Republic of Korea and the United States.
- V.4: "You may not use, reproduce, modify, distribute, or display the MiniMax H3 Works or any of their Outputs or results outside the Applicable Territory."
- A public YouTube video is shown in the US, EU, UK and Korea, so publishing H3 output on the channel very likely falls outside the licence. This is our reading, not legal advice. Kaggle's servers are Google's; where they run is unverified.
- Also: AUP 12 requires clear disclosure that content is machine-generated; IV.2 asks commercial products to display "MiniMax H3"; outputs are not claimed by MiniMax (VI.4).
- Open-H3-Regenerate-2K (NVIDIA, Efficient-Large-Model) follows the same licence; its merged LoRA also contains LightX2V Turbo and LMS Sharp, and the latent upscaler comes from LBH-123-AI, each under its own licence (not checked).
- Qwen3-VL-32B-Instruct: Apache-2.0 (fine).

## "Always live" is not possible on Kaggle
Weekly GPU quota 30 h (168 h in a week), session cap 12 h (secondary sources, not yet read on Kaggle's docs page), idle sessions stop. Keep-alive scripts or extra accounts would break the terms (one account per person is stated in the terms). The only sound pattern on any free GPU is on demand: start, make a batch, save, stop.

## Legal routes to more GPU (to verify before building)
| Route | Licence of model | Cost | Status |
|---|---|---|---|
| Wan 2.2 (Wan-AI/Wan2.2-T2V-A14B, TI2V-5B) | Apache-2.0 (HF metadata) | - | model OK for commercial use |
| Modal Starter plan | - | $0 plan + $30/month free credits (pricing page snippets; T4 $0.59/h, A100 40GB $2.10/h) | commercial-use terms and card requirement NOT verified |
| Hugging Face ZeroGPU (free) | - | about 5 GPU-min a day | too small for video |
| Current studio path: Cloudflare FLUX.2 pictures + parallax | Apache-2.0 | $0 | working today |

## Owner decisions
1. Accept or reject using Kaggle for channel work given the non-commercial clause (recommendation: reject).
2. Accept or reject MiniMax H3 output on a worldwide channel given the territory clause (recommendation: reject).
3. If a paid-credit route is wanted: allow research of Modal's terms and a Wan 2.2 batch worker design (plan, playbook, agenteval case, mutation check, as CLAUDE.md requires).
4. Stop the Kaggle session when not in use: the public link has no password and the session spends GPU hours.

Sources: kaggle.com/terms (browser, 23 Nov); hf://models/MiniMaxAI/MiniMax-H3/LICENSE; hf://models/Efficient-Large-Model/Open-H3-Regenerate-2K/README.md; HF metadata for Qwen/Qwen3-VL-32B-Instruct and Wan-AI/Wan2.2-T2V-A14B; modal.com/pricing (search snippets); huggingface.co/docs/hub/spaces-zerogpu (search snippets).
