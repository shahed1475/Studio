# SESSION.md

## Project Context

Voice-as-a-Skill is a meta-skill that produces voice skills. It is a public-facing project staged in `public/voice-as-a-skill/` (per the CLAUDE.md convention that all `public/` subdirectories become public GitHub repos under `ericporres`). The meta-skill was reverse-engineered from Eric Porres's `eric-porres-voice` and `tropes` skills — both private — by abstracting the structural pattern (identity → modes → channels → patterns → tropes → tensions → examples → harvest pointer) and removing all Eric-specific content (signature words, mode labels, ban lists).

The work was scoped during a Cowork session on 2026-05-08:
- Self-applied (the user is the writer whose voice gets extracted)
- Output is a SKILL.md scaffold (not a finished skill)
- Interviewer pattern (the meta-skill conducts a structured interview)
- Tropes section explicitly broader than AI tells (personal pet peeves + industry cliches + hedging + AI tells + tensions)

The Beyond Reason article path is on the table as the public launch artifact. The thesis under consideration: voice as a skill — meaning, voice should be encoded as a portable, evolvable, compoundable artifact (SKILL.md format) rather than as a one-shot description re-explained to an LLM each session.

## Current State

- v1 SKILL.md complete (~470 lines, comprehensive interviewer pattern with 11 phases including setup, expectation-setting, sample harvest, pattern extraction, tropes interview across 5 sub-categories, mode dial calibration, worked examples library, generation, optional companion, install instructions, and exit confirmation)
- Four reference templates in `references/`: voice skill template, tropes skill template, install instructions, harvest cycle pattern
- README.md, SESSION.md, ARCHITECTURE.mermaid in place per the public/ convention
- Not yet tested end-to-end with a real first-time user
- No GitHub repo created yet (waiting on Eric's launch decision)

## Next Actions

1. Review the SKILL.md end-to-end for voice-and-tropes pass before any external sharing (per the CLAUDE.md "Voice Check Before Deliver" rule for prose that ships with Eric's name attached)
2. Decide on launch artifact: Beyond Reason article, blog post, README-only release, or quiet release with no marketing
3. If Beyond Reason article path: draft the substack-article.md staging the underlying thesis (voice-as-a-skill as a knowledge-work pattern, not a marketing pitch)
4. Test the skill end-to-end: have Eric or a test user run it on a small sample set and verify the v1 output is reasonable
5. Create the GitHub repo under `ericporres/voice-as-a-skill` (public per the public/ convention) when launch decision is made
6. Add LICENSE (Apache 2.0 per README) before publication
7. Optional: build a `<eric>-voice` regeneration as the worked example — run the meta-skill against a sample of Eric's writing and compare the output to his actual mature voice skill, as a calibration test

## Session Log

| Date | Summary | Outcome |
|------|---------|---------|
| 2026-05-08 | Scoped meta-skill design via Cowork conversation. Wrote v1 SKILL.md (8-phase interview pattern, expanded to 11 phases for setup + tropes companion + install + exit). Wrote four reference templates. Confirmed scope: self-applied, interviewer pattern, scaffold output, tropes-not-only-AI framing. Moved staging from `shared/skills/voice-skill-creator/` to `public/voice-as-a-skill/` per Eric's redirect — this is a public-repo-shaped project, not a personal plugin. | v1 ready for review and end-to-end test |

## Known Issues

- The meta-skill has not been run end-to-end against a real first-time user. Phase boundary discipline (refusing to skip Phase 3 sample harvest) and the "v1 expectation set repeatedly" pattern are untested in practice — they could prove either too rigid or too lax in real use.
- The tropes-skill-template references the Russell/Karpinska/Iyyer paper (ACL 2025) as canonical empirical anchor for AI tells. If the paper is later superseded, the template needs updating. The reference is currently inline; future versions may externalize it to a separate `references/empirical-anchors.md`.
- Worked-example reference to `eric-porres-voice` and `tropes` is by path. If this repo ships publicly without those skills being also public, the reference becomes a dangling pointer. Two options: publish those skills too (not Eric's preference — they're personal artifacts), or reference them by structural description only and remove the path reference. Currently the SKILL.md references them by name and structure, which is the right balance — readers can see the pattern Eric uses without needing access to his actual skill content.
- The skill refuses to extract someone else's voice (self-applied only). This is a deliberate design choice but worth flagging to early users — the most common ask for "voice skills" in the wild is ghostwriting use cases (CoS or comms team writing for an executive). Those use cases are out of scope for this skill and would need a different skill design.

## Key Files

- `SKILL.md` — the canonical meta-skill, the entry point for any user invocation
- `references/voice-skill-template.md` — output template for the user's voice SKILL.md
- `references/tropes-skill-template.md` — output template for the optional companion
- `references/install-instructions-template.md` — multi-system install guidance
- `references/harvest-cycle-template.md` — post-install evolution pattern (the most important file for setting v1 expectations correctly)
- `README.md` — public-facing overview
- `ARCHITECTURE.mermaid` — visual map of the meta-skill's flow

## Reference Materials (not in repo)

- `~/ClaudeCode_2026/shared/skills/eric-porres-voice/SKILL.md` — the canonical worked example (Eric's mature voice skill, 3+ years of harvests). Referenced structurally in this repo's SKILL.md.
- `~/ClaudeCode_2026/shared/skills/tropes/SKILL.md` — Eric's tropes companion. Referenced structurally.
- `~/ClaudeCode_2026/shared/skills/chief-of-staff/SKILL.md` — the harvest pattern Eric uses; referenced as the canonical evolution mechanism in `references/harvest-cycle-template.md`.
