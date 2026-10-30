# Gloamtale 3D stage 1: three scene templates Implementation Plan

> **For agentic workers:** execute task by task (superpowers:executing-plans); each task ends with a render whose frames are looked at before the next starts.

**Goal:** Three reusable, branded 3D scene templates (army march, caravan flyover, sandstorm) as a Remotion project, rendered on CPU only, with the measured cost per frame, so the owner can judge the look before any server change.

**Architecture:** `studio3d/` Remotion project. Shared world (terrain, sky, light, post effects, brand overlay) plus actors (soldiers, camels, palms, temple) and weather (storm wall, dust). Everything is drawn from simple shapes in code, so there is no outside model, no licence question and one consistent low-poly style. Every motion is a pure function of the frame number (deterministic, no shake).

**Tech Stack:** Remotion 4.0.539, three.js 0.186, React Three Fiber 9, Drei (Sky), React Postprocessing (bloom, vignette), Cinzel font.

**Spec:** docs/superpowers/plans/2026-10-30-branded-3d-pipeline.md and docs/studio/BRAND_KIT_GLOAMTALE_2026-10-30.md.

## Global Constraints
- No faces, hands or noses: figures are low-poly and seen from a distance.
- Frame-driven motion only; no camera shake; no `useFrame`.
- 1280x720, 24 fps for the look proof (the film is 1920x1080: render cost about 2.25x).
- Brand: gold `#f2c46d`, cream `#fff1d4`, night `#0b0f2a`, plum `#3b2350`, ember `#d7743a`; Cinzel; the Gloamtale mark as a corner bug.
- Nothing changes on the server. CPU-only render, measured on a 4-core subset of this PC as a proxy.
- Honesty: judge the look with the eye and say what is still weak.

## Review Focus
- The title must not sit on the figures (use a scrim and keep figures right of centre).
- The army or caravan must stay in frame for the whole scene.
- The storm must read as a storm (layers, streaks, darkening), not a flat blob.
- The render time per frame is stated per scene, not averaged away.

## Tasks
1. Shared world, brand tokens and overlay (`studio3d/src/brand.ts`, `world.tsx`, `Overlay.tsx`). Check: one still renders with the bug and title.
2. Actors: soldiers, camels (body, hump, neck, head, four swinging legs, pack), palms, temple (`actors.tsx`). Check: camels walk, legs swing, no figure floats above the dune.
3. Weather: storm wall, dust, streaks (`weather.tsx`).
4. Scenes March, Caravan, Storm with their camera rigs (`scenes.tsx`, `Root.tsx`). Check: frames at four moments each, looked at.
5. Render all three CPU-only on 4 cores; record seconds per frame; publish a private review page with the three videos.
6. Docs, commit locally, memory.

## Not in this plan
Server changes (Node and Chrome in the worker image), the scene director, a film. Those are stage 2.
