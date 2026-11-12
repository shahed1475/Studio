"""Speed test for headless Blender on this PC (1 Nov 2026). Usage: blender -b -P tools/bench_blender.py -- <engine> <device> <out.png> [width height samples]
engine: CYCLES or EEVEE; device: CPU or CUDA or OPTIX. Prints one line: BENCH engine device WxH samples seconds."""
import sys, time
import bpy

a = sys.argv[sys.argv.index("--") + 1:]
engine, device, out = a[0], a[1], a[2]
W, H, S = (int(a[3]), int(a[4]), int(a[5])) if len(a) >= 6 else (1280, 720, 64)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = out

# a floor, a sphere of rough stone and a glossy ball, a sun and a sky: enough to exercise light, shadow and reflection
bpy.ops.mesh.primitive_plane_add(size=30)
floor = bpy.context.object
m = bpy.data.materials.new("floor"); m.use_nodes = True
b = m.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (0.35, 0.28, 0.2, 1); b.inputs["Roughness"].default_value = 0.9
floor.data.materials.append(m)
for x, col, rough, met in ((-1.6, (0.6, 0.55, 0.5, 1), 0.8, 0.0), (1.6, (0.9, 0.7, 0.2, 1), 0.15, 1.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2, location=(x, 0, 1.2), segments=64, ring_count=32)
    o = bpy.context.object; bpy.ops.object.shade_smooth()
    mm = bpy.data.materials.new("s"); mm.use_nodes = True
    bb = mm.node_tree.nodes["Principled BSDF"]
    bb.inputs["Base Color"].default_value = col; bb.inputs["Roughness"].default_value = rough; bb.inputs["Metallic"].default_value = met
    o.data.materials.append(mm)
bpy.ops.object.light_add(type="SUN", rotation=(0.9, 0.2, 0.6)); bpy.context.object.data.energy = 4
w = bpy.data.worlds.new("w"); w.use_nodes = True; sc.world = w
sky = w.node_tree.nodes.new("ShaderNodeTexSky"); w.node_tree.links.new(sky.outputs[0], w.node_tree.nodes["Background"].inputs[0])
bpy.ops.object.camera_add(location=(0, -9, 2.6), rotation=(1.35, 0, 0)); sc.camera = bpy.context.object

if engine == "CYCLES":
    sc.render.engine = "CYCLES"; sc.cycles.samples = S; sc.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if device == "CPU":
        sc.cycles.device = "CPU"
    else:
        prefs.compute_device_type = device
        prefs.refresh_devices() if hasattr(prefs, "refresh_devices") else prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
        print("DEVICES", [(d.name, d.type, d.use) for d in prefs.devices])
        sc.cycles.device = "GPU"
else:
    sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = S

t = time.time()
bpy.ops.render.render(write_still=True)
print("BENCH", engine, device, f"{W}x{H}", S, round(time.time() - t, 1), "s")
