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
    kit.sky(p.get("hdri", "venice_sunset_2k.hdr"), strength=p.get("sky", 0.8), rotation=p.get("sky_rot", 2.2))
    kit.sun(p.get("sun_elev", 9), p.get("sun_az", 250), p.get("sun", 3.2), warm=(1.0, 0.7, 0.45))
    floor_m = kit.pbr("floor", "cobblestone_floor_01", scale=0.18)
    g = kit.terrain(size=120, res=120, height=0.35, freq=0.05, seed=p.get("seed", 5), material=floor_m)
    col_m = kit.pbr("col", "brick_wall_02", scale=0.4, tint=(0.95, 0.9, 0.8, 1))
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


SCENES = {"dunes": dunes, "temple": temple, "stones": stones}
