# Branded 3D proof (30 Oct 2026)
A 6 second Remotion + three.js scene: low-poly Persian column marching on dunes, golden-hour sky, closing dust wall, brand title. Not used by the studio yet.
Run: `npm install && npx remotion render src/index.ts Army out/army.mp4 --gl=swangle` (CPU only, the way the server must run it).
Measured on a 6-core PC, 1280x720, 24 fps: this scene about 0.35 s a frame on CPU only (24 frames in 12 s with start-up), about 0.43 s a frame on the GPU path (144 frames in 74 s with bundling): the cost is frame capture and encode, not shading. A simpler first scene ran about 0.05 s a frame. Not measured on the server.
Known flaws: the title overlaps the army, the army drifts out of frame on the right, the storm wall is a flat blob, one camera angle. Plan: docs/superpowers/plans/2026-10-30-branded-3d-pipeline.md. Models and assets must be CC0 and recorded.
