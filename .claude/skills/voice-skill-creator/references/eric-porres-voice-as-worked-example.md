# Worked Example — Eric Porres's Voice + Tropes Skills (Structural Abstraction)

## Why This File Exists

The voice-skill-creator meta-skill was reverse-engineered from Eric Porres's `eric-porres-voice` and `tropes` skills — the only mature, multi-year-harvested voice skill pair the author of this meta-skill had access to during design. This file abstracts the structure of those two skills so the meta-skill (and any reader) can use them as a structural reference WITHOUT inheriting Eric's specific signature words, mode labels, ban lists, anecdote bank, or any other content unique to him.

**Read this file to understand what a mature voice skill looks like at the structural level. Do not copy any specific content from Eric's actual skills.** Eric's voice is Eric's. Anyone running the voice-skill-creator meta-skill is producing their own voice skill from their own samples; the structure transfers, the content does not.

Eric's actual voice + tropes skills are not included in this public repository. They live privately in his personal plugin namespace. This file is the only authorized structural reference.

---

## Voice Skill — Mature Structure (Eric's pattern, abstracted)

Eric's voice skill is approximately 670 lines, the result of 3+ years of harvest cycles on top of an initial scaffold. The structural pattern below is what the v1 scaffold from this meta-skill should aim toward, but at v1 it will be much shorter (~200–300 lines), thinner in each section, and with most of the depth coming through harvest over time.

The order matters. Each section builds on the prior. Do not reshuffle.

### 1. Frontmatter

Standard SKILL.md YAML — `name`, `description`, `triggers`, `version`, `created_by`, `last_updated`. Description is a single paragraph (3–6 sentences) that captures who the voice belongs to, what the skill does, and when to use it.

Eric's frontmatter (abstracted): identifies him by role and primary writing surfaces (Substack, LinkedIn, internal comms, presentations), names the modes (PRO / PERS / PUB) and one mode-naming convention (`[PRO]` etc.), and lists trigger phrases including slash command form.

### 2. Identity anchor — "Who I Am"

3–8 sentences establishing professional context, primary audience, and the writer's posture toward their craft. Not a full bio — the most relevant slice for someone who needs to write *as* this person.

Eric's section is ~5 sentences and includes: current role, prior arc (career history compressed), the dual-axis context (technical + executive), the tone he aims for ("respect for the reader's intelligence"), and the publishing surface that anchors the public mode (his Substack).

### 3. Core voice attributes — typically 3–7 named

Each attribute is a one-sentence headline followed by a paragraph that explains what it means in practice and how it shows up in writing.

Eric has 5 attributes (abstracted as types, NOT names):
- An attitude attribute (irreverent / earnest / polite / blunt — pick one and own it)
- An analytical attribute (pattern-seeking / first-principles / story-driven — pick one)
- An audience-positioning attribute (for-practitioners / for-executives / for-generalists — pick one)
- A precision attribute (specific-not-vague / numerical / example-driven — pick one)
- An evidence-stance attribute (opinionated-with-receipts / hedge-as-rigor / show-the-work — pick one)

The pattern: each attribute is binary or multi-positional. The writer commits to a position. The voice skill is more useful when these are stark choices than when they're hedged ("balanced," "moderate," "thoughtful" all read as nothing).

### 4. Modes / mode dials

2–4 named modes with explicit triggers. Eric uses three modes:

- A formal/work mode for internal team and executive audiences
- A personal/casual mode for warm and intimate writing
- A public mode for thought leadership

Each mode has its own:
- Tone description (one sentence)
- Trigger keyword (e.g., `[PRO]`, `[PERS]`, `[PUB]`)
- Channel mapping (which channels default to which mode)
- Length and structure norms
- Allowed/banned elements specific to that mode

The mode list is canonical. The agent looks up which mode to use either from explicit invocation (`[PRO]` in the prompt) or by inferring from channel.

### 5. Channel guardrails

Per-channel rules that override or specialize mode rules. Channels Eric covers:
- Email (peer / manager / external — different sub-rules)
- Slack / chat
- LinkedIn (post / comment / DM)
- Substack (long / short / headline image)
- Internal documents
- Presentations / decks
- Podcast / spoken-voice (different from written)

