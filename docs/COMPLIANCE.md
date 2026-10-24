# YouTube compliance agent

Every video is checked against a catalog of YouTube rules before it is approved, again when it is repaired or polished, and the rules are listed in `compliance.RULES` with the official page each came from, the day it was read (20 Oct 2026) and an honest status. Only VERIFIED rules are enforced. CONFLICTING and UNVERIFIED items are watched, never stated as fact (CLAUDE.md A).

| Rule | Check | What happens when it fails |
|---|---|---|
| `metadata_valid` (title 100 chars, description 5000 bytes as sent, no `<` `>`, tags 500 chars with commas and quotes) | deterministic, on the description exactly as uploaded (`compliance.final_description`) | block; the fixer sanitises it; `upload.upload` refuses to send what YouTube would reject, without counting a failed attempt |
| `title_matches`, `thumbnail_matches` (misleading metadata is a deceptive practice) | the AI review's one call reads title, description and thumbnail text against the narration | block; the fixer writes a new title or description, or a new thumbnail text made from the narration (`thumbnail.hook_for`) and the thumbnails again |
| `originality` (no reading aloud of text we did not write) | share of the narration's 8-word runs found in the source article; warn 6%, block 15% (our videos measured 0 to 4.1%) | warn is reported; block: the fixer rewords the copied lines and the video is made again |
| `template_variety` (templated, repetitive videos) | existing variety checks and the Risks card | the fixer varies the script |
| `kids_signals` (kid-directed wording may make YouTube treat it as made for kids) | deterministic words in title, description, tags | warn; you decide |
| `ai_disclosure` | upload sets `containsSyntheticMedia`; a test keeps the art style an illustration | n/a |
| `api_private_lock` CONFLICTING | `safety.check` reports a video still private after its slot and names the possibility | Autopilot pauses and tells you; the first public video settles it |
| `phone_verification` UNVERIFIED | the upload survives a refused thumbnail, records `thumbnail_error` and tells you | add the thumbnail in YouTube Studio |

## Thumbnails and chapter titles
- The hook is written from the narration (`thumbnail.hook_for`): a candidate the narration does not support, or one used before, is skipped.
- Frames for the three layouts are cut above or below the burned-in caption band, and one vision reading prefers frames that show the story's own subject (a frame showing another place is left for last). A reading that cannot run changes nothing.
- Chapter titles are read by the AI review (they are in the public description), and a chapter whose lines were rewritten gets a new title from its current lines, in the list and in the description.
- Repairs wait for the day's money cap: a video's two tries are not spent on weak free models.

## Keeping it current
`newswatch.policy_watch` reads the official pages every morning. When a page a rule depends on changes after the rule's `verified` date, the Risks card row "YouTube rules checked on every video" turns to watch and names the rules. Read the page, then re-verify the rule and update its `verified` date.

## Adding a rule
1. Read the official page and write down what it says. If it is not on an official page, mark the rule UNVERIFIED and do not enforce it.
2. Add it to `compliance.RULES` (source, page key from `newswatch.POLICY_PAGES`, status, severity, remedy).
3. Add the check to `compliance.checks` (deterministic) or to the AI review prompt (judgement), a remedy in `fixer.fix`, and the tests first.

## Limits
The thumbnail judgement reads the thumbnail's text, not its pixels. Copy detection catches near-verbatim runs, not paraphrase. A model review varies between runs.

## Re-verification log
- 2026-10-24: the Spam, deceptive practices and scams page (policy watch, 06:10 UTC) gained two sentences: creators should disclose AI-generated or meaningfully altered content, and the disclosure is not a free pass to break policies. Nothing was removed. Our uploads set `containsSyntheticMedia` and add an AI-narration line, so `title_matches` and `thumbnail_matches` keep their rules; `verified` moved to 2026-10-24 for both.
