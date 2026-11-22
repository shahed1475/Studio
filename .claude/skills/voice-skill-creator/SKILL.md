---
name: voice-skill-creator
description: |
  Self-applied interviewer that walks a first-time agent user (Cowork, Codex, Claude Code, or any Skills-aware system) through producing a v1 voice SKILL.md scaffold of their own. Conducts a structured interview across identity, modes, sample harvest, pattern extraction, tropes, and worked examples; then generates a starter voice skill file plus an optional tropes companion plus install instructions. Output is explicitly v1 — the skill ships with a built-in expectation that the user runs harvest cycles for 8+ weeks before treating any of it as canonical. Reverse-engineered from Eric Porres's eric-porres-voice and tropes skills, abstracted to be applicable to any user.

  Triggers: "create my voice skill", "build my voice skill", "I want my own voice skill", "extract my voice", "/voice-creator", "/build-my-voice", "make a voice skill for me", "scaffold a voice skill", "I just got Cowork and want my voice", "help me write in my voice", "voice skill from scratch"
version: 1.0
created_by: "Eric Porres — eric@porres.com"
last_updated: 2026-05-08
---

# voice-skill-creator — Self-Applied Voice-Skill Scaffolder (v1)

## What This Is

A meta-skill. Most skills *do* something. This one *produces another skill* — specifically, a starter voice skill the user can install in their own plugin namespace.

It is designed for the first-time agent user. Picture someone who just installed Cowork (or set up Codex, or installed a Claude Code skills folder) and wants Claude or another LLM to write in their voice — emails, posts, documents, social — without sounding generic. They have writing samples but no skill yet. This meta-skill walks them through the interview, harvests samples, extracts patterns, and produces a v1 SKILL.md they install and then evolve over time.

It is NOT:
- An automatic voice-extraction tool that takes one prompt and produces a finished skill (that produces shallow tells baked in as if they were signature moves)
- A way to extract someone else's voice (self-applied only — the interviewee is the writer)
- A replacement for accumulated harvest cycles (eric-porres-voice represents 3+ years of `/cos` harvests; the v1 output of this skill is a starting hypothesis, not a finished product)

## Honest Expectations (read this first)

The output is v1, not v∞. A voice skill that compounds in value gets evolved over months. What you get from one interview is a hypothesis to refine, not a canonical document.

Samples are required. Pattern extraction without writing samples produces hallucinated voice; the agent will pattern-match on its own training distribution and call it yours. Five samples across modes is the minimum, and the skill refuses to proceed below that threshold.

The tropes section is half the value. What you actively avoid writing is as defining as what you write, and skipping the tropes interview produces a thinner skill no matter how thorough the rest of the pass is.

