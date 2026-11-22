# Tropes Skill Template

Optional companion to the voice skill. Generated only when the user's avoid-list (Phase 5a–5d) yielded 30+ distinct items. Below that threshold, inline the bans into the voice skill instead.

The tropes skill is a diagnostic — invoked as a second pass over a draft, after the voice check, before shipping. It scans for items on the ban-list and flags them.

---

```markdown
---
name: <firstname-lastname>-tropes
description: |
  Second-pass editor for <First Name>'s writing. Diagnostic skill paired with
  <firstname-lastname>-voice. Where the voice skill sets the affirmative target,
  this skill is the ban-list enforcer — scans drafts for items on the avoid-list
  (personal pet peeves, industry cliches, hedging language, AI tells) and flags
  them. Runs after voice check, before shipping.

  Triggers: "trope scan", "trope check", "ban list scan", "is this on-voice",
  "final pass", "/<firstname>-tropes", any invocation after a draft is complete.
version: 0.1
created_by: "<Full Name> — <canonical email>"
last_updated: <YYYY-MM-DD>
status: v1-scaffold-needs-harvest
---

# <First Name>'s Tropes — v1 Scaffold

> **This is a v1 scaffold.** Generated from the same interview that produced `<firstname-lastname>-voice`. Same evolution pattern: harvest cycles refine the skill over weeks of use.

## What This Skill Is

A diagnostic skill. Run it on a finished draft as the final pass before shipping. It scans for items the voice skill says to avoid and flags them with location and reason.

It is NOT the voice skill. The voice skill describes what <First Name> writes. This skill describes what they refuse to write. Both are necessary; they serve different functions.

## When to Run

Run this skill on:
- Any email or message the user is about to send to anyone other than themselves
- Any document, post, or article that ships under the user's name
- Any prose the user is reviewing that was drafted by an LLM (or another person) on their behalf

Skip this skill for:
- Conversational replies in chat
- Internal scratchpad work
- Code comments
- Brainstorm drafts the user is going to rewrite anyway

## Tensions With the Voice Skill (read first)

Before scanning, know that some patterns appear on the ban list below but are simultaneously signature moves in `<firstname-lastname>-voice`. The rule for these is not "ban" — the rule is "do not stack."

<from Phase 5e Tensions list, with each item explicitly listed and the meta-rule attached>

When scanning a draft, encountering a signature word once is fine. Encountering it three times is a tell. Apply the count-don't-lean rule.

## Ban Categories

### 1. Personal pet peeves
<from Phase 5a: full list of words and phrases the user has banned for personal reasons>

### 2. Industry cliches
<from Phase 5b: full list of domain-specific corporate-speak the user has banned>

### 3. Hedging and weakness language
<from Phase 5c: full list of hedge words, apology openers, permission-seeking phrases, wishy-washy adjectives>

### 4. AI-generated tells

**Vocabulary** (most evasion-resistant per Russell/Karpinska/Iyyer ACL 2025 — survived paraphrasing at 88%):
<list from Phase 5d, vocabulary subcategory>

**Sentence rhythm patterns:**
<list: triples, "not just X, it's Y," signposted conclusions, etc.>

**Structural patterns:**
<list: bullet-point everything, "It's important to note that...", pre-summary intros, mandatory headers, "Despite Its Challenges..." formula>

**Naming and authority patterns:**
<list: fictional authority names, "Dr. Sarah Chen" style invented experts, vague attribution>

### 5. Mode-specific bans

Some bans only apply in certain modes. List per-mode rules here:

- `[<MODE>]` adds: <list of bans that only apply in this mode>
- `[<MODE>]` removes: <list of items that are usually banned but acceptable in this mode>

(from Phase 6 mode calibration, where applicable)

## Scanning Workflow

When invoked on a draft:

1. **Read the draft once for context.** Identify the mode (`[WORK]`, `[PUB]`, etc.). Note the channel and audience.
2. **Apply the Tensions rule first.** For each Tension item, count occurrences. Flag any that appear 3+ times in the draft.
3. **Scan each ban category.** For each ban list (1–5 above), look for matches. Flag with line/sentence reference and category.
4. **Surface mode-specific bans.** Apply mode-specific rules from category 5.
5. **Output a structured report:**

```
## Trope scan — <draft filename or first 8 words>

### Stacking violations (Tensions)
- "<word>" appeared <N> times. Cap is 1 per document. Locations: <line refs>

### Banned vocabulary
- "<word>" — Category: <ban category>. Location: <line ref>. Suggested replacement: <if obvious>

### Hedging
- "<phrase>" — Hedge weakening claim. Location: <line ref>. Cut or commit.

### AI tells
- <pattern> — Category: <vocab / rhythm / structural>. Location: <line ref>.

### Mode-specific
- <pattern> — In [<MODE>], this is banned. Location: <line ref>.

### Net assessment
<one or two sentences: how badly does this draft need a revision pass? "Three vocabulary hits, one stacking violation, otherwise clean — quick fix" vs. "Twelve hits across four categories — this draft reads as AI-generated, recommend full rewrite">
```

## What This Skill Does NOT Do

- Does not rewrite the draft — only flags
- Does not replace the voice skill — they're paired
- Does not catch every problem — judgment-grade items still need a human review
- Does not enforce style preferences (Oxford comma, em-dashes) — those are in the voice skill, not here

## How to Evolve This Skill

Same harvest pattern as the voice skill. Each time the user runs the trope scan and decides to OVERRIDE a flag (i.e., decides the flagged item should not have been flagged), that's a learning. Conversely, each time they catch a tell the scan missed, that's a learning. Write dated entries to `learnings/`, distill periodically into this SKILL.md.

The skill compounds when used. The v1 here is the starting hypothesis.
```

---

## Notes for the meta-skill author when filling this template

- The Tensions section is the load-bearing piece — it's what prevents the skill from over-flagging signature moves. Pull directly from Phase 5e.
- Empirical anchors (Russell/Karpinska/Iyyer) are pre-loaded for the AI tells category. The user does not need to derive them; they are canonical for AI-detection literature.
- Mode-specific bans are optional — only include category 5 if the user articulated mode-specific rules in Phase 6 calibration.
- The output format spec at the bottom is the canonical scan report shape. Do not vary it; consistency is the value when the user is reviewing scan output across many drafts.
- If the avoid-list grew beyond ~80 items, suggest splitting the trope skill into two — one for general writing crutches and one specifically for AI tells. Eric's existing pattern is a single skill; the split is a v2 evolution pattern.
