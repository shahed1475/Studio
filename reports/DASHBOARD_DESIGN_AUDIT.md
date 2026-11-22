# Dashboard design audit and v5 palette (22 Nov 2026)

Sub-plan 2 of the owner's master mission. Owner's decision (22 Nov): navy surfaces with one accent, replacing the v4 black-and-white rule.

Skills used: redesign-skill (scan, diagnose, fix in the existing stack), taste-skill (colour and contrast rules only; it states that dashboards are outside its scope).

## Scan
- Stack: one HTML app (`dashboard.html`), plain CSS custom properties in `static/studio.css`, Geist and Geist Mono fonts, Phosphor-style icons in `static/icons`. No framework; kept as it is.
- Colour lived in a v4 block of 17 tokens per theme, all greys, enforced by a test. `monitor.html` and `notifications.html` repeat the tokens. Status already carried an icon and a fill style (an accessibility win kept as it is).

## Diagnosis
- Pure-black dark mode (`#050505`) and flat greys: no hierarchy between "you can press this" and "this is just text"; everything active was the same ink.
- Status (done, needs a look, failed) told apart only by fill style; correct for accessibility, slow to scan.
- Already good, kept: Geist type, 44 px touch targets, no sideways scroll on phones, reduced-motion handling, motion only on transform and opacity, skeleton loaders, empty states, visible focus ring.

## Fix (v5 block, end of `static/studio.css`)
| Token | Light | Dark |
|---|---|---|
| Page / panel / sunken | `#eef2f8` / `#ffffff` / `#e4e9f2` | `#0a1220` / `#101a2c` / `#0c1524` |
| Ink / muted ink / lines | `#0e1a2f` / `#4a5a76` / `#d3dbe8` | `#e6ebf5` / `#94a2bb` / `#22304b` |
| Accent / label on accent | `#2e5cb8` / `#ffffff` | `#7ea6ec` / `#0a1220` |
| Done | `#176f46` on `#e1f3e9` | `#5fcf99` on `#123227` |
| Needs a look | `#8a5d00` on `#fbefd2` | `#e8bd63` on `#3a2d12` |
| Failed | `#b83227` on `#fbe2df` | `#f17b7b` on `#3e1a20` |

- The accent appears only on what can be acted on or is selected: main buttons, selected tab and filter chip, counters, the bell badge, focus ring, switches, progress bars, the live step.
- Shadows and the soft light from above are tinted navy, never pure black.
- Same tokens in `monitor.html` and `notifications.html`; browser theme colour and app manifest `#0a1220`; stylesheet link bumped to `?v=6` so browsers fetch the new file.

## Evidence
- Contrast (WCAG 2 formula, computed in `tests/test_live_ui.py`): ink on panel 17.4 light / 14.6 dark; muted ink 6.96 / 6.75; label on accent 6.29 / 7.63; each status colour on its own background and on the panel 4.5 or more in both themes. The first draft's light "done" green was 4.34 and was darkened to `#176f46` before shipping.
- Real Chrome, test dashboard with demo data: 25 screenshots (home, videos, Autopilot, growth, activity, settings; light and dark; 1440 px and 360 px phone; the open notification panel). No page scrolls sideways at 360 px in either theme. Pixels read from the screenshots match the tokens (dark page `#0b121f` with the soft light, accent button `#7ea6ec`; light selected tab `#2e5cb8`, panel `#ffffff`).
- Tests: `tests/test_live_ui.py`, `tests/test_ui_behaviour.py`, `tests/test_dashboard_api.py`: 47 passed.

## Not done in this step (left for later, each needs its own look)
- Page-by-page layout changes (spacing, hierarchy of the Home page, Live page motion). The colour system was the agreed first step.
- 3D or new motion graphics on the dashboard.
- Screenshots of the live dashboard behind its login (the test dashboard runs the same code and stylesheet).

## Layout pass (v6, 22 Nov 2026, later the same day)
Skill used: redesign-skill (scan, diagnose, fix in the existing stack). Full-length screenshots of nine pages at 1440 px and 390 px (phone) on the test dashboard; zero script errors.

Found and fixed:
- **Autopilot plan badges had no style** (a real defect): the plan asked for badge classes `b-w` and `b-`, which do not exist, so "Make now", "Too soon", "Later" and "Paused" showed as bare text. Now `warn` / `mute`.
- **Live page showed a raw status word** ("empty") as a label: every planner status now has a readable label (Make now, In work, Later).
- **Sentences started in lower case** ("nothing yet, Autopilot makes it now"): the planner words are sentence case and the Home card ends the sentence.
- **Next-step card**: the icon floated mid-height apart from its title; it now sits in a small tile beside the title on a desktop and above it on a phone. On a phone the shared `.grow` rule (basis 220 px) turned into a 130 px empty band above the button; fixed for this card.
- **Live strip on a phone**: three loose lines; now the dot beside two tight lines.
- **Line length**: page intros and help paragraphs stop at about 80 characters.
- **Pexels**: Home's setup check asked for a Pexels key and Settings had a key field, although Pexels is not on the owner's licence list. Both now say it is not used; the dead `savePk` code is gone (the server-side key route is unchanged).

Tests: `tests/test_ui_behaviour.py` gains three real-browser tests (every badge uses an existing style and no label starts in lower case, on five pages; no empty band in the phone card; Settings asks for no Pexels key), each mutation-checked (the old code put back made it fail). Stylesheet link `?v=7`.

Not changed: the page structure, navigation, the sidebar, motion.
