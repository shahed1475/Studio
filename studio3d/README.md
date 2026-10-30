# Gloamtale 3D (stage 1)
Remotion + three.js scene templates, drawn from simple shapes in code (no outside models): `March`, `Caravan`, `Storm`, and `SubscribePop` (the subscribe reminder, rendered once to the transparent PNG sequence in `branding/gloamtale/subscribe/`, laid on videos by `subscribe.py`). Plan: docs/superpowers/plans/2026-10-30-3d-stage1-templates.md.
Run: `npm install`, then `npm run render:march` and so on. CPU only (`--gl=swangle`), the way the server must run it.
Lessons: the 3D post-processing pass (bloom) draws the first frame of every browser tab black, so the vignette and glow are drawn in `Overlay.tsx` instead; stills (`remotion still`) are not trustworthy for 3D, render a few frames of video and look at one.
Not connected to the studio yet (stage 2).
