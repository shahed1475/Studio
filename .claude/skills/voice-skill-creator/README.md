# Voice-as-a-Skill

A self-applied interviewer that walks first-time agentic-system users (Cowork, Claude Code, Codex, or any Skills-aware client) through producing their own v1 voice skill — a portable SKILL.md their LLM uses to write in their actual voice across emails, posts, documents, and other surfaces.

The output is explicitly v1 — a starting scaffold, not a finished voice. Voice skills compound across months of harvest cycles. This project ships the scaffold and the harvest pattern; the user evolves the skill from there.

## What's in this repo

| File | Role |
|---|---|
| `SKILL.md` | The meta-skill itself — the canonical interviewer that produces a user's voice skill |
| `references/voice-skill-template.md` | Skeleton the meta-skill fills in to produce the user's `<name>-voice/SKILL.md` |
| `references/tropes-skill-template.md` | Optional skeleton for a paired tropes (avoid-list) companion skill |
| `references/install-instructions-template.md` | Per-system install paths (Cowork, Claude Code, Codex, direct API) |
| `references/harvest-cycle-template.md` | The post-install evolution pattern — how the v1 scaffold becomes a mature voice skill over weeks |
| `SESSION.md` | Project context for any agent reading the repo cold |
| `ARCHITECTURE.mermaid` | Visual map of the meta-skill's flow |

## Quick start

If you have a Skills-aware system already configured:

1. Drop `SKILL.md` into your skills directory (per your client's convention — see `references/install-instructions-template.md` for paths).
2. Trigger the skill: "create my voice skill" or `/voice-creator`.
3. Follow the 8-phase interview. Bring 5–15 writing samples across modes when you start; the skill refuses to proceed without samples.
4. Output: a `<your-name>-voice/` directory ready to install in your plugin namespace, plus optional `<your-name>-tropes/` companion, plus `INSTALL.md` and `HARVEST-CYCLE.md`.
5. Install the generated voice skill and use it. Run weekly harvests for 4–8 weeks. Distill into v1.0 when ready.

## Design principles

Voice belongs to the writer. A voice skill encodes one person's writing patterns; sharing it produces ghostwriting, not voice. Each writer runs the meta-skill on their own samples.

Samples are required. Without writing samples, pattern extraction hallucinates voice, and the skill refuses to proceed without five-plus samples across modes.

Tropes are not exclusively AI. What you avoid writing is half of voice, and the avoid-list spans personal pet peeves, industry cliches, hedging language, and AI tells. Treating tropes as only AI tells misses the larger category, which is a deliberate framing departure from the AI-detection literature.

v1 is a hypothesis, not a deliverable. The skill ships with the explicit expectation that the user will run harvest cycles for eight-plus weeks before treating any section as canonical.

Voice skills live in the human canonical layer of Karpathy's three-layer model. The middle layer holds dated harvest observations. The raw layer (writing logs, deep memory) is the substrate. The harvest cycle moves signal up the layers over time.

## Worked example

The canonical worked example for this meta-skill is Eric Porres's voice skill, which represents 3+ years of harvest cycles on top of an initial scaffold. It is a separate artifact (not included in this public repo) and is referenced in `SKILL.md` as a structural model — abstract the structure, not the content.

## Influences

- **Karpathy's three-layer model** for LLM-augmented knowledge work — raw store, LLM-owned middle, human canonical
- **Russell, Karpinska, and Iyyer (ACL 2025)** on AI-text detection — empirical anchor for the AI-tells subset of the tropes section, particularly the canonical vocabulary list that survived paraphrasing at 88%
- **Anthropic's Skills format** — the SKILL.md frontmatter convention and trigger-phrase pattern

## License

Apache 2.0. See `LICENSE`.

## Status

Public release. The meta-skill is functional and tested against Eric Porres's existing voice + tropes skills (used as the structural reverse-engineering source).
