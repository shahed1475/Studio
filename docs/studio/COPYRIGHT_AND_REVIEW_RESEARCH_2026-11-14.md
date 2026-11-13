# Footage rights, free review and agent messaging: research record (14 Nov 2026)

Labels follow CLAUDE.md A. VERIFIED = passage read in the page itself (Chrome, raw page text). PARTIALLY_VERIFIED = taken from a search summary or a fetch summary, page not read raw. UNVERIFIED = not checked. Read on 14 Nov 2026 (PC clock).

## 1. How can a channel use "real footage" without trouble?
| Finding | Source | Label |
|---|---|---|
| Fair use is decided by courts, case by case, on four factors (purpose, nature, amount, market effect). YouTube advises legal advice before uploading copyrighted content. | https://support.google.com/youtube/answer/9783148 : "Ultimately, courts decide fair use cases according to the facts of each unique case." | VERIFIED |
| Credit, a disclaimer, saying "entertainment" or "non-profit", or adding your own material do not by themselves protect a video (the page lists them as questions "Am I protected by fair use if I..."). | same page | VERIFIED (the page lists the questions; the answers sit behind fold-outs I did not open) |
| A Content ID claim is automatic and usually does not affect the channel; a strike follows a valid removal request; 3 strikes in 90 days can end a channel. YouTube "can't determine what qualifies for exceptions such as fair use". Credit, owning a copy or not monetising are not valid dispute reasons. | https://support.google.com/youtube/answer/2814000, /6013276, /2797454 | PARTIALLY_VERIFIED (search summary) |
| Creative Commons Attribution (CC BY) content, public domain content and your own content may be reused; credit needs title, author, source address and licence. A video with a Content ID claim cannot carry CC BY. | https://support.google.com/youtube/answer/2797468 | VERIFIED |
| NASA: imagery is generally not copyrighted in the US but "not in the public domain" as a label; credit NASA; some images belong to others; identifiable people and logos need care for commercial use. | https://www.nasa.gov/nasa-brand-center/images-and-media/ | PARTIALLY_VERIFIED |
| Library of Congress: it owns most rights to few items; read each item's Rights and Access; "Free to Use and Reuse" sets are cleared; privacy and publicity rights are separate from copyright. | https://www.loc.gov/legal/understanding-copyright/ , https://blogs.loc.gov/loc/category/free-to-use-and-reuse/ | PARTIALLY_VERIFIED |
| A YouTube search for "cristiano ronaldo documentary full" shows 48 to 63 minute films with 9 to 31 chapters and 0.8 to 49 million views. Whether any of them carries claims cannot be seen from search results. | https://www.youtube.com/results?search_query=cristiano+ronaldo+documentary+full | VERIFIED for what is listed; claim status UNVERIFIED |

**What this means.** Channels that show "real footage" without trouble do one of four things: licence it or own it (agency, stock, own camera); use public-domain or CC material with credit; rely on fair use for commentary and accept that a claimant can still claim it; or have a claim that moves the revenue without a strike. None of these is a safe way to take match footage. I did not survey individual channels, so I cannot say which of the four any given channel does.

**Not implemented, on purpose:** altering, mirroring, speeding or cropping other people's footage to avoid detection. That is evasion, is against YouTube's rules and against this project's rules (B and D). Downloading other people's YouTube videos stays forbidden.

**What the studio can do.** Footage ladder for Autopilot, best first: (1) the studio's own drawings, 3D renders and code-drawn graphics; (2) public domain and CC0 with the licence page saved; (3) CC BY and CC BY-SA with the credit line in the description (title, author, address, licence); (4) US government works (NASA, Library of Congress items marked free to use) with credit and no implied endorsement; (5) nothing else. Fair use is never chosen by Autopilot: it needs a person and, for a living person or a sport, a lawyer's view.

## 2. Why paid review models seem to work and free ones do not
| Finding | Source | Label |
|---|---|---|
| Free (`:free`) models: 20 requests a minute; 50 a day if fewer than 10 credits were ever bought, 1,000 a day if at least 10; the tier is by all-time purchases; buying credits raises only the daily cap. | https://openrouter.ai/docs/api-reference/limits | PARTIALLY_VERIFIED (fetch summary with quotes) |
| Structured (JSON schema) output is supported only by select models and "per endpoint, not just per model"; routing to compatible endpoints needs `require_parameters: true` plus `response_format` of type `json_schema`; an unsupported request fails with an error. | https://openrouter.ai/docs/features/structured-outputs | PARTIALLY_VERIFIED |
| Studio data, 13 Nov: the review role made 97 calls and 375k output tokens in a day; free models "did not return JSON" several times; videos ended `unreviewed`; the balance still fell about $0.21. | `data/llm_usage.json` on the server | VERIFIED (our own record); the cause of the dollar drain is UNVERIFIED |

**What this means.** A paid model is not more truthful. It answers in the required JSON shape every time, reads the long script plus source in one call, and has no shared 20-a-minute limit. Free models fail on shape and rate. The checks that guard facts do not need a model: the claim ledger (passage found in the saved page), licences, ffprobe, decode, captions, dead air and frozen pictures are rules. A model can only add warnings (CLAUDE.md: a model can only warn).

**Design (to build, tested):** deterministic gate first; then one JSON-schema-constrained opinion from the server's own Ollama models (no limit, no cost); then free OpenRouter only with `require_parameters`; malformed JSON is `unreviewed`, never a pass; one retry only; a per-video call budget. Approval by Autopilot when every rule passes and no model raises a blocker, recorded as `approved_by: autopilot-free`, never as the owner's.

## 3. Agent-to-agent messaging (A2A)
| Finding | Source | Label |
|---|---|---|
| A2A is JSON-RPC 2.0 over HTTP(S); agents publish an Agent Card (identity, skills, endpoint, auth); work is a Task with a lifecycle (working, input-required, completed, failed, cancelled, rejected); v0.3 used `tasks/get`, v1.0 uses `GetTask` style names; started by Google in 2025 and moved to the Linux Foundation. | https://a2a-protocol.org/latest/specification/ | PARTIALLY_VERIFIED |
| The studio already has an internal inbox (`agentbus.py`: post, claim, finish, to_owner; states open, working, done, failed, owner) and an A2A gateway with conformance tests exists on branch `feature/hub` (`hub/a2a.py`, `tools/hub_a2a_conformance.py`), built but not deployed. | repo | VERIFIED |

**Design:** keep `agentbus` as the single source of truth and add a thin A2A adapter (Agent Cards for the 24 agents, `message/send` posts a task, `tasks/get` reads its state), reusing `hub/a2a.py` after a security review. Bind to loopback, no secrets in cards, owner-only token.