Install, harvest, iterate. After the skill outputs a v1 SKILL.md, the user installs it, uses it for four to eight weeks while running `/cos harvest`-style cycles (or the equivalent in whatever agentic system they're in), and updates it as the LLM-owned middle layer accumulates evidence. The version that actually sounds like you is the version that's been used for a year.

The skill surfaces these expectations to the user at the start of the interview and will not ship without samples.

## The Three-Layer Model (context for the user)

Voice skills live in the human canonical layer of Karpathy's three-layer model:

| Layer | Role | Example |
|---|---|---|
| Raw verbatim store | Append-only firehose of conversations and writing | Deep memory ingest, history of drafts |
| LLM-owned middle | Dated observations and proposed refinements | `<voice-skill>/learnings/` directory written by harvest cycles |
| Human canonical | The skill itself, ships in plugins | `<voice-skill>/SKILL.md` |

The v1 output of voice-skill-creator IS the human canonical layer. This skill creates the canonical scaffold. The user evolves it through the middle layer over time.

## When to Run

- A user just got their first agentic system and wants the LLM to write in their voice
- A user has been writing for years, has accumulated samples, and wants to formalize their voice as a skill instead of re-explaining it every session
- A user has an LLM-generated voice doc that doesn't sound like them and wants to ground a real one in actual samples
- A team or organization wants to scaffold voice skills for executives, founders, or thought leaders who write under their own name

Trigger phrases listed in frontmatter. Slash command: `/voice-creator` or `/build-my-voice`.

## Workflow

The interview runs in 8 phases. Each phase has a clear input ask, a structured output, and a phase boundary the user must explicitly approve before proceeding to the next. This is intentional — the interview is the value, and skipping phases produces a thinner skill.

### Phase 1 — Setup and expectation-setting

Open with the four honest expectations above. Ask the user to confirm they understand. If they push back ("I just want a skill in 5 minutes"), explain that you can produce a SKILL.md in 5 minutes but it won't sound like them — only the interview produces a voice skill that holds up.

Ask three setup questions:
- What's your name, and what canonical email or handle do you write under?
- What's your professional context — title, organization, what you do? (1–2 sentences; this becomes the identity anchor)
- What system are you installing this skill into? (Cowork plugin, Claude Code skill, Codex, custom — affects install instructions in Phase 8)

### Phase 2 — Audience and mode mapping

Ask the user to enumerate their primary audiences and the modes they use with each. Examples:

- Internal team at work (peers, reports, manager) — mode: warm, direct, low-stakes
- External professional (clients, partners, board) — mode: formal, structured, higher-stakes
- Family and close friends (partner, kids, close friends) — mode: casual, intimate
- Public audience (Substack, LinkedIn, conference, podcast) — mode: thought leadership, irreverent-but-precise
- Self (own notes, journals, planning docs) — mode: terse, telegraphic

The user picks 2–4 named modes that matter for their writing. Suggested labels: `[WORK]`, `[PERSONAL]`, `[PUBLIC]`, `[INTERNAL]`. They can rename or use their own conventions.

For each mode, capture:
- What it sounds like (one sentence)
- A trigger keyword the user can use to invoke that mode (`[WORK]`, `[PUB]`, etc.)
- The most common output channel (email, Slack, LinkedIn post, etc.)

### Phase 3 — Sample harvest

This is the heaviest phase, and the one most likely to be skipped. Refuse to skip it. Without samples, the skill is a hallucination.

Ask the user to paste 5–15 writing samples spanning their modes. Specifically:

| Mode | Min samples | Suggested examples |
|---|---|---|
| Work / professional | 2–3 | A peer email, a manager email, an external partner email |
| Casual / personal | 1–2 | A Slack message thread, a WhatsApp message, a casual email |
| Public / thought leadership | 1–2 | A LinkedIn post, a Substack paragraph, a podcast intro |
| Long-form | 1–2 | A blog post, an internal memo, a strategy doc |
| Negative samples (optional but valuable) | 1–2 | A piece NOT in their voice — failed AI draft, ghostwritten content, something a colleague wrote that sounded wrong |

If the user has fewer than 5 samples available, pause the interview, tell them to come back with samples, and stop. Do not proceed.

Store samples internally; do not write them to disk yet. They are private to the interview.

### Phase 4 — Pattern extraction

Analyze the samples for the following pattern classes. Write each finding back to the user for confirmation; do not assume.

**Lexical patterns**
- Words that appear repeatedly across samples (signature words)
- Words conspicuously absent compared to typical professional prose (signature avoidances)
- Punctuation habits (em-dashes, Oxford comma, semicolons, exclamation marks, ellipses)
- Capitalization conventions (Title Case Habits, ALL-CAPS for emphasis, etc.)

**Sentence-level patterns**
- Average sentence length (short / medium / long / mixed)
- Opener patterns (lead with answer? bury lede? start with a question? a frame?)
- Closer patterns (call to action? rhetorical question? summary? abrupt stop?)
- Triplet structures, "not just X but Y" patterns, list-of-three rhythms

**Structural patterns**
- Paragraph length (terse / standard / long)
- Use of headers, bullets, lists (frequent / rare / mode-dependent)
- Argumentation style (assertion-first / evidence-first / story-led / data-led)
- How they handle disagreement (push back directly / Socratic / hedge / agree-then-pivot)

**Mode-specific patterns**
- How does formal differ from casual? (vocabulary, sentence length, structure)
- How does public differ from internal? (concept density, link-out behavior, hooks)
- Where are the modes most blurred and where are they most distinct?

For each pattern, present three candidate findings to the user with examples from their samples. Ask: is this real and worth encoding, partially-real-but-needs-revision, or wrong? Capture the response.

### Phase 5 — Tropes interview (the avoid-list)

Tropes are not exclusively AI tells. They are patterns the user actively avoids — writing crutches, industry cliches, hedging language, corporate-speak, business-school jargon, AI-generated tells, and the user's own personal pet-peeve phrases. The voice skill is half what they write and half what they refuse to write.

Walk the user through five sub-categories:

**5a. Personal pet peeves**
What words or phrases make them cringe to read or hear? "Synergy," "leverage as a verb," "going forward," "at the end of the day," "circle back," "double-click on that"? Capture their personal ban list.

**5b. Industry cliches**
What's the corporate-speak in their domain that they've banned themselves from? Tech: "ecosystem," "platform play," "unlock value." Finance: "headwinds," "tailwinds," "inflection point." Marketing: "best-in-class," "value proposition," "north star." Get specific to their industry.

**5c. Hedging and weakness language**
Hedge words ("perhaps," "somewhat," "I think maybe"), apology openers ("I'm not sure if this is right but..."), permission-seeking ("if I might add..."), wishy-washy adjectives ("interesting," "great," "good"). Most writers have a hedging habit they've been trying to break.

**5d. AI-generated tells**
Even before the AI era, certain patterns scream "machine wrote this." Examples (drawn from the Russell/Karpinska/Iyyer ACL 2025 vocabulary list and similar empirical work):
- Vocabulary: "delve," "tapestry," "navigate the landscape," "in the realm of," "showcase," "leverage" (as a verb)
- Sentence rhythm: triples ("X, Y, and Z"), "not just X, it's Y," signposted conclusions ("In conclusion,")
- Structural: bullet-point everything, mandatory header for every paragraph, "It's important to note that..."
- The "Despite Its Challenges..." formula (acknowledge-and-dismiss)
- Pre-summary intros ("In this section, we will...")
- Title-Case headings on everything
- Fictional authority names ("Dr. Sarah Chen, expert in...")

The user picks which AI tells they want banned. Most pick most of the list, but the canonical signal is which ones they explicitly ban — that intentionality is what makes the trope rule load-bearing in their skill.

**5e. Tensions — signature moves that overlap with avoid-list**
This is the subtle one and the most valuable. Some patterns are simultaneously the user's signature move AND on a generic AI tell list. Eric Porres uses "load-bearing" deliberately and frequently — it's a signature word for him, but it's also on some AI vocabulary lists. The right move is not to ban it but to flag it as a tension: "This word is signature for me; the meta-rule is don't stack it three times in one document."

Ask the user: from the avoid-list assembled in 5a–5d, are there any items that you actually use deliberately as signature moves? Capture those as Tensions, not bans.

### Phase 6 — Mode dial calibration

Take the modes from Phase 2 and the patterns from Phases 4–5. For each mode, write a 3–5 sentence calibration that codifies how the user's voice shifts across modes. Examples:

- `[WORK]`: medium-length sentences, structured, leads with the answer, Oxford comma, no exclamation marks, terse but warm. Banned: corporate-speak from 5b. Allowed: technical density, peer-to-peer directness.
- `[PERSONAL]`: shorter sentences, casual punctuation, em-dashes for asides, occasional fragment for emphasis, more humor and less hedging. Banned: anything formal-sounding.
- `[PUBLIC]`: medium-to-long sentences, irreverent-but-precise, signature words used deliberately, examples from real experience preferred, no corporate prose, lead with a hook not a frame. Banned: pre-summary intros, signposted conclusions, "delve."

Present each mode's calibration to the user for review. Ask which to keep, which to revise, which to drop.

### Phase 7 — Worked examples library

The single most valuable training signal in a voice skill is concrete before/after pairs. Ask the user to provide 3–5:

- Generic version: "I'm reaching out to follow up on our previous conversation regarding the proposal we discussed. Please let me know your thoughts at your earliest convenience."
- User's version: "Following up on the proposal — what's your read?"

Or:
- AI-style: "Despite its challenges, the project remains on track. Looking forward, we anticipate continued progress."
- User's version: "Three things broke this week. Two are fixed; one is the design constraint we'll have to live with."

These pairs encode mode, vocabulary, sentence rhythm, and avoid-list all at once. They are the single highest-leverage section in the generated SKILL.md.

If the user can't easily generate 3 pairs, prompt with one of their samples and ask: how would generic AI write the same thing? They write the comparison. The before/after gap is the encoding.

### Phase 8 — Generate v1 SKILL.md

Compile everything into a starter SKILL.md. The output uses the template in `references/voice-skill-template.md` (see Reference Files below). The structure mirrors the eric-porres-voice canonical example, abstracted.

Key sections in the generated file:
1. Frontmatter (name, description, triggers, version 0.1, created_by)
2. Honest expectations and three-layer-model context (so the user remembers this is v1)
3. Identity (from Phase 1)
4. Modes and dials (from Phases 2 + 6)
5. Channel guardrails (from Phase 2's channel mapping)
6. Lexical patterns — USE FREELY list and AVOID list (from Phase 4 lexical + Phase 5)
7. Sentence-level patterns (from Phase 4 sentence-level)
8. Structural patterns (from Phase 4 structural)
9. Tropes section (from Phase 5, all five sub-categories)
10. Tensions list (from Phase 5e)
11. Worked examples library (from Phase 7)
12. How to evolve this skill — pointer to harvest pattern (8+ weeks of `/cos`-style runs before treating any section as canonical)

Output path: `<user-chosen-base-path>/<user-name>-voice/SKILL.md`. Default base path: the directory the user invoked the skill from. Default skill name: `<firstname-lastname>-voice` (kebab-case).

### Phase 9 — Optional tropes companion

If Phase 5 yielded enough avoid-list content (rule of thumb: 30+ distinct items across 5a–5d), offer to generate a separate `<user-name>-tropes/SKILL.md` companion. The tropes skill is a diagnostic — invoked as a second pass over a draft, it scans for items on the avoid-list and flags them. The voice skill sets the affirmative target; the tropes skill is the ban-list enforcer.

Pattern follows Eric's tropes skill: Tensions section first (signature moves that overlap with bans, must NOT be flagged), then five categorized ban lists, then a usage note ("invoke after the voice check, before shipping").

If avoid-list is thin (<30 items), do not generate a tropes companion. Inline the bans into the voice skill instead. Tell the user explicitly: "Your avoid-list isn't yet rich enough to justify a separate tropes skill — when you've harvested another 20+ bans through use, regenerate."

### Phase 10 — Install instructions and harvest pattern

Generate `INSTALL.md` in the same directory as the voice skill. Contents depend on the system the user named in Phase 1:

- **Cowork plugin**: Path to drop the skill into a personal plugin, plugin.json bump, marketplace push (or upload via Settings → Plugins → +)
- **Claude Code**: Path to drop into `~/.claude/skills/` or project `.claude/skills/`
- **Codex / generic Skills system**: Path conventions and how the skill gets discovered
- **Anthropic API direct**: How to inject the skill content as a system-prompt prefix

Also generate `HARVEST-CYCLE.md` describing the evolution pattern:
- Run the voice skill on real writing tasks for 4–8 weeks
- Each session, note: did the output sound like you? What did you rewrite? What surprised you (in a good or bad way)?
- Weekly, run a harvest pass — re-read the week's drafts, flag patterns the skill missed or got wrong, write dated learning entries to `<voice-skill>/learnings/YYYY-MM-DD-<slug>.md`
- After 8 weeks, do a distill pass — read all learnings, edit SKILL.md to incorporate accumulated signal
- The pattern continues indefinitely; voice skills are always evolving

### Phase 11 — Confirm and exit

Tell the user the file paths written. Show the v1 SKILL.md to them in the response and ask them to skim it for obvious errors before they install. Do not write to their plugin namespace or skills folder automatically — they install manually. Final sanity check: refuse to call the skill complete if any phase was skipped.

## Reference Files

- `references/voice-skill-template.md` — the canonical skeleton for the generated voice SKILL.md
- `references/tropes-skill-template.md` — the canonical skeleton for the optional tropes companion
- `references/install-instructions-template.md` — install paths for Cowork, Claude Code, Codex, and Anthropic API
- `references/harvest-cycle-template.md` — the evolution pattern after install
- `references/eric-porres-voice-as-worked-example.md` — pointer to Eric's actual voice skill, marked as the canonical worked example for this meta-skill (read but do not copy verbatim — abstract the structure, not the content)

The reference templates are loaded per phase as needed. They are not embedded inline in this SKILL.md to keep this file readable.

## Important Guardrails

- **Refuse to ship without samples.** Phase 3 is non-skippable. If the user can't provide 5+ samples across modes, exit and tell them to come back when they have samples.
- **Refuse to extract someone else's voice.** This is a self-applied skill. If a user pastes someone else's writing and asks for "their voice," refuse and explain why (the empirical samples must come from the person whose voice it is).
- **Set the v1 expectation up front and again at exit.** The most common failure mode is the user treating the v1 output as canonical and never running harvest cycles. Repeat the expectation at the start (Phase 1) and at the end (Phase 11).
- **Do not auto-install.** Generate files in a working directory; let the user install manually. The user must read what they're installing.
- **Do not invent samples.** If the user provides 4 samples and you need a 5th to test a mode, ask for it. Do not synthesize the missing one.
- **Reference but do not copy** Eric's voice skill. The structure abstracts; the content does not transfer.

## What This Skill Does NOT Do

- Does not produce a finished voice skill — only a v1 scaffold the user evolves
- Does not extract another person's voice — self-applied only
- Does not auto-install into the user's plugin namespace
- Does not run continuously — one-time generator + handoff to harvest pattern
- Does not modify any existing skill, including its own SKILL.md
- Does not work without writing samples — refuses to proceed without them
- Does not include a finished tropes companion when the avoid-list is thin (<30 items)
- Does not lock the user into Eric Porres's specific structure — abstracts the pattern, not the content

## Worked Example: Eric Porres's Voice

The canonical worked example is `~/ClaudeCode_2026/shared/skills/eric-porres-voice/SKILL.md` (paired with `~/ClaudeCode_2026/shared/skills/tropes/SKILL.md`). It represents 3+ years of harvest cycles on top of an initial scaffold. Reading it before running this meta-skill is helpful — it shows what a mature voice skill looks like — but the v1 output of this meta-skill should NOT mimic its content. The meta-skill abstracts the structure, not the specific signature moves, ban list, or modes.

Specifically, the user should NOT inherit:
- Eric's signature words ("load-bearing," "instrumentation→orchestration," "surface area")
- Eric's mode labels (`[PRO]`, `[PERS]`, `[PUB]`)
- Eric's tone (irreverent-but-precise public, direct-no-corporate-prose work)
- Eric's banned vocabulary (his specific industry-cliche list)

The user SHOULD inherit:
- The structure (identity → modes → channels → patterns → tropes → tensions → examples → harvest pointer)
- The honest-v1 expectation
- The sample-required discipline
- The tropes-as-not-only-AI framing
- The worked-example-pair convention

## Future Versions (not v1)

- **v1.1 — Sample upload via file references.** Currently the user pastes samples inline. v1.1 lets them point at files in their workspace (`~/Documents/writing/*.md`) and the skill reads them.
- **v2 — Cross-mode triangulation.** v1 treats modes independently. v2 finds patterns that hold across all modes (true signature) vs. patterns mode-specific (true mode dial), producing a more reliable signature/dial separation.
- **v3 — Distill assistant.** After 8+ weeks of harvest, a complementary `/voice-distill` skill reads accumulated learnings and proposes a v2 SKILL.md with explicit diffs against v1.
- **v4 — Multi-author collaboration.** A team of writers building voice skills together, with shared trope rules and per-author signature dials. Useful for organizations.

## Known Constraints

- **The interview takes 30–60 minutes if done right.** Set the expectation at the start. Users who try to compress it produce thin v1 skills.
- **Sample quality matters more than sample count.** Five real samples beats fifteen-near-duplicates. Push for variety across modes.
- **The user's own awareness is the limiting factor for tropes.** Some users have rich pet-peeve lists; others can barely articulate what they avoid. The interview should help surface unconscious avoidances by showing concrete examples.
- **Tropes are not exclusively AI.** This is a deliberate framing choice. Treating tropes as "only AI tells" misses the larger category — the writer's full ban list across personal, industry, hedging, and AI categories. The eric-porres-voice + tropes pair models this correctly and the meta-skill inherits the framing.
- **Voice skills do not transfer between people.** Two people with similar professional backgrounds will produce very different v1 skills from this meta-skill if their samples differ. That's the design — the samples ARE the voice.
