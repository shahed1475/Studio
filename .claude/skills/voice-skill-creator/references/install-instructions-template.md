# Install Instructions Template

The meta-skill generates an `INSTALL.md` file alongside the v1 voice skill. The contents depend on the system the user named in Phase 1. Use the section below that matches their target system.

---

## For Cowork users (Claude Desktop with Cowork mode)

Cowork loads skills via plugins. To install your new voice skill:

### Option A — Add to an existing personal plugin

If you already have a personal plugin in Cowork (typically named `<yourname>` or `personal`), drop the skill into it:

1. Locate the plugin's `skills/` directory in your plugin source folder.
2. Copy the entire `<firstname-lastname>-voice/` directory (and the optional `<firstname-lastname>-tropes/` directory if you generated one) into `skills/`.
3. Bump the plugin version in `plugin.json` (patch bump for new skill content — e.g., 1.0.0 → 1.0.1).
4. Rebuild the plugin via your build script (if you have one).
5. In Cowork, go to Settings → Plugins → ··· next to your plugin → Check for updates.

### Option B — Create a new personal plugin for your voice skill

If you don't have a personal plugin yet, the simplest path is:

1. Create a directory `<yourname>-voice-plugin/` somewhere stable in your filesystem (e.g., `~/Documents/cowork-plugins/`).
2. Inside it, create the standard plugin structure:
   ```
   <yourname>-voice-plugin/
   ├── .claude-plugin/
   │   └── plugin.json
   └── skills/
       └── <firstname-lastname>-voice/
           └── SKILL.md
   ```
3. `plugin.json` minimum content:
   ```json
   {
     "name": "<yourname>-voice",
     "version": "0.1.0",
     "description": "<Your name>'s voice and style guide. v1 scaffold from voice-skill-creator.",
     "author": { "name": "<Your name>" }
   }
   ```
4. Zip the plugin directory: `cd <plugin-parent-directory> && zip -r <yourname>-voice-plugin.plugin <yourname>-voice-plugin`
5. In Cowork, go to Settings → Plugins → "+" → Upload plugin → select the `.plugin` file.

### Option C — Cowork "My skills" (not recommended)

Cowork has a "My skills" feature for individual skill files. This works but creates a snapshot copy that drifts from your canonical source. If you plan to evolve the skill (you should), use Option A or B instead.

---

## For Claude Code users (Terminal CLI)

Claude Code reads skills from `~/.claude/skills/` (user-level) or `<project-root>/.claude/skills/` (project-level).

### User-level install (recommended for personal voice)

1. Copy `<firstname-lastname>-voice/` to `~/.claude/skills/`.
2. Verify with: `ls ~/.claude/skills/<firstname-lastname>-voice/SKILL.md`
3. The skill is now available in any Claude Code session.
4. Trigger it by name or by trigger phrase from the SKILL.md frontmatter.

### Project-level install (if voice is project-specific)

1. From your project root: `mkdir -p .claude/skills`
2. Copy `<firstname-lastname>-voice/` to `<project-root>/.claude/skills/`
3. The skill is available only in this project.

---

## For Codex users (or other Skills-aware agentic systems)

Codex and similar systems typically read skills from a configured directory. Check your system's documentation for the canonical path.

For most systems following the Anthropic Skills convention:

1. Locate the skills directory (often `~/.codex/skills/`, `~/.skills/`, or system-specific).
2. Copy `<firstname-lastname>-voice/` into it.
3. Verify the system can discover the skill. Most systems list available skills with a command like `codex skills list` or via a UI panel.
4. Trigger via the skill name in the frontmatter.

---

## For direct Anthropic API use (no Skills system)

If you don't use a Skills-aware client and want to use the voice skill via direct API calls:

1. Read the SKILL.md content into a string.
2. Inject it as a system-prompt prefix:
   ```python
   from anthropic import Anthropic
   client = Anthropic()

   with open("<firstname-lastname>-voice/SKILL.md") as f:
       voice_skill = f.read()

   message = client.messages.create(
       model="claude-sonnet-4-6",
       max_tokens=2048,
       system=f"{voice_skill}\n\nApply this voice to the user's writing tasks.",
       messages=[{"role": "user", "content": "Draft an email to <recipient> about <topic>."}]
   )
   ```
3. The voice rules will apply to that message. For multi-turn conversations, include the system prompt in every call.

This works but is the lowest-fidelity option — Skills-aware clients handle invocation, mode-switching, and triggers more cleanly. Use a Skills client if you can.

---

## After install — first-use checklist

1. Trigger the skill in a writing session: "Write me a [WORK] mode email to <recipient> about <topic>"
2. Compare the output to what you would have written. Note the gaps in two columns:
   - **What the skill got right** — keep these
   - **What the skill got wrong or missed** — these become your first harvest entries
3. Within the first week, write 2–3 dated learning entries to `<voice-skill>/learnings/YYYY-MM-DD-<slug>.md` capturing observations.
4. Continue using the skill on real writing tasks for 4–8 weeks before treating any section as canonical.

See `HARVEST-CYCLE.md` for the full evolution pattern.

---

## Troubleshooting

**The skill triggers but the output doesn't sound like me.** This is the v1 problem. Don't try to fix the SKILL.md from a single bad output. Instead, write a learning entry naming what was wrong and why, then keep using the skill. After 4–8 weeks of harvest, distill the learnings into a v1.0 (or v0.2, v0.3 — whatever cadence works for you).

**The skill triggers in modes I didn't intend.** Frontmatter triggers are too broad. Edit the `triggers` field in frontmatter to be more specific to your invocation patterns.

**The skill output reads as AI-generated.** Likely cause: tropes section is too thin or signature words are stacking. Run the tropes companion if you generated one. If not, expand the AVOID list in the voice skill manually based on what you're seeing.

**I want to share my voice skill with my team.** A voice skill belongs to one writer. Sharing it with others produces ghostwriting — fine for some contexts (executive comms team writing on behalf of an exec) but not for individual voice. If your team wants their own voice skills, point each member at this meta-skill.
