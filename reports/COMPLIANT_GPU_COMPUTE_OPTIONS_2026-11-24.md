# Compliant GPU and compute options for the studio (24 Nov 2026)

Question: which lawful, free (or clearly priced) compute can run the owner's already-downloaded models, or otherwise finish the Seven Sleepers documentary fast?
Method: each provider's own current page, read in the owner's Chrome (signed out, read only) or through its public API; local hardware measured with nvidia-smi and /proc/meminfo; model licences matched by SHA-256 against Hugging Face. "Not verified" means exactly that. Model choice and compute choice are kept separate (see reports/DOWNLOADED_MODEL_INVENTORY_2026-11-24.md for the models).

## Comparison

| Option | Runs the owner's own model files? | GPU memory | Session limit | Storage / checkpoints | Free allowance (verified?) | Commercial output allowed? | Payment |
|---|---|---|---|---|---|---|---|
| **This PC, GPU** (GTX 1050 Ti) | Yes: Ollama (GGUF), stable-diffusion.cpp (Z-Image Turbo GGUF, measured) | 4 GB (about 3 GB free with the desktop running) | none | local disk, 234 GB free; studio caches are the checkpoints | unlimited (electricity) | Yes for Apache-2.0 / MIT weights; three Z-Image files verified Apache-2.0 by SHA-256 today | none |
| **This PC, CPU** | Yes (Ollama, llama.cpp); diffusion too slow to matter | 23 GB RAM (13 GB available) | none | as above | unlimited | as above | none |
| **VPS** | n/a | n/a | n/a | n/a | **No VPS exists** (deleted by Hostinger 17 Nov 2026) | n/a | n/a |
| **Kaggle Notebooks** (T4 x2) | Technically yes (upload as a private dataset/model) | 2 x 16 GB (announcement 735239) | 12 h a session (docs) | 20 GB saved output (docs) | 30 h a week "or sometimes higher" (docs, verified) | **No without written permission**: Terms say "internal, personal, non-commercial use"; AUP bars "activity unrelated to ML data science" and "server farming" | none |
| **Google Colab, free tier** | Technically yes | not published ("GPU types available... vary over time") | not published | VM disk, lost at end | **No published allowance** ("dynamic usage limits", FAQ, verified); content generation through a web UI is "outside our priorities" for the free tier | commercial terms not checked today | free tier; paid plans exist |
| **SageMaker Studio Lab** | - | - | - | - | **Closed**: "no longer open to new customers" (FAQ banner, verified) | - | - |
| **Lightning AI** | - | - | - | - | **Not available here**: "hasn't expanded to your area yet" (pricing page, verified) | - | - |
| **Cloudflare Workers AI** (already used) | No (Cloudflare's hosted models only) | n/a | n/a | n/a | **10,000 Neurons a day free, reset 00:00 UTC** (pricing page, verified); FLUX.2 klein 4B costs 26.05 Neurons per 512x512 output tile = about 104 a 1024x576 picture, 156 a 704x1248 picture | FLUX.2 klein **4B** is Apache-2.0 (Hugging Face card, verified); the studio calls 4B. (klein **9B** is non-commercial: never switch to it) | free plan; paid only if the owner signs up for Workers Paid |
| **Free text APIs** (owner's Gemini key, FreeLLMAPI proxy, OpenRouter free models) | No (hosted models) | n/a | n/a | n/a | per-provider limits (already handled by `llm.py` routing) | per provider; used for scripts' fact-checks, not for pictures | free tiers only (Free Mode) |
| Hugging Face ZeroGPU Spaces | - | - | - | - | **Not verified** (not checked today) | not verified | not verified |

## Conclusion and chosen route
1. **Kaggle is not used for any production asset.** Its current terms do not allow commercial use, and generating media for a monetised channel is not "ML data science". A permission request is drafted (reports/KAGGLE_COMMERCIAL_USE_PERMISSION_REQUEST.md) and NOT sent. Personal, non-commercial experiments (testing a model, benchmarks) would fit Kaggle's terms but must stay separate from channel assets.
2. **Fastest lawful route for the Seven Sleepers film: Cloudflare Workers AI's free daily allowance for the film's pictures, this PC for voice, render and checks.** The film's existing pictures are FLUX.2 klein drawings, so the new ones keep one look and one credit line; about 30 to 50 new pictures cost about 3,100 to 5,200 Neurons, inside one free day. The allowance resets at 00:00 UTC (it is spent for 24 Nov).
3. **The owner's own downloaded models are used where they fit:** Z-Image Turbo (Apache-2.0, verified) on this PC's GPU draws the Mary Celeste Short's corrected opening picture now, through the studio's existing spec route (`tools/zimage_batch.py`, `ccbuild`), with the credit line naming it. Drawing all 30 to 50 film pictures locally was rejected: about 5 to 10 minutes a picture at this GPU (4 to 8 hours), no faster than the 00:00 UTC reset, and a second look and credit inside one film.
4. **No paid compute, no paid API.** Nothing in this route spends money.
5. A future Kaggle worker stays as designed and switched off (`config/compute.json` `kaggle.enabled: false`, `computerouter.kaggle_gate`): finite sessions, public models by repo id, no production data, no credentials in packages, explicit owner-approved submission. It is activated only after Kaggle's written permission names this use.

This is a reading of published terms and pages, not legal advice.
