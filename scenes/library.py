"""Scenes that run inside Blender. Each takes the render size and a params dict and returns (near, far) metres for the depth picture. Add a scene by adding a function and a line in SCENES."""
import math

from . import kit


def dunes(p):
    """Wind-carved dunes under a low sun; a few rocks; haze. Params: hdri, sun_elev, sun_az, rocks, seed, cam_height, haze."""
    kit.sky(p.get("hdri", "kloppenheim_06_puresky_2k.hdr"), strength=p.get("sky", 0.9), rotation=p.get("sky_rot", 0.6))
    kit.sun(p.get("sun_elev", 11), p.get("sun_az", 35), p.get("sun", 5.5))
    sand = kit.pbr("sand", "dense_sand", scale=p.get("tex_scale", 0.3), tint=(1.0, 0.9, 0.75, 1))
    g = kit.terrain(size=140, res=260, height=p.get("height", 6.0), freq=p.get("freq", 0.028), seed=p.get("seed", 3), ridge=True, material=sand)
    rock_m = kit.pbr("rock", "rock_boulder_dry", scale=0.5, tint=(0.55, 0.45, 0.36, 1))
    for i in range(int(p.get("rocks", 4))):
        x, y = -6 + i * 4.2, 14 + i * 3
        kit.rock((x, y, kit.ground_z(g, x, y) + 0.2), radius=1.1 + 0.3 * (i % 3), seed=i, material=rock_m)
    kit.camera((0, -18, kit.ground_z(g, 0, -18) + p.get("cam_height", 2.2)), (0, 30, kit.ground_z(g, 0, 30) + 3.0), lens=p.get("lens", 32), fstop=p.get("fstop", 0.0), focus=p.get("focus"))
    return 4.0, 120.0


def temple(p):
    """A row of columns, some broken, on a worn stone floor at dusk. Params: hdri, columns, broken, seed."""
    kit.sky(p.get("hdri", "belfast_sunset_puresky_2k.hdr"), strength=p.get("sky", 0.8), rotation=p.get("sky_rot", 2.2))  # a pure sky: the Venice sky showed a modern villa behind the columns (20 Nov 2026)
    kit.sun(p.get("sun_elev", 9), p.get("sun_az", 250), p.get("sun", 3.2), warm=(1.0, 0.7, 0.45))
    floor_m = kit.pbr("floor", "cobblestone_floor_01", scale=0.18)
    g = kit.terrain(size=120, res=120, height=0.35, freq=0.05, seed=p.get("seed", 5), material=floor_m)
    col_m = kit.pbr("col", "rock_boulder_dry", scale=0.6, tint=(0.95, 0.9, 0.8, 1))  # weathered stone, not brick
    n = int(p.get("columns", 7))
    for i in range(n):
        kit.column((-9 + i * 3.0, 6 + 1.2 * (i % 2), kit.ground_z(g, -9 + i * 3.0, 6 + 1.2 * (i % 2)) - 0.1), height=6.5, radius=0.5, material=col_m, broken=p.get("broken", 0.5) if i % 3 else 0.0, seed=i)
    kit.camera((-4, -9, kit.ground_z(g, -4, -9) + 1.7), (0, 8, 2.6), lens=p.get("lens", 28), fstop=p.get("fstop", 0.0), focus=p.get("focus"))
    return 3.0, 80.0


def stones(p):
    """Standing stones on a rolling field at dawn. Params: hdri, count, seed."""
    kit.sky(p.get("hdri", "belfast_sunset_puresky_2k.hdr"), strength=p.get("sky", 1.0), rotation=p.get("sky_rot", 1.0))
    kit.sun(p.get("sun_elev", 7), p.get("sun_az", 110), p.get("sun", 3.0), warm=(1.0, 0.75, 0.55))
    ground = kit.pbr("ground", "brown_mud_leaves_01", scale=0.25, tint=(0.7, 0.8, 0.55, 1))
    g = kit.terrain(size=160, res=200, height=3.0, freq=0.02, seed=p.get("seed", 2), material=ground, flat_radius=14)
    rock_m = kit.pbr("stone", "aerial_rocks_02", scale=0.35)
    for i in range(int(p.get("count", 9))):
        a = i / p.get("count", 9) * 2 * math.pi
        x, y = math.cos(a) * 11, math.sin(a) * 11 + 10
        o = kit.rock((x, y, kit.ground_z(g, x, y) + 1.4), radius=1.0, squash=(0.45, 0.35, 1.8), seed=i, material=rock_m, rough=0.18)
    kit.camera((0, -4, kit.ground_z(g, 0, -4) + 1.6), (0, 14, kit.ground_z(g, 0, 14) + 2.4), lens=p.get("lens", 30), fstop=p.get("fstop", 0.0), focus=p.get("focus"))
    return 3.0, 120.0


