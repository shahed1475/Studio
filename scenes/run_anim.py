"""Run inside Blender: blender -b -P scenes/run_anim.py -- spec.json   (spec: scene, params, width, height, samples, frames, fps, out_dir).
Renders a moving clip as numbered PNG frames. Frames already on disk are skipped (Blender's no-overwrite and placeholder settings), so a render that was stopped part way
continues where it stopped instead of starting again."""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scenes import kit, library  # noqa: E402

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
sc = kit.reset(spec["width"], spec["height"], spec.get("engine", "CYCLES"), spec.get("samples", 12), spec.get("ev", 0.0))
frames = int(spec["frames"])
sc.frame_start, sc.frame_end, sc.render.fps = 1, frames, int(spec.get("fps", 24))
library.ANIMATED[spec["scene"]](spec.get("params", {}), frames)
sc.render.filepath = str(Path(spec["out_dir"]) / "f_")
sc.render.use_overwrite, sc.render.use_placeholder = False, True
sc.render.use_persistent_data = True  # the scene and the 8K Earth picture are loaded once, not once a frame
sc.cycles.max_bounces, sc.cycles.transparent_max_bounces, sc.cycles.caustics_reflective, sc.cycles.caustics_refractive = 3, 4, False, False
bpy.ops.render.render(animation=True)
print("ANIM_DONE", spec["scene"], frames)
