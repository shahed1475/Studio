# Creator Hub: research, analysis and chosen design (10 Nov 2026)

The owner's brief (10 Nov 2026): a website where content creators (YouTube, Facebook, Instagram, TikTok, any social platform) open an account by email or Google, pick a niche, and a team of agents researches that niche, stores what it finds, and starts producing videos for it. The agents must talk to each other properly through A2A. Research first, then analysis, then the best version.

Labels: **VERIFIED** = read on the official page or run by me today; **SECONDARY** = only blogs and tool vendors say so; **UNVERIFIED** = not found or sources conflict. Nothing marked SECONDARY or UNVERIFIED is built on as fact.

## 1. What the studio already has (read in the code, not assumed)
- **User studios** (`tenantmode.py`, `deploy/tenant.sh`, docs/USER_STUDIOS.md): up to 5 other people, one folder and two containers each (worker cap 1.5 GB), invite link, own password, own OpenRouter key, own YouTube login, one public address with cookie routing.
- **Niches** (`niche.py`): ten presets, a fit check (a custom niche passes when 5 of 8 sample subjects have an article of 1,500+ characters), a research step that turns a choice into a plan, refusal of news, finance, health advice, politics, children's content and living people.
- **Agents** (`agents.py`): 26 named agents, each with a playbook, lessons, an escalation ladder, an inbox (`agentbus.py`, a JSON file) and behaviour checks (`agenteval.py`).
- **Login** (`webauth.py`): one owner, scrypt password, signed cookie, invites. No email codes, no Google identity sign-in (Google is used only to connect a YouTube channel).
- **Production engine:** Wikipedia-grounded narrated stories with a claim ledger, reviewer, fixer, YouTube upload. About $1 per documentary.

Consequence: the hub must not rebuild any of this. It adds an account layer, a shared research store, an A2A layer and platform adapters on top.

## 2. A2A (Agent2Agent) findings
| Finding | Label | Source |
|---|---|---|
| Latest released protocol version is 1.0.0 (earlier 0.3.0, 0.2.6, 0.1.0). Only Major.Minor is negotiated, in the `A2A-Version` header. | VERIFIED | a2a-protocol.org/latest/specification |
| Official Python SDK `a2a-sdk` 1.3.0, released 27 Oct 2026, Python >= 3.10, Apache-2.0, extras `http-server`, `grpc`, `sql`, `sqlite`, `postgresql`, `signing`, `telemetry`, `all`. Installed and imported by me in a scratch environment today (it pulls protobuf, starlette, httpx, pydantic). | VERIFIED | pypi.org/project/a2a-sdk, my install |
| Three bindings with equal behaviour: JSON-RPC 2.0, gRPC, HTTP+JSON. | VERIFIED | spec sections 9 to 11 |
| Agent Card is served at `/.well-known/agent-card.json`; fields include `name`, `description`, `supportedInterfaces` (each `url`, `protocolBinding`, `protocolVersion`), `capabilities`, `securitySchemes`, `securityRequirements`, `skills` (`id`, `name`, `description`, `tags` required), `defaultInputModes`, `defaultOutputModes`. | VERIFIED | spec 8.2 and 4.4.5; SDK type definitions |
| Methods on the wire: `SendMessage`, `SendStreamingMessage`, `GetTask`, `ListTasks`, `CancelTask`, `SubscribeToTask`, the four push-notification config methods, `GetExtendedAgentCard`. | VERIFIED | spec 9.4; SDK `jsonrpc.py` |
| Task states: SUBMITTED, WORKING, COMPLETED, FAILED, CANCELED, REJECTED, INPUT_REQUIRED, AUTH_REQUIRED (wire form `TASK_STATE_*`); terminal: COMPLETED, FAILED, CANCELED, REJECTED. | VERIFIED | spec 6.5 and 9.4.6 |
| Message roles `ROLE_USER` / `ROLE_AGENT`; results belong in Artifacts, not Messages; Part holds text, file or structured data. | VERIFIED (Part field table not read) | spec overview |
| Auth schemes: API key, HTTP, OAuth 2.0, OpenID Connect, mutual TLS. A server must answer 401 for missing credentials and must not reveal whether a resource exists to an unauthorized client. `TASK_STATE_AUTH_REQUIRED` alone is never authorization. TLS is required in production. | VERIFIED | spec 7.1 to 7.6 |
| A2A agents collaborate without sharing internal state, memory or tools (this is the difference from MCP, which connects one agent to tools). The full A2A-versus-MCP appendix was not read. | PARTLY VERIFIED | spec overview |
| Governance: Linux Foundation (since June 2025), later also an "AAIF" body in Aug 2026. | SECONDARY | search snippets; not needed by the design |
| Spec bytes 200,000 to 256,159 (appendices) were not read. | LIMIT | |

