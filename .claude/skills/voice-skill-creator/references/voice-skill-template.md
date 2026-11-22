# Voice Skill Template

This is the canonical skeleton the meta-skill uses to generate the user's v1 voice SKILL.md. Fields in `<angle brackets>` are interview-derived. Fields in `[square brackets]` are guidance for what should fill in.

---

```markdown
---
name: <firstname-lastname>-voice
description: |
  Voice, tone, and style guide for <Full Name> — <Professional Context>.
  Use this skill when writing content as <First Name> or in their voice:
  <list of primary surfaces — emails, posts, articles, internal docs>.

  Triggers: "write in <first name>'s voice", "<first name> voice",
  "/<firstname>-voice", "draft for <first name>", "<first name>'s tone"
version: 0.1
created_by: "<Full Name> — <canonical email>"
last_updated: <YYYY-MM-DD>
status: v1-scaffold-needs-harvest
---

# <Full Name>'s Voice — v1 Scaffold

> **This is a v1 scaffold.** It was generated from an interview and a sample harvest. It is a hypothesis to refine, not a canonical document. Run `/cos`-style harvest cycles for 4–8 weeks of real use before treating any section as locked. See `HARVEST-CYCLE.md` in this directory for the evolution pattern.

## Identity

<2–4 sentences from Phase 1: name, role, organization, what they do, who they write for>

## Modes

The voice flexes across <N> modes. Use the mode dial to select tone, length, and structure.

### `[<MODE-1>]` — <name>
<3–5 sentences from Phase 6 calibration: what it sounds like, when to use it, channel mapping, banned and allowed elements>

### `[<MODE-2>]` — <name>
<3–5 sentences>

### `[<MODE-3>]` — <name>
<3–5 sentences, if applicable>

If the user does not specify a mode, infer from the channel:
- <Channel> → `[<MODE>]`
- <Channel> → `[<MODE>]`
- (continue for each channel mapped in Phase 2)

## Lexical Patterns

### USE FREELY (signature words)

These words are part of <First Name>'s signature voice. Use deliberately, but do not stack — three uses of the same signature word in one document is a tell, regardless of whether each individual use is on-voice.

- <word> — <usage note>
- <word> — <usage note>
- (3–10 items from Phase 4 lexical analysis)

### AVOID

Banned vocabulary. Do not use these in any mode unless quoting someone else.

- <word> — <reason or category>
- <word> — <reason or category>
- (5–20 items from Phase 5a + 5b + 5c)

## Sentence-Level Patterns

### Length and rhythm
<2–3 sentences from Phase 4 sentence-level analysis: average sentence length, mix preference, opener and closer patterns>

### Punctuation conventions
- Oxford comma: <yes / no>
- Em-dashes: <frequent / occasional / rare>
- Exclamation marks: <never / rare / mode-dependent>
- Semicolons: <frequent / occasional / rare>
- Ellipses: <usage note>

## Structural Patterns

### Argumentation style
<from Phase 4 structural: assertion-first / evidence-first / story-led / data-led, with example>

### Paragraph and section conventions
- Paragraph length: <terse / standard / long>
- Headers: <frequent / rare / mode-dependent>
- Bullets: <when to use, when to avoid>
- Lists of three: <signature move / acceptable / avoid>

### How <First Name> handles disagreement
<1–2 sentences from Phase 4: direct pushback / Socratic / hedge-then-pivot / agree-then-redirect>

## Tropes — What <First Name> Refuses to Write

Half of voice is what you avoid. This section is the ban list across five categories.

### Personal pet peeves
<from Phase 5a: list of words and phrases the user personally cringes at>

### Industry cliches
<from Phase 5b: domain-specific corporate-speak the user has banned>

### Hedging and weakness language
<from Phase 5c: hedge words, apology openers, permission-seeking phrases, wishy-washy adjectives>

### AI-generated tells
<from Phase 5d: vocabulary, sentence rhythm, structural patterns flagged as AI tells>

### Deeper canonical references
For the empirical anchor on AI tells, see Russell, Karpinska, and Iyyer (ACL 2025) on AI-text detection. The vocabulary list survived paraphrasing in their experiments at 88% — vocabulary-banning is the highest-leverage AI-detection intervention.

## Tensions — Signature Moves That Overlap with the Avoid-List

Some patterns are simultaneously <First Name>'s signature move AND on a generic AI tell list. The rule is NOT to ban them; the rule is to flag stacking.

<from Phase 5e: tension list with specific guidance per item>

Example format:
- **<word or pattern>** — Signature use is permitted and characteristic. Failure mode is stacking — three uses in one document is a tell. Count, don't lean.

## Worked Examples

The single highest-leverage section in this skill. These before/after pairs encode the voice better than any prose description.

### Example 1: <one-line context — e.g., "Following up on a meeting">
**Generic version:**
> <generic AI-style draft>

**<First Name>'s version:**
> <user's actual version from Phase 7>

What changed:
- <one or two sentences naming the specific signature moves applied>

### Example 2: <context>
<format repeats>

### Example 3: <context>
<format repeats>

(3–5 pairs from Phase 7)

## How to Evolve This Skill

This is v1. The pattern from here:

1. **Install and use.** Drop this skill into your agentic system per `INSTALL.md`. Use it for 4–8 weeks on real writing tasks.
2. **Note as you go.** Each session, observe: did the output sound like you? What did you rewrite? What did the skill miss or get wrong?
3. **Weekly harvest.** Once a week, write a dated learning entry to `<this-skill-directory>/learnings/YYYY-MM-DD-<slug>.md`. Format: what was observed, what to potentially change, evidence quote, confidence rating. See `HARVEST-CYCLE.md` for the full pattern.
4. **Distill periodically.** After 8 weeks of harvests, do a distill pass — read all learnings, edit this SKILL.md to incorporate accumulated signal. Bump version to 1.0 when the skill feels reliable. Continue evolving forever.

The skill compounds in value with use. The v1 here is a hypothesis. The v∞ is the version that's been harvested for years and accurately encodes a voice.

## Companion Skill: <First Name>-Tropes

If the avoid-list in the Tropes section above grew rich enough during the interview (30+ items), a separate `<firstname-lastname>-tropes` skill was generated as a companion. Run it as a second pass over drafts before shipping. The voice skill sets the affirmative target; the tropes skill is the ban-list enforcer.

(Omit this section if no companion was generated.)

## What This Skill Does NOT Do

- Does not write content automatically — invoked at the top of writing sessions
- Does not enforce a finished voice — the v1 is a starting hypothesis
- Does not replace the harvest cycle — install + use + learn + distill is the pattern
- Does not transfer to other writers — this voice belongs to <First Name>

## Known Constraints

- v1 was generated from <N> writing samples. More samples produces a more reliable skill — when in doubt, harvest more.
- The Tensions list is the most fragile section. Items that feel like signature moves at v1 may turn out to be AI tells the user inherited unconsciously. The harvest cycle is the right mechanism to surface that.
- This skill assumes the writing context is professional or public. Highly personal modes (private journaling, intimate communication) are typically not encoded here — voice in those contexts is private and shouldn't be agentic anyway.
```

---

## Notes for the meta-skill author when filling this template

- Quote at least 2 examples from the user's actual samples in the Lexical Patterns and Sentence-Level Patterns sections. Concrete > abstract.
- The Worked Examples section is the section that will be cited most often during use. Pick the strongest 3–5 pairs from Phase 7. Quality over quantity.
- The Modes section is the section users most often skip in early use. Make sure each mode has a clear trigger keyword and channel mapping.
- The Tensions section should be tight (3–7 items). If it grows beyond that, items are probably belonging in either USE FREELY or AVOID, not in the gray zone.
- Frontmatter version starts at 0.1 deliberately — signals v1-scaffold and is below the conventional 1.0 "stable" threshold.
- Reference Eric Porres's voice skill as the worked example for the user, but do NOT copy any specific signature moves, mode labels, or trope items from it. Abstract the structure only.
