"""Helpers that run inside Blender 5.x: render set-up, CC0 sky and textures from assets/cc0, simple terrain and props, camera, and a depth picture.
Only free, shipped inputs: Blender's own tools plus the CC0 files listed in assets/cc0/LEDGER.md. No outside model, no network."""
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector, noise

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "cc0"


def reset(width, height, engine="CYCLES", samples=96, ev=0.0):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = width, height, 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = ev
    if engine == "CYCLES":
        sc.render.engine = "CYCLES"
        sc.cycles.samples, sc.cycles.use_denoising = samples, True
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        prefs.refresh_devices()
        gpu = [d for d in prefs.devices if d.type == "CUDA"]
        for d in prefs.devices:
            d.use = d.type == "CUDA"
        sc.cycles.device = "GPU" if gpu else "CPU"
    else:
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = samples
    return sc


def sky(hdri, strength=1.0, rotation=0.0):
    """A CC0 HDRI as the whole sky and the light (assets/cc0/hdri)."""
    w = bpy.data.worlds.new("sky")
    w.use_nodes = True
    bpy.context.scene.world = w
    n, l = w.node_tree.nodes, w.node_tree.links
    env = n.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(ASSETS / "hdri" / hdri))
    mp, tc = n.new("ShaderNodeMapping"), n.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value[2] = rotation
    l.new(tc.outputs["Generated"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], env.inputs["Vector"])
    bg = n.get("Background")
    bg.inputs["Strength"].default_value = strength
    l.new(env.outputs["Color"], bg.inputs["Color"])


def sun(elevation=20, azimuth=40, energy=3.0, warm=(1.0, 0.82, 0.62)):
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(90 - elevation), 0, math.radians(azimuth)))
    s = bpy.context.object
    s.data.energy, s.data.color, s.data.angle = energy, warm, math.radians(1.2)
    return s


def pbr(name, tex, scale=3.0, tint=None, rough_mul=1.0):
    """A material from a CC0 texture folder in assets/cc0/tex (diffuse, normal GL, roughness), box-projected so it sits on a slope."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    tc, mp = n.new("ShaderNodeTexCoord"), n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])

    def img(kind, data):
        t = n.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(ASSETS / "tex" / tex / f"{tex}_{kind}_1k.jpg"))
        t.image.colorspace_settings.name = "sRGB" if data == "color" else "Non-Color"
        t.projection, t.projection_blend = "BOX", 0.25
        l.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t

    d = img("diff", "color")
    if tint:
        mix = n.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs["B"].default_value = tint
        l.new(d.outputs["Color"], mix.inputs["A"])
        l.new(mix.outputs["Result"], b.inputs["Base Color"])
    else:
        l.new(d.outputs["Color"], b.inputs["Base Color"])
    r = img("rough", "data")
    if rough_mul != 1.0:
        mu = n.new("ShaderNodeMath")
        mu.operation = "MULTIPLY"
        mu.inputs[1].default_value = rough_mul
        l.new(r.outputs["Color"], mu.inputs[0])
        l.new(mu.outputs["Value"], b.inputs["Roughness"])
    else:
        l.new(r.outputs["Color"], b.inputs["Roughness"])
    nm, nt = n.new("ShaderNodeNormalMap"), img("nor_gl", "data")
    l.new(nt.outputs["Color"], nm.inputs["Color"])
    l.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def terrain(size=60.0, res=220, height=3.0, freq=0.05, seed=1, ridge=False, material=None, flat_radius=0.0):
    """A displaced grid (fractal noise). ridge=True makes sharp wind-blown crests like dunes. flat_radius keeps the middle level."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=res, y_subdivisions=res, size=size)
    o = bpy.context.object
    off = Vector((seed * 17.3, seed * 9.1, 0))
    for v in o.data.vertices:
        p = (v.co * freq) + off
        z = noise.fractal(p, 0.55, 2.0, 5)
        if ridge:
            z = 1.0 - abs(noise.noise(Vector((p.x * 0.55, p.y * 1.3, 0)))) * 2.0
            z += 0.25 * noise.fractal(p * 2.5, 0.5, 2.0, 3)
        fade = 1.0 if flat_radius <= 0 else min(1.0, max(0.0, (math.hypot(v.co.x, v.co.y) - flat_radius) / (size * 0.15)))
        v.co.z = z * height * fade
    bpy.ops.object.shade_smooth()
    if material:
        o.data.materials.append(material)
    return o