## 3. Platform publishing findings (decides what "all platforms" can honestly mean)
| Platform | What the sources say | Label |
|---|---|---|
| YouTube | Already built (`upload.py`). A public product that connects other people's channels needs Google's sensitive-scope verification and a public home page and privacy policy on a domain the owner verifies (docs/GOOGLE_PRODUCTION.md); unverified apps are capped at 100 new users. | VERIFIED (studio's own record of Google's pages) |
| TikTok | A client that has not passed TikTok's audit can post only as private (self only); at most 5 users may post in 24 hours; public accounts get HTTP 403 `unaudited_client_can_only_post_to_private_accounts`; app review (grants `video.publish`) and the audit are separate steps. | SECONDARY (TikTok's guideline page was returned by search but I did not open it) |
| TikTok review time | "several days to two weeks" (review) and "2 to 6 weeks" (audit) | UNVERIFIED (TikTok does not publish audit criteria or time) |
| Instagram | Content Publishing API posts images, videos and Reels only to Professional (Business or Creator) accounts linked to a Facebook Page; flow is create container (`/{ig-user-id}/media`) then publish (`/{ig-user-id}/media_publish`); needs `instagram_business_basic` and `instagram_business_content_publish` through app review. | SECONDARY (Meta page returned by search, snippets only) |
| Instagram daily limit | 50 or 100 posts per 24 hours; Meta's own pages disagree. The account's real number is read from `GET /<IG_ID>/content_publishing_limit`. | UNVERIFIED number, VERIFIED method |
| Instagram review time | "2 to 4 weeks" | UNVERIFIED |
| Facebook | Reels go to Pages only: start with `POST /{page-id}/video_reels` (`upload_phase=start`), upload binary to `rupload.facebook.com`, finish with another `video_reels` call; 30 API-published Reels per 24 hours. Permission list and whether `scheduled_publish_time` works for Reels: sources conflict. | SECONDARY (limit and flow quoted from Meta's guide in search results) / UNVERIFIED (permissions, scheduling) |

Analysis: only YouTube can be automated end to end today. The other three each need the owner's developer app, a review that takes weeks, and per-user Page or Professional-account linking. Until a platform approves the app, the honest feature is an **export package** (the finished vertical video plus caption, hashtags and a checklist) the creator posts by hand, with the connector switched on per platform only after its approval. Every video stays private or draft until the creator approves it (rule E).

## 4. Sign-in findings
- **Google sign-in (identity only).** Verify the ID token on the server: signature against Google's keys, `aud` equals our web client id, `iss` is `accounts.google.com` or `https://accounts.google.com`, `exp` not past, and the double-submit CSRF check (`g_csrf_token` cookie equals the POST body value). Use `sub` as the account key, never the email. An address is trusted when it ends in `@gmail.com`, or when `email_verified` is true and `hd` is set; otherwise ask for the emailed code. The library call `google.oauth2.id_token.verify_oauth2_token` checks signature, audience and expiry; the rest is ours. `google-auth` is already in requirements. (VERIFIED, Google's page.)
- **Emailed one-time code.** OWASP's forgot-password sheet (VERIFIED) says: generated by a cryptographically secure generator, long enough against brute force (numeric codes 6 to 12 digits), expiring, single use, stored securely, rate limited per account, the same answer whether or not the account exists (and the same timing), no automatic login after a reset flow, no links built from the Host header. It gives **no** numbers for expiry or attempts: ours (10 minutes, 5 tries per code, 3 sends per hour per address) are our own choices, said so in the code.
- Backend-design skills (auth-and-authorization, security-discipline) applied: server-side sessions with sliding and absolute expiry, deny by default, tenant id from the session never from the body, generic errors, constant-time compares, audit log of every sign-in decision.
- Sending real email needs an SMTP account or a mail provider key: **owner step**. Prices and free tiers of providers were not researched (UNVERIFIED); the hub ships a mailer interface, an SMTP sender and a local outbox for testing.

## 5. Analysis: options and the choice
**A2A server: our own small implementation versus the official SDK server.**
- SDK server: needs starlette, uvicorn, httpx, protobuf, pydantic on the server image; async; the dashboard and every other server here is stdlib `http.server`; the project rule is that libraries are planned and tested, never copied in blind.
- Own implementation of the JSON-RPC binding: stdlib only, about 400 lines, same threading model as the dashboard, task store in SQLite we already control.
- **Choice: own implementation of the A2A 1.0 JSON-RPC binding, checked by the official SDK's client in a test** (the test is skipped where the SDK is absent). The SDK stays a test-time tool, so a protocol mistake of ours shows up as a failing conformance test rather than a guess.