For each channel: typical mode default, length norms, formatting rules, and any channel-specific signature moves (e.g., "Substack: lead with a personal anecdote that becomes the structural metaphor of the piece").

### 6. Always-on constraints

Rules that apply across all modes and channels. Eric's are conventions like Oxford comma policy, no exclamation marks (in PUB mode specifically), avoid corporate prose, prefer concrete-over-abstract. 3–8 items, terse.

### 7. Writing mechanics

Subdivided into:

**Sentence structure** — Length norms, opener patterns, closer patterns, rhythm preferences (mixed length / consistently short / etc.).

**Formatting philosophy** — Use of headers (frequent / rare), bullets (when / when not), em-dashes, semicolons, capitalization conventions, code formatting if technical.

**Signature patterns** — Specific structural moves the writer uses repeatedly. Eric has ~10 named signature patterns (e.g., "Scene-drop opener," "The Reframe," "Pattern recognition pivot"). At v1, expect 2–4. The list grows through harvest.

### 8. Lexical sections — USE FREELY, NEVER USE, AI-CLICHÉ WATCHLIST, WORD SWAPS, USE SPARINGLY

**USE FREELY** — signature words the writer uses deliberately. Eric has ~30 items at maturity. Each entry is one word/phrase plus a usage note. Critical: USE FREELY is *permission*, not *instruction*. The meta-rule (see Tropes section) is: don't stack. Three uses of the same signature word in one document is a tell, regardless of whether each individual use is on-voice.

**NEVER USE** — banned vocabulary. Eric has ~15 items. Each entry is the banned word plus a one-line reason or category.

**AI-CLICHÉ WATCHLIST** — vocabulary that screams AI-generated. Eric has ~50 items here, drawn primarily from the Russell/Karpinska/Iyyer (ACL 2025) canonical list plus his own additions. This is the densest section in the file and the one with the strongest empirical backing.

**WORD SWAPS** — pairs that name a banned word and the preferred replacement. Eric has ~5 items. Examples not from Eric's list: "leverage" → "use", "utilize" → "use", "in order to" → "to".

**USE SPARINGLY** — words that are not banned but should not be defaults. Acceptable in moderation; flagged if frequent. ~5 items at maturity.

### 9. Metaphor domain

A short section establishing the mental-model substrate the writer reaches for. Eric's metaphor domain is martial arts, music, philosophy, and triathlon — drawn from his actual hobbies and background. The section names the domains and gives 2–3 example metaphor patterns from each.

The pattern: metaphors are powerful in writing only when they're consistently from a coherent domain. A writer who reaches for a sports metaphor in one paragraph and a cooking metaphor in the next produces voice incoherence. The metaphor domain section captures the writer's actual mental-model substrate so the LLM doesn't substitute generic LLM-default metaphors.

### 10. Analytical framework

A section titled like "Questions I Always Ask" or "How I Approach New Problems." Eric has ~7 questions he applies to most analytical writing. The section is short (one line per question) and operationally specific — not philosophical.

### 11. Prompt DNA / structural prompt pattern (Eric-specific, may not generalize)

Eric has a section called "Prompt DNA: RCToBR" naming his structural pattern for prompting LLMs. This section is unique to him — most users will not have a personal prompt-engineering convention. **The meta-skill should NOT generate this section by default.** Only include if the user explicitly articulates a structural pattern they use repeatedly.

### 12. Measurement vocabulary (also Eric-specific, often not relevant)

Eric has a section on adoption signals and ROI vocabulary because his domain (Chief AI Officer, prior CMO) demands operational metrics language. Most users will not have this. Skip unless the user explicitly works in a measurement-heavy domain (finance, ops, product, marketing).

### 13. Content types & adaptations

Per-format rules. Each format gets 1–2 paragraphs covering: typical length, structure conventions, opener and closer patterns, things to lean into, things to avoid. Eric covers ~8 formats. At v1, expect 3–4. The list grows as the writer encounters new formats.