def ground_z(ground, x, y):
    """Height of the terrain under (x, y), found by a ray straight down onto it."""
    hit, loc, _n, _i = ground.ray_cast(Vector((x, y, 500.0)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0


def rock(location, radius=1.0, squash=(1, 1, 0.7), seed=0, material=None, rough=0.35):
    rnd = random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=radius, location=location)
    o = bpy.context.object
    off = Vector((rnd.random() * 50, rnd.random() * 50, rnd.random() * 50))
    for v in o.data.vertices:
        d = 1.0 + rough * noise.fractal(v.co * 1.3 + off, 0.6, 2.0, 4)
        v.co = Vector((v.co.x * d * squash[0], v.co.y * d * squash[1], v.co.z * d * squash[2]))
    o.rotation_euler = (0, 0, rnd.random() * 6.28)
    bpy.ops.object.shade_smooth()
    if material:
        o.data.materials.append(material)
    return o


def column(location, height=6.0, radius=0.45, material=None, broken=0.0, seed=0):
    """A fluted column; broken in 0..1 cuts its top off at an angle."""
    rnd = random.Random(seed)
    h = height * (1 - broken * rnd.uniform(0.3, 0.8))
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=h, location=(location[0], location[1], location[2] + h / 2))
    o = bpy.context.object
    for v in o.data.vertices:
        a = math.atan2(v.co.y, v.co.x)
        r = 1.0 + 0.04 * math.cos(a * 16)
        v.co.x, v.co.y = v.co.x * r, v.co.y * r
    bpy.ops.object.shade_smooth()
    if material:
        o.data.materials.append(material)
    return o


def camera(loc, target, lens=35, fstop=0.0, focus=None):
    """A camera at loc looking at target. fstop > 0 turns depth of field on, focused on the target (or at distance focus)."""
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.object
    c.data.lens = lens
    d = Vector(target) - Vector(loc)
    c.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if fstop > 0:
        c.data.dof.use_dof = True
        c.data.dof.aperture_fstop = fstop
        c.data.dof.focus_distance = focus if focus else d.length
    bpy.context.scene.camera = c
    return c


def render_still(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def render_depth(path, near, far):
    """The exact depth of every pixel as a grey picture: white = at `near` metres or closer, black = at `far` or beyond (the sky). Same convention as depth.py."""
    sc = bpy.context.scene
    keep = (sc.render.engine, sc.view_settings.view_transform, sc.view_settings.exposure)
    m = bpy.data.materials.new("depth")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    for x in list(n):
        n.remove(x)
    cam, mr, em, out = n.new("ShaderNodeCameraData"), n.new("ShaderNodeMapRange"), n.new("ShaderNodeEmission"), n.new("ShaderNodeOutputMaterial")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = near, far
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
    mr.clamp = True
    l.new(cam.outputs["View Distance"], mr.inputs["Value"])
    l.new(mr.outputs["Result"], em.inputs["Color"])
    l.new(em.outputs["Emission"], out.inputs["Surface"])
    w = bpy.data.worlds.new("black")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    old_world, sc.world = sc.world, w
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 8
    sc.view_settings.view_transform, sc.view_settings.exposure = "Standard", 0.0
    bpy.context.view_layer.material_override = m
    cam_data = sc.camera.data
    dof = cam_data.dof.use_dof
    cam_data.dof.use_dof = False
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    cam_data.dof.use_dof = dof
    bpy.context.view_layer.material_override = None
    sc.world = old_world
    sc.render.engine, sc.view_settings.view_transform, sc.view_settings.exposure = keep
