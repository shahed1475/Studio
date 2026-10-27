# Costs: every paid call the studio makes (26 Oct 2026)

Only numbers that were measured and written down elsewhere in this repo appear here, each with its source. A number nobody measured says "not measured". Prices change: re-read them before relying on them.

## Paid calls
| What | Where in the code | Measured cost | Source of the number |
|---|---|---|---|
| Writing, fact-check and review text (OpenRouter chat: Claude Sonnet 5.5 / Haiku 5.5, free models as fallback) | `llm.chat`, used through `scriptgen.py`, `reviewer.py`, `fixer.py`, `growth.py`, `seo.py` | one documentary: script about $0.25, reviews about $0.20 | `CLAUDE.md` "Money and repair rules" |
| AI storybook pictures (OpenRouter image model) | `aiart.py`, `PRICE_EACH` | $0.034 a picture ($3.19 for 95 pictures, 20 Oct 2026); about $0.54 a documentary | `aiart.py` comment, `CLAUDE.md` |
| A repair that re-renders | `fixer.py`, `run.py repair` | one title and description repair of a Short: $0.049 (Hong Gildong, 25 Oct); re-renders add to the video's total | `docs/studio/PROGRESS.md` 25 Oct |
| Footage clip (OpenRouter video model, test studio only) | `tools/footage/clipgen.py` | one 8 s test clip: $0.24 (owner studio, before the guard existed). The settings price of $0.03 a second is NOT confirmed; the tool now reads the live price list and books the provider's own `usage.cost` | `docs/studio/PROGRESS.md`, `config/footage.json` |

## Totals that were recorded
- A full documentary with pictures: about $1 (`CLAUDE.md`). Mami Wata (26 Oct slot): $0.906 recorded by `llm.cost_scope` (`data/video_costs.json` on the server).
- A day of Autopilot work with remakes: about $2.9 on 24 Oct (`docs/studio/PROGRESS.md`).

## Free calls (no money, but limits)
Edge TTS voice (`tts.py`), Wikipedia, GitHub API (60 requests an hour when not signed in: `githubfacts.py`), YouTube Data API (daily quota, no charge), Pexels (free account).

## Guards that cap the spend
Daily cap `daily_budget_usd` in `llm.json` (1.5; the worker reads it live), no new video under $1.50 OpenRouter credit (`autopilot.MIN_CREDIT_TO_MAKE`), per-video limits ($2.50 documentary, $0.70 Short: `MAX_VIDEO_COST`), per-clip cap and live price check for footage (`config/footage.json`), hourly `risk.money_watch`.

## Not measured
Average cost of a Short; the monthly total; the cost of the web fact-check (`webcheck.py`); the real price of the footage model per second; whether OpenRouter bills a video job that ends `failed` (its docs do not say: the tool keeps the money booked if the balance fell).

## Savings, ranked by money saved against effort (from the figures above only)
1. Keep AI pictures at the existing limits (10 a documentary, 4 a Short): pictures are the largest single line of a documentary ($0.54 of about $1).
2. Fix a video once, not three times: each re-render repeats the picture cost, so the two polish rounds and the picture-only third try are the real limit (`fixer.POLISH_ROUNDS`).
3. Do not make footage clips for the owner studio until the test studio proof (a real run, the cap refusal, the bad source) has passed: a clip is $0.24 for 8 s at the list price, so a 60 s Short made of clips would cost about $1.80 before any review.