### 14. Philosophical stances

3–6 short paragraphs articulating positions the writer holds about their craft, their domain, or their audience. Examples (not from Eric's): "I think most strategy writing hides behind frameworks; I aim for arguments instead." Or "I believe AI accountability is a journalism problem before it's a regulatory problem."

This section is harvested-grown. At v1, expect 2–3 stances; growth comes through the writer noticing patterns in what they argue for repeatedly.

### 15. Canonical anecdote bank

A short list of stories the writer reuses across drafts. Each entry: 2–3 sentences naming the anecdote and what it illustrates. Not the full story — the LLM doesn't need full stories; it needs to know the anecdote exists and what claim it lands.

Eric has ~10 anecdotes at maturity. At v1, expect 2–4 — anecdotes accumulate across years of writing.

### 16. Worked examples library

5+ short illustrative samples showing the voice in action. Each example is 1–4 lines, named with a label like "Strong opening" or "The reframe" or "Scene-drop." This is the section the LLM cites most often during use — it's the densest training signal in the file.

Eric has ~7 named examples at maturity.

---

## Tropes Skill — Mature Structure (Eric's pattern, abstracted)

Eric's tropes skill is approximately 220 lines. Shorter than the voice skill because tropes are narrower (a ban list with diagnostic logic, not a full style guide).

The tropes skill is paired with the voice skill but distinct. Voice = affirmative target. Tropes = ban list enforcer. The pair is invoked sequentially: voice check first (does the draft sound like the writer), tropes scan second (does the draft contain banned items).

### 1. Frontmatter

Standard SKILL.md YAML. Description names the diagnostic role and the pairing with the voice skill explicitly.

### 2. Tensions with Voice — the load-bearing section

This is the section that prevents the tropes skill from over-flagging signature moves. Eric has 6 tensions:

- A punctuation pattern that's both a signature move and an AI tell (e.g., heavy em-dash use)
- A reframe pattern (e.g., "Not X, but Y") that's both signature and a known AI rhythm
- A tricolon / three-beat rhythm that's both signature and an AI tell
- A fragment-for-emphasis pattern that's both signature and an AI tell
- A historical analogy pattern (signature when grounded, AI tell when generic)
- An opener pattern (e.g., "Here's X") that's both signature and AI tell

For each tension: the meta-rule is "don't ban, count." A signature move used once is on-voice. Used three times in one document is a tell. The cap is per-document, not per-section.

This section's entries should be 5–10 at maturity. At v1, expect 2–4 — tensions are subtle and hard to articulate without harvested evidence.

### 3. Absorption List — items added to the voice skill's watch

A list of high-leverage AI-cliché items that the writer specifically wants caught on every scan, even though they're not in the writer's USE FREELY or other voice-skill sections. Each entry is 3–4 sentences:
- The pattern name
- Why it's an AI tell
- An example of how it shows up
- The fix or alternative

Eric has ~14 items in his absorption list. Examples (not from his actual list — synthesized):
- Magic adverbs ("quietly," "carefully," "thoughtfully") used as filler
- "Serves as" dodges (avoidance of direct claims)
- Invented concept labels (capitalizing a phrase to imply it's a known framework when it isn't)
- Superficial "-ing" analyses ("By doing X, the team is doing Y")
- False ranges ("This represents a 40% to 60% improvement...")
- Pre-built analogies ("Think of it as..." / "It's like...")
- Counterfactual openers ("Imagine a world where...")
- Stakes inflation ("This isn't just X — it's the future of Y")
- Signposted conclusions ("In conclusion," "To sum up")
- Acknowledge-and-dismiss ("Despite Its Challenges...")
- Bold-first bullets (every list item starts with bold word)
- Unicode arrows and smart quotes (typographic AI tells)
- Fractal summaries (every section ends with a recap of what was just said)
- One-point dilution (a clean argument padded with multiple "examples" that all say the same thing)

At v1, this list will be 4–8 items. Most absorption-list entries grow through tropes-scan harvests where the writer encounters a new tell in their drafts and adds it.

### 4. Canonical Trope Reference — categorized

A categorized reference list of AI-writing tropes. Eric's categories:

- Word Choice (vocabulary, phrasing)
- Sentence Structure (rhythms, openers, closers)
- Paragraph Structure (length, transitions)
- Tone (sycophancy, hedging, faux-formality)
- Formatting (headers, bullets, bold, capitalization)
- Composition (overall argument shape, recap loops)

Each category has 3–10 items. Each item is one line or a short paragraph naming the pattern.

The empirical anchor for the AI-tells subset is Russell, Karpinska, and Iyyer (ACL 2025) on AI-text detection. Their canonical vocabulary list survived paraphrasing at 88% — this is why vocabulary-banning is the highest-leverage AI-detection intervention.

The Canonical Trope Reference is the section most directly transferable to other users. Most of the AI-specific items will appear in any tropes skill. The Tensions section (item 2 above) and the writer-specific bans in their voice skill are where individuality emerges.

---

## What to Inherit, What NOT to Inherit

When the meta-skill walks a user through producing their voice + (optional) tropes skills, it should inherit from Eric's pattern:

- The 16-section structure of the voice skill (not all sections will appear at v1, but the order and the section types should match)
- The 4-section structure of the tropes skill
- The voice/tropes pairing pattern (affirmative + diagnostic)
- The "don't ban, count" rule for Tensions
- The honest-v1 expectation
- The harvest-cycle pattern for evolution
- The empirical anchoring of the AI-tells subset (Russell/Karpinska/Iyyer)

It should NOT inherit:

- Eric's specific signature words (they're his — emerged from his samples and his harvests)
- Eric's mode labels (`[PRO]`, `[PERS]`, `[PUB]`) — let users name their own, or default to neutral generic labels
- Eric's tone (irreverent-but-precise, opinionated-with-receipts)
- Eric's metaphor domains (martial arts, music, philosophy, triathlon)
- Eric's anecdote bank
- Eric's signature patterns (Scene-drop, The Reframe, etc.)
- Eric's Prompt DNA section (his RCToBR pattern is his)
- Eric's measurement vocabulary section (most users don't need it)

