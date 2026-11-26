# Kaggle policy and workload eligibility (25 Nov 2026)

This is a reading of published terms, not legal advice. Where the terms are unclear, the workload is BLOCKED pending authorization.

## Sources read today (VERIFIED)
Kaggle's pages were read signed out in the owner's Chrome. Kaggle renders them with scripts, so a plain fetch returned only page titles.
- **Terms of Use** (https://www.kaggle.com/terms): the page shows **"Terms Version June 22, 2025 (active)"**.
  - Use clause: "You will only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party".
  - Prohibited uses include crawling or scraping, copying significant portions of the Content, and cryptomining.
- **Notebooks documentation** (https://www.kaggle.com/docs/notebooks):
  - "12 hours execution time for CPU and GPU notebook sessions and 9 hours for TPU notebook sessions";
  - "20 Gigabytes of auto-saved disk space (/kaggle/working)";
  - "Up to 20 GBs of output from a Notebook may be saved".
  - It still says "a single NVIDIA Tesla P100". That is out of date: the CLI's own help says retired accelerators such as P100 "are accepted but warn", and every real session gave 2 x T4.
- **GPU tips** (https://www.kaggle.com/page/GPU-tips-and-tricks): "up to 30 hours per week of GPU, and individual sessions can run up to 9 hours".
  - **Conflict:** the Notebooks page says 12 hours for GPU sessions. Plan with the stricter **9 h**.
  - The account's own figure (`kaggle quota`, today) is 30.00 h total, 18.12 h left, refresh 2026-11-28 00:00 UTC.
- **Kaggle CLI docs** (github.com/Kaggle/kaggle-cli, docs/kernels.md):
  - `kernels push --accelerator` (T4 x2 is `NvidiaTeslaT4`, "default GPU"; others such as L4, A100 and H100 are listed "as of Sep 2026", some only for specific competitions);
  - `-t/--timeout` in seconds;
  - `kernels output` downloads the latest run's output;
  - **no cancel or stop command** (`kernels delete` deletes the kernel itself).
  - github.com/Kaggle/kaggle-api now serves the kaggle-cli page (renamed or redirected; no archive notice seen).
- **Competition rules, `spaceship-titanic`** (rules page): the page **contradicts itself**.
  - Its summary line says "DATA ACCESS AND USE: Competition Use and Academic, Non-Commercial Use Only".
  - Its section A says "You may access and use the Competition Data for any purpose, whether commercial or non-commercial".
  - **Correction:** the 24 Nov report quoted only section A.
- **`titanic` and `house-prices`:** read 24 Nov (not re-read today): competition data non-commercial only.

## Eligibility matrix
| Workload | Data source | Model / licence | Commercial? | Kaggle allowed? | Evidence |
|---|---|---|---|---|---|
| Competition experiment (submissions to `titanic`, `house-prices`, `spaceship-titanic`) | That competition's data only | Any model whose licence allows it | No | **YES, within that competition's rules** | Terms; each competition's rules page |
| Use of competition data for anything other than that competition (including attaching it to a benchmark) | Competition data | — | — | **BLOCKED (unclear or non-commercial)** | spaceship-titanic's contradictory page; titanic / house-prices non-commercial |
| Model benchmark (fixed public prompts; outputs are timings and sample answers, never channel material) | 5 public prompts in `data/compute/inputs/` | Public twin, licence on the production list (e.g. Qwen3-4B-Instruct-2507, Apache-2.0) | Personal by the owner's standing decision (24 Nov, `owner_permitted_tasks: ["benchmark"]`) | **ALLOWED-CONDITIONAL** | Terms "internal, personal, non-commercial". Residual ambiguity: a benchmark run to choose infrastructure for a monetised channel could be read as a business purpose. Kaggle's written answer would remove it (draft request exists, not sent). |
| Image-model benchmark (e.g. Z-Image Turbo, public prompts, pictures discarded) | Public prompts | Z-Image Turbo GGUF twin (Apache-2.0), Qwen3-4B text encoder, ae VAE (all verified twins) | Same as above | **NEEDS OWNER CONFIRMATION** (new task type; pictures must never reach the channel) | as above |
| Personal experiment on the owner's own data | Owner's private files | Any | Possibly personal | **BLOCKED by studio policy** (private data never leaves this PC: `data_class` gate), whatever Kaggle allows | config/compute.json, `computerouter.kaggle_gate` |
| Fine-tuning or running the owner's own models (cyberexpert, argon, marketing, LoRAs) | Private weights | Owner's | — | **BLOCKED** (the file would have to be uploaded; no public twin exists) | twin rule |
| Documentary or Short production (scripts, voice, pictures, video, renders) | Studio assets | Any | **Yes (monetised channel)** | **BLOCKED pending Kaggle's written authorization** | Terms; studio rule; `commercial_use_permitted: false` |
| Generating channel pictures or video "as a test" and then using them | — | — | Yes | **BLOCKED** (disguising production as a test is refused) | Brief, rule 2 |

## Rules the worker must keep (all present today unless marked)
- **Data class:** only `public-test` data leaves this PC.
- **Task allowlist:** only listed tasks (`benchmark`) are allowed while `commercial_use_permitted` is false.
- **Owner's models:** they run only through a public twin proven by SHA-256; nothing private is uploaded.
- **Accounts and sessions:** no second account, no keep-alive, no scraping, no notebook that polls a studio server.
- **Licence:** each job records its model's licence. A job's competition source is attached only for a genuine competition job (**NOT YET**: benchmarks attach `spaceship-titanic` today; removal NEEDS APPROVAL, Category B).
