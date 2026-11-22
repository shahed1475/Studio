# Harvest Cycle Template

Generated alongside the v1 voice skill. Describes the evolution pattern after install.

---

# Harvest Cycle — How Your Voice Skill Compounds in Value

Your voice skill is v1. The version that actually sounds like you is v∞ — and you only get there through use, observation, and dated learnings that compound over weeks.

This document describes the pattern. It's the same pattern Eric Porres uses on `eric-porres-voice` and `tropes` (3+ years and counting), abstracted for your voice skill.

## The Three-Layer Model

Your voice skill lives in three layers:

| Layer | Role | Where it lives |
|---|---|---|
| Raw verbatim store | Append-only record of what you wrote and what the skill produced | Conversation logs, drafts you saved, deep memory if you have it |
| LLM-owned middle | Dated observations the skill harvested across sessions | `<this-skill-directory>/learnings/` |
| Human canonical | The skill itself | `<this-skill-directory>/SKILL.md` |

The harvest cycle moves signal from the raw layer (what happened) through the middle layer (what was observed about what happened) into the canonical layer (what the skill should encode going forward).

## The Cycle

### Daily — Use the skill

Use the voice skill on real writing tasks. Don't manufacture practice writing for the skill — use it on actual emails, posts, documents, messages.

For each session, after the skill produces output, ask three questions silently:

1. **Did the output sound like me?** If yes, no harvest needed. Move on.
2. **What did I rewrite?** If you edited the output before sending, the edit is signal. The pattern you reverted to is more "you" than the pattern the skill produced.
3. **Did anything surprise me?** Either positive ("the skill caught a phrasing I would never have thought to use deliberately, and it landed perfectly") or negative ("the skill insisted on a structure I never use"). Surprises are the highest-value signal.

Do not try to harvest in the moment. Note silently and move on.

### Weekly — Harvest

Pick a fixed time once a week (Friday afternoon, Saturday morning, whatever fits). Spend 15–30 minutes writing dated learning entries.

Re-read the week's writing where the voice skill was invoked. For each session, ask:

- Was the output on-voice or off-voice?
- If off-voice, what specifically went wrong? Quote the exchange.
- What rule, ban, or pattern in the SKILL.md needs to change to fix it?

Write each observation as a dated entry to `<this-skill-directory>/learnings/YYYY-MM-DD-<slug>.md`. Format:

```markdown
---
date: YYYY-MM-DD
target_skill: <firstname-lastname>-voice
confidence: high | medium | low
source_session: <session identifier — file path, conversation slug, or date>
still_valid_as_of: YYYY-MM-DD (one year out)
status: active
---

# <One-line observation title>

## What happened
Narrative. Quote the specific exchange. Show what the skill produced and what you wanted.

## What to potentially change
Concrete suggestion. Name the section of SKILL.md that would change.

## Evidence
- Specific quotes from the session
- Related prior learnings (if any)

## Notes for distill pass
Anything the future distill pass should know.
```

A typical week produces 0–5 learnings. Most weeks produce 1–2. Zero is acceptable; manufactured learnings are not. If nothing was off-voice this week, write nothing.

### Periodic — Distill

Every 8–12 weeks, do a distill pass. Read all the learnings since the last distill. Look for:

- **Recurring observations** — same observation in 3+ learnings probably means the skill needs the change
- **Conflicts** — two learnings that contradict each other; pick a side or note the tension explicitly
- **Aging out** — learnings past their `still_valid_as_of` date or that have been superseded by newer signal

Edit `SKILL.md` to incorporate the recurring observations. Bump the version (0.1 → 0.2 for first distill, 0.2 → 0.3 for second, etc.). Once the skill feels reliable across a wide range of writing tasks — typically 6–12 months of harvests — bump to 1.0.

The distill pass is the most cognitively demanding step in the cycle. Don't rush it. The discipline of refusing to distill on flimsy signal is how the skill stays sharp instead of bloating into a "comprehensive" doc nobody actually uses.

## What NOT to Do

Don't edit SKILL.md mid-week based on a single bad output. Single observations are noise; recurrence is signal.

Don't manufacture learnings to fill the directory. Empty harvest weeks are correct. Voice skills compound across many weeks of clean signal, not many weeks of padded entries.

Don't delete old learnings. Even superseded learnings are part of the historical record. Mark them archived in frontmatter; never remove.

Don't skip the distill pass. A learnings/ directory with 50 entries that have never been distilled into SKILL.md is a graveyard. The compounding only works if the canonical layer absorbs the signal periodically.

Don't share your voice skill. It belongs to you. Sharing it with another writer produces ghostwriting; voice skills are individual artifacts.

## When to Stop

You won't. Voice skills evolve as long as you write. Eric Porres's voice skill was scaffolded years ago and is still being harvested on. The expectation is not "ship a finished voice skill"; the expectation is "make the skill better than it was last quarter."

If the cycle becomes burdensome, that's a signal that either (a) the skill is mature enough that weekly harvests aren't producing signal — switch to monthly, or (b) you're not writing enough for a voice skill to be useful — that's fine; voice skills are for people whose writing volume justifies the maintenance.

## Tools That Help

- **A `/harvest` or `/cos` skill** — automates the weekly harvest pattern. If your agentic system has chief-of-staff style automation, use it. Eric's `chief-of-staff` skill handles the weekly run; it's portable.
- **Deep memory or a transcript archive** — lets you search across past sessions for "where did the skill produce off-voice output." Without one, you're harvesting from short-term recall, which is fine but lower-fidelity.
- **A version-controlled SKILL.md** — git the skill directory. Every distill pass is a commit. Reviewing the diff over time is how you see your own voice evolve.

## Reference: Eric Porres's pattern

For the canonical worked example of this cycle, see Eric's voice skill at `~/ClaudeCode_2026/shared/skills/eric-porres-voice/SKILL.md` and the harvest log at `~/ClaudeCode_2026/shared/skills/eric-porres-voice/learnings/log.md`. The structure is the same; the content is his. Use it as a model for what mature looks like, not as a template to copy.