**How agents "discuss".** A room is an A2A `contextId`. A member agent is called with `SendMessage`; it answers with a Message or, when it needs another agent or the creator, moves its task to INPUT_REQUIRED. The room runner gives each round to the next agent, stops at a round limit (default 3 rounds), a cost limit (account's daily budget through `llm.cost_scope`) or agreement, and stores the transcript and one decision Artifact. Discussion is bounded because every turn costs tokens and the owner's budget is small. An agent can never publish, spend above its cap or change settings from inside a room: it can only ask the publisher agent, which refuses without a human approval flag.

**Tenancy.** Today: one container pair per user (max 5, 1.5 GB worker each). That cannot serve "any creator" on one small server. The hub therefore separates the **control plane** (accounts, niche research store, agents, A2A, website: one light process, many accounts, SQLite with `account_id` on every row and a data layer that cannot be called without it) from the **render plane** (the existing engine). First version: control plane for any number of accounts; rendering stays in the existing per-user studios, so real video output remains limited to 5 accounts until the engine runs several accounts in one worker (a refactor of modules that read `config.ROOT`). Said plainly in the website and here.

**Niche scope.** The production engine only grounds stories in Wikipedia articles. The hub accepts any niche into research and planning (and stores everything), but marks each niche's **tier**: A = the engine can produce it fully (history, legends, science, space, art and similar, the existing presets and passing custom ones); B = research, plan and script drafts and export package only, no promise of fact-checked video. The sensitive categories the engine already refuses stay refused with the reason.

**Research store.** SQLite tables (accounts, sessions, login codes, niches, sources, facts, trends, topics, a2a_tasks, messages, artifacts, audit). A research fact is stored with its URL, passage and date, and a label (VERIFIED, PARTIALLY_VERIFIED, CONFLICTING, UNVERIFIED) like the claim ledger; the researcher agent may not label a fact VERIFIED without a source passage (rule A).

## 6. Chosen design (built in this order)
1. **M1 Hub core (`hub/` package):** SQLite store, email-code and Google sign-in, sessions, audit log, rate limits; A2A gateway (agent cards, `SendMessage`, `SendStreamingMessage`, `GetTask`, `ListTasks`, `CancelTask`, `SubscribeToTask`, `GetExtendedAgentCard`); rooms; seven hub agents with playbooks (concierge, researcher, strategist, scriptwriter, producer, reviewer, publisher). Tests, including a conformance test with the official client.
2. **M2 Website:** landing page, sign-in (code and Google), niche onboarding, workspace with the agents' live room, platform status page. Premium visual design, animation honouring reduced motion, light and dark.
3. **M3 Niche research handler** (existing `niche.py`, Wikipedia, YouTube trends where a key exists) writing to the research store; **export package** per platform; YouTube connector through the existing studio.
4. **M4 Deploy** (owner's yes): a third container behind the existing Caddy proxy, SMTP settings, Google web client id, domain and privacy page.

## 7. What needs the owner (nothing here is done by an assistant)
- A name and a domain for the product (Google verification and email deliverability both need one).
- An SMTP account or mail provider for sign-in codes; the Google **Web** client id for Google sign-in (same client as in docs/USER_STUDIOS.md). The terminal prompt that stores them privately, the exact steps and what was and was not verified: `docs/studio/HUB_MAIL_AND_GOOGLE_SETUP.md` (`python -m hub.configure`).
- Developer apps and reviews at Meta (Instagram, Facebook) and TikTok; Google sensitive-scope verification for connecting other people's YouTube channels.
- A decision on how many accounts may render videos, given the server's memory (today 5).
- Cost: each creator brings their own OpenRouter key (as user studios do); the hub's own agents use a small shared budget for onboarding only, capped.

## 8. Limits and risks
- A passing check is evidence, not proof; agents' conversations are model output, not facts: facts still need a source passage.
- Platform rules above are mostly SECONDARY or UNVERIFIED; read each platform's own page before connecting it.
- Reposting one video to four platforms is allowed by none of the sources I read to be "free of policy risk": YouTube's inauthentic-content rule (VERIFIED in this project) judges whole channels for templated, mass-produced content; other platforms' rules were not read.
- Email codes can be phished; Google sign-in is offered as the stronger choice.
- A2A discussion adds model cost and a prompt-injection surface (text from the web reaching an agent). Mitigation in the design: web text is data, labelled and capped; no agent action that spends, publishes or deletes is reachable from a message alone.