def _earth_material():
    """NASA Blue Marble (public domain, assets/cc0/earth) wrapped on the sphere by its own spherical coordinates: longitude 0 on +X, latitude on Z, so a place's
    latitude and longitude put its marker exactly where the picture shows that place."""
    import bpy

    m = bpy.data.materials.new("earth")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.8
    b.inputs["Specular IOR Level"].default_value = 0.15  # a matte planet: the label and the marker must not show a mirrored copy on it
    tc, nv, sep = n.new("ShaderNodeTexCoord"), n.new("ShaderNodeVectorMath"), n.new("ShaderNodeSeparateXYZ")
    nv.operation = "NORMALIZE"
    l.new(tc.outputs["Object"], nv.inputs[0])
    l.new(nv.outputs["Vector"], sep.inputs["Vector"])

    def math(op, a, b2=None, value=None):
        x = n.new("ShaderNodeMath")
        x.operation = op
        l.new(a, x.inputs[0])
        if b2 is not None:
            l.new(b2, x.inputs[1])
        elif value is not None:
            x.inputs[1].default_value = value
        return x.outputs["Value"]

    lon = math("ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    lat = math("ARCSINE", sep.outputs["Z"])
    u = math("ADD", math("DIVIDE", lon, value=2 * 3.141592653589793), value=0.5)
    v = math("ADD", math("DIVIDE", lat, value=3.141592653589793), value=0.5)
    uv = n.new("ShaderNodeCombineXYZ")
    l.new(u, uv.inputs["X"])
    l.new(v, uv.inputs["Y"])
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(kit.ASSETS / "earth" / "blue_marble_8k.jpg"))
    img.interpolation, img.extension = "Linear", "REPEAT"
    l.new(uv.outputs["Vector"], img.inputs["Vector"])
    l.new(img.outputs["Color"], b.inputs["Base Color"])
    lw, pw = n.new("ShaderNodeLayerWeight"), n.new("ShaderNodeMath")  # a blue rim of air toward the edge, inside the planet's own material: a see-through air sphere
    lw.inputs["Blend"].default_value = 0.5                             # doubled the time of every frame (20 Nov 2026)
    pw.operation, pw.inputs[1].default_value = "POWER", 3.0
    l.new(lw.outputs["Facing"], pw.inputs[0])
    b.inputs["Emission Color"].default_value = (0.35, 0.6, 1.0, 1)
    l.new(pw.outputs["Value"], b.inputs["Emission Strength"])
    return m


def _emission(name, color, strength):
    import bpy

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    for x in list(n):
        n.remove(x)
    e, o = n.new("ShaderNodeEmission"), n.new("ShaderNodeOutputMaterial")
    e.inputs["Color"].default_value, e.inputs["Strength"].default_value = (*color, 1), strength
    l.new(e.outputs["Emission"], o.inputs["Surface"])
    return m


