"""Run inside Blender: blender -b -P scenes/run_scene.py -- spec.json   (spec: scene, params, width, height, samples, engine, ev, out, depth_out)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scenes import kit, library  # noqa: E402

spec = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
kit.reset(spec["width"], spec["height"], spec.get("engine", "CYCLES"), spec.get("samples", 96), spec.get("ev", 0.0))
near, far = library.SCENES[spec["scene"]](spec.get("params", {}))
kit.render_still(spec["out"])
if spec.get("depth_out"):
    kit.render_depth(spec["depth_out"], near, far)
print("SCENE_DONE", spec["scene"])