The structure transfers; the content doesn't. That distinction is the entire point of running the meta-skill instead of copying Eric's files.

---

## How the Meta-Skill Uses This File

During Phase 8 (Generate v1 SKILL.md), the meta-skill should:

1. Load `references/voice-skill-template.md` as the canonical skeleton.
2. Use this file (the worked example) as the structural depth reference — for each section in the template, this file describes what the mature version looks like, what to include at v1, and what's specific to Eric vs. universal.
3. Cross-reference the Phase 5 tropes interview output against this file's "Tensions with Voice" structural pattern to ensure the user's Tensions section is properly bridged (signature moves that overlap with bans, with the don't-ban-count meta-rule).
4. Use the "What to Inherit, What NOT to Inherit" section above as a final pass before generating output — verify the v1 output is structurally Eric-derived but content-wise the user's.

If the meta-skill ever produces output that contains Eric's signature words, mode labels, or anecdote bank, it has failed the abstraction. The structure should be present; the content should be the user's.

---

## A Note on Mature Voice Skills as Worked Examples Generally

Eric's voice + tropes skills are the worked example used here because they were available to the meta-skill's author. They are not the only valid mature voice-skill pattern, and they are not universally optimal.

Other writers building toward mature voice skills may diverge structurally — they may not need a metaphor domain section (if metaphors aren't a primary tool), they may need additional sections (e.g., a writer who works heavily in dialogue may need a "How I write voiced characters" section), or they may use radically different mode/channel structures (e.g., a fiction writer's modes are not work/personal/public — they're third-person-omniscient/first-person-protagonist/screenplay-direction).

The meta-skill should treat Eric's pattern as a reasonable default starting point — the structural depth is well-tested across years of use — but should be willing to deviate when the user's interview surfaces patterns that don't fit. A v1 voice skill that adds a section Eric doesn't have, because the user's writing genuinely needs it, is a better v1 than one that forces every user into Eric's exact 16-section structure.

The discipline: structure should serve the writer's voice, not the other way around.