def _space_world():
    """A near-black sky with small, uneven stars (a Voronoi pattern on the view direction): no picture file, nothing that dates the scene."""
    import bpy

    w = bpy.data.worlds.new("space")
    w.use_nodes = True
    bpy.context.scene.world = w
    n, l = w.node_tree.nodes, w.node_tree.links
    tc, vor, lt, noise, mul, add = n.new("ShaderNodeTexCoord"), n.new("ShaderNodeTexVoronoi"), n.new("ShaderNodeMath"), n.new("ShaderNodeTexWhiteNoise"), n.new("ShaderNodeMath"), n.new("ShaderNodeMath")
    vor.inputs["Scale"].default_value = 350
    l.new(tc.outputs["Generated"], vor.inputs["Vector"])
    lt.operation = "LESS_THAN"
    lt.inputs[1].default_value = 0.035
    l.new(vor.outputs["Distance"], lt.inputs[0])
    l.new(vor.outputs["Position"], noise.inputs["Vector"])
    mul.operation = "MULTIPLY"
    l.new(lt.outputs["Value"], mul.inputs[0])
    l.new(noise.outputs["Value"], mul.inputs[1])
    add.operation = "ADD"
    add.inputs[1].default_value = 0.004
    l.new(mul.outputs["Value"], add.inputs[0])
    bg = n["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.85, 1)
    l.new(add.outputs["Value"], bg.inputs["Strength"])


def _sph(lat, lon, r=1.0):
    from mathutils import Vector

    return Vector((r * math.cos(lat) * math.cos(lon), r * math.cos(lat) * math.sin(lon), r * math.sin(lat)))


def globe(p, frames=1):
    """The Earth from space, the camera coming down toward one place over the clip, a small glowing marker and the place's name on it. Params: lat and lon in degrees
    (from the story's own Wikipedia article), label (the article's title), dist0 and dist1 (camera distance in Earth radii at the start and the end), turn (degrees the
    camera travels round the globe). Every frame is keyframed here, so the clip renders frame by frame and a restarted render skips the frames already on disk."""
    import bpy
    from mathutils import Vector

    lat, lon = math.radians(float(p["lat"])), math.radians(float(p["lon"]))
    _space_world()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
    earth = bpy.context.object
    bpy.ops.object.shade_smooth()
    earth.data.materials.append(_earth_material())
    place = _sph(lat, lon, 1.0)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.012, location=place * 1.004)
    bpy.context.object.data.materials.append(_emission("marker", (1.0, 0.72, 0.3), 30.0))
    bpy.context.object.visible_shadow = False
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.0025, depth=0.06, location=place * 1.03)
    pin = bpy.context.object
    pin.rotation_euler = place.to_track_quat("Z", "Y").to_euler()
    pin.data.materials.append(_emission("pin", (1.0, 0.8, 0.45), 12.0))
    pin.visible_shadow = False
    sun_dir = _sph(lat + math.radians(12), lon - math.radians(38))  # lit from the side the camera comes from: the place is in daylight, the far side is not
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy, sun.data.color = 4.5, (1.0, 0.96, 0.9)
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = float(p.get("lens", 35))
    cam.data.clip_start, cam.data.clip_end = 0.01, 100
    bpy.context.scene.camera = cam
    label = str(p.get("label") or "").strip()[:40]
    if label:
        bpy.ops.object.text_add(location=place * 1.075)
        t = bpy.context.object
        t.data.body, t.data.size, t.data.align_x = label, 0.045, "CENTER"
        t.data.materials.append(_emission("label", (1.0, 0.97, 0.9), 6.0))
        t.visible_glossy = t.visible_diffuse = t.visible_shadow = False  # seen by the camera only: no reflection or shadow of the name on the planet
        c = t.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = cam, "TRACK_Z", "UP_Y"
    d0, d1, turn = float(p.get("dist0", 4.2)), float(p.get("dist1", 2.0)), math.radians(float(p.get("turn", 40)))
    n_f = max(1, int(frames))
    for f in range(1, n_f + 1):
        t = 0.0 if n_f == 1 else (f - 1) / (n_f - 1)
        e = t * t * (3 - 2 * t)  # ease in and out
        clat = lat - math.radians(10) * (1 - e)
        pos = _sph(clat, lon - turn * (1 - e), d0 + (d1 - d0) * e)
        aim = place * (0.55 * e)  # the globe's centre at first, the place by the end
        cam.location = pos
        cam.rotation_euler = (aim - pos).to_track_quat("-Z", "Y").to_euler()  # a camera looks down its -Z with Y up (20 Nov 2026: "Z" here turned the Earth upside down)
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    bpy.context.scene.frame_set(n_f)
    return 0.5, 6.0


def sea(p):
    """Open water to a low horizon under a pure sky (the rocks were removed on 20 Nov 2026: box-projected texture smeared on them): a voyage, a coast or an island, of no particular century. Params: hdri, waves, seed."""
    import bpy

    kit.sky(p.get("hdri", "kloppenheim_06_puresky_2k.hdr"), strength=p.get("sky", 0.9), rotation=p.get("sky_rot", 1.4))
    kit.sun(p.get("sun_elev", 9), p.get("sun_az", 70), p.get("sun", 4.0), warm=(1.0, 0.82, 0.62))
    water = bpy.data.materials.new("water")
    water.use_nodes = True
    b = water.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value, b.inputs["Roughness"].default_value = (0.02, 0.07, 0.09, 1), 0.06
    kit.terrain(size=400, res=300, height=p.get("waves", 0.6), freq=0.16, seed=p.get("seed", 4), material=water)
    kit.camera((0, -9, 1.6), (0, 40, 1.2), lens=p.get("lens", 30))
    return 2.0, 200.0


def night(p):
    """Low hills under a starry night sky (a CC0 night sky): stars, the moon, a long night, of no particular century. Params: hdri, seed."""
    kit.sky(p.get("hdri", "dikhololo_night_2k.hdr"), strength=p.get("sky", 1.2), rotation=p.get("sky_rot", 0.4))
    ground = kit.pbr("ground", "brown_mud_leaves_01", scale=0.25, tint=(0.35, 0.38, 0.3, 1))
    g = kit.terrain(size=220, res=200, height=p.get("height", 5.0), freq=0.018, seed=p.get("seed", 6), material=ground, flat_radius=10)
    kit.camera((0, -6, kit.ground_z(g, 0, -6) + 1.5), (0, 40, kit.ground_z(g, 0, 40) + 9.0), lens=p.get("lens", 24))
    return 3.0, 150.0


SCENES = {"dunes": dunes, "temple": temple, "stones": stones, "sea": sea, "night": night}
ANIMATED = {"globe": globe}  # scenes rendered as a moving clip, frame by frame (scenes/run_anim.py, ccrender.render_clip)
