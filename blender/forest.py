"""Procedural stylised Valdivian night forest (south of Chile).

Elements: mossy ground with a soil path along +X, coihue-like trees, orange
arrayan trunks, araucaria silhouettes, ferns, a nalca (Gunnera tinctoria)
patch, a fallen log, rocks, moon, moonlight and drifting spores.
Seeded, so every episode can reuse the same location or vary it.
"""

import math
import random

import bmesh
import bpy
from mathutils import Vector

PATH_HALF_WIDTH = 0.8


def mat(name, color, rough=0.8, emission=None, sss=0.0, noise_mix=None, bump=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
    if emission:
        p.inputs["Emission Color"].default_value = (*emission[:3], 1)
        p.inputs["Emission Strength"].default_value = emission[3]
    if noise_mix or bump:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 6.0
        tex.inputs["Detail"].default_value = 6.0
        if noise_mix:
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.elements[0].color = (*color, 1)
            ramp.color_ramp.elements[1].color = (*noise_mix, 1)
            nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
            nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
        if bump:
            b = nt.nodes.new("ShaderNodeBump")
            b.inputs["Strength"].default_value = bump
            nt.links.new(tex.outputs["Fac"], b.inputs["Height"])
            nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


def ground_material():
    m = bpy.data.materials.new("ground")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Roughness"].default_value = 0.95
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    absn = nt.nodes.new("ShaderNodeMath")
    absn.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["Y"], absn.inputs[0])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.5
    noise.inputs["Detail"].default_value = 8
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    nt.links.new(noise.outputs["Fac"], add.inputs[0])
    add.inputs[1].default_value = 0.9
    nt.links.new(absn.outputs[0], add.inputs[2])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 1.0
    mr.inputs["From Max"].default_value = 1.6
    nt.links.new(add.outputs[0], mr.inputs["Value"])
    moss_noise = nt.nodes.new("ShaderNodeTexNoise")
    moss_noise.inputs["Scale"].default_value = 9.0
    moss = nt.nodes.new("ShaderNodeValToRGB")
    moss.color_ramp.elements[0].color = (0.018, 0.045, 0.012, 1)
    moss.color_ramp.elements[1].color = (0.05, 0.08, 0.02, 1)
    nt.links.new(moss_noise.outputs["Fac"], moss.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (0.045, 0.028, 0.018, 1)  # path soil
    nt.links.new(mr.outputs[0], mix.inputs[0])
    nt.links.new(moss.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    b = nt.nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = 0.4
    nt.links.new(moss_noise.outputs["Fac"], b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


def link(ob, coll):
    coll.objects.link(ob)
    return ob


def mesh_obj(name, bm, material, coll):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material)
    return link(bpy.data.objects.new(name, me), coll)


def ground(coll, rng, x0=-30, x1=40, y0=-14, y1=24):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=140, y_segments=76, size=1.0)
    for v in bm.verts:
        x = x0 + (v.co.x + 1) / 2 * (x1 - x0)
        y = y0 + (v.co.y + 1) / 2 * (y1 - y0)
        h = 0.12 * math.sin(x * 0.7 + 1.3) * math.cos(y * 0.6) + 0.07 * math.sin(x * 1.9 + y * 1.3)
        h *= min(1.0, max(0.0, (abs(y) - PATH_HALF_WIDTH) / 1.5))  # flat path
        h += 0.015 * math.sin(x * 7.1) * math.sin(y * 6.3)
        v.co = Vector((x, y, h - 0.01))
    return mesh_obj("ground", bm, ground_material(), coll)


def _tree_mesh(name, height, r0, r1, bark, bend=0.0, segs=10):
    bm = bmesh.new()
    rings = 8
    prev = None
    for i in range(rings + 1):
        k = i / rings
        r = r0 + (r1 - r0) * k ** 0.7
        z = height * k
        off = bend * math.sin(k * math.pi * 0.8)
        ring = [bm.verts.new((off + r * math.cos(2 * math.pi * j / segs), r * math.sin(2 * math.pi * j / segs), z))
                for j in range(segs)]
        if prev:
            for j in range(segs):
                bm.faces.new((prev[j], prev[(j + 1) % segs], ring[(j + 1) % segs], ring[j]))
        prev = ring
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(bark)
    return me


def _blob_mesh(name, material, subdiv=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    rnd = random.Random(name)
    for v in bm.verts:
        v.co *= 1.0 + 0.18 * (rnd.random() - 0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    return me


def _leaf_mesh(name, material, lobes=9, cup=0.35):
    """Nalca leaf: scalloped, cupped disc of radius 1."""
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0))
    n = lobes * 8
    ring = []
    for j in range(n):
        a = 2 * math.pi * j / n
        r = 1.0 - 0.13 * abs(math.sin(a * lobes / 2))
        ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), cup * r * r)))
    for j in range(n):
        bm.faces.new((c, ring[j], ring[(j + 1) % n]))
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges], cuts=1, use_grid_fill=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    return me


def _fern_mesh(name, material, fronds=9):
    bm = bmesh.new()
    for i in range(fronds):
        a = 2 * math.pi * i / fronds
        prev = None
        for k in range(7):
            t = k / 6
            r = 0.55 * t
            z = 0.45 * math.sin(t * math.pi * 0.75)
            w = 0.07 * math.sin(t * math.pi)
            cx, cy = r * math.cos(a), r * math.sin(a)
            px, py = -math.sin(a) * w, math.cos(a) * w
            pair = (bm.verts.new((cx + px, cy + py, z)), bm.verts.new((cx - px, cy - py, z)))
            if prev:
                bm.faces.new((prev[0], prev[1], pair[1], pair[0]))
            prev = pair
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    return me


def build(seed=7, keepout=(), motes=True):
    """keepout: list of (x, y, radius) circles kept free of trees/ferns."""
    rng = random.Random(seed)
    coll = bpy.data.collections.new("forest")
    bpy.context.scene.collection.children.link(coll)

    bark = mat("bark", (0.05, 0.035, 0.025), 0.9, noise_mix=(0.025, 0.03, 0.015), bump=0.6)
    arrayan = mat("arrayan", (0.42, 0.14, 0.04), 0.5, noise_mix=(0.6, 0.35, 0.18), bump=0.2)
    foliage = mat("foliage", (0.012, 0.04, 0.014), 0.9, sss=0.05, noise_mix=(0.03, 0.07, 0.02))
    arauc = mat("araucaria", (0.008, 0.025, 0.012), 0.9)
    fern_m = mat("fern", (0.02, 0.07, 0.015), 0.7, sss=0.15)
    leaf_m = mat("nalca", (0.05, 0.17, 0.025), 0.55, sss=0.25, noise_mix=(0.08, 0.22, 0.04), bump=0.3)
    stalk_m = mat("nalca_stalk", (0.25, 0.05, 0.03), 0.6)
    rock_m = mat("rock", (0.05, 0.055, 0.05), 0.9, noise_mix=(0.03, 0.07, 0.02), bump=0.8)
    log_m = mat("log", (0.06, 0.04, 0.025), 0.9, noise_mix=(0.03, 0.07, 0.02), bump=0.8)

    ground(coll, rng)

    def free(x, y, r=0.0):
        if -11 < x < 17 and -3.4 < y < 1.9:  # camera/path corridor
            return False
        return all((x - kx) ** 2 + (y - ky) ** 2 > (kr + r) ** 2 for kx, ky, kr in keepout)

    trunk_meshes = [_tree_mesh(f"trunk{i}", rng.uniform(9, 14), rng.uniform(0.18, 0.32), 0.06, bark,
                               bend=rng.uniform(-0.4, 0.4)) for i in range(5)]
    arr_meshes = [_tree_mesh(f"arrayan{i}", rng.uniform(4, 6), rng.uniform(0.1, 0.16), 0.05, arrayan,
                             bend=rng.uniform(-0.7, 0.7), segs=8) for i in range(3)]
    canopy = [_blob_mesh(f"canopy{i}", foliage, 3) for i in range(4)]
    placed = 0
    tries = 0
    while placed < 110 and tries < 5000:
        tries += 1
        x, y = rng.uniform(-28, 38), rng.uniform(-13, 22)
        if not free(x, y, 0.6):
            continue
        placed += 1
        kind = rng.random()
        if kind < 0.18 and abs(y) < 9:
            ob = link(bpy.data.objects.new("arrayan", rng.choice(arr_meshes)), coll)
            ob.location = (x, y, -0.05)
            ob.rotation_euler = (0, 0, rng.uniform(0, 6.28))
            continue
        ob = link(bpy.data.objects.new("tree", rng.choice(trunk_meshes)), coll)
        ob.location = (x, y, -0.05)
        ob.rotation_euler = (0, 0, rng.uniform(0, 6.28))
        h = ob.data.vertices[-1].co.z
        for _ in range(rng.randint(2, 4)):
            c = link(bpy.data.objects.new("leaves", rng.choice(canopy)), coll)
            s = rng.uniform(1.4, 2.6)
            c.location = (x + rng.uniform(-1, 1), y + rng.uniform(-1, 1), h * rng.uniform(0.75, 1.0))
            c.scale = (s, s, s * 0.6)
    # Araucaria silhouettes far behind the path (seen against the sky).
    for i in range(7):
        x, y = rng.uniform(-25, 30), rng.uniform(12, 22)
        t = link(bpy.data.objects.new("araucaria_trunk", _tree_mesh(f"arau{i}", 17, 0.35, 0.18, bark)), coll)
        t.location = (x, y, 0)
        crown = _blob_mesh(f"arau_crown{i}", arauc, 2)
        for k in range(9):
            a = 2 * math.pi * k / 9 + rng.random()
            c = link(bpy.data.objects.new("arau_branch", crown), coll)
            c.location = (x + 1.8 * math.cos(a), y + 1.8 * math.sin(a), 16.0 + rng.uniform(-0.4, 0.4))
            c.scale = (1.4, 1.4, 0.45)
        top = link(bpy.data.objects.new("arau_top", crown), coll)
        top.location = (x, y, 16.8)
        top.scale = (1.7, 1.7, 0.6)
    # Ferns along the path edges.
    fern_meshes = [_fern_mesh(f"fern{i}", fern_m, rng.randint(7, 11)) for i in range(3)]
    for _ in range(170):
        x, y = rng.uniform(-14, 22), rng.choice([-1, 1]) * rng.uniform(1.1, 6.0)
        if -11 < x < 17 and -4.4 < y < 0:  # keep the camera side of the path clear
            continue
        if any((x - kx) ** 2 + (y - ky) ** 2 < (kr + 0.4) ** 2 for kx, ky, kr in keepout):
            continue
        f = link(bpy.data.objects.new("fern", rng.choice(fern_meshes)), coll)
        s = rng.uniform(0.6, 1.4)
        f.location = (x, y, -0.02)
        f.scale = (s, s, s)
        f.rotation_euler = (0, 0, rng.uniform(0, 6.28))
    return coll, dict(leaf=leaf_m, stalk=stalk_m, rock=rock_m, log=log_m, fern=fern_m)


def nalca_patch(coll, mats, center=(11.0, 1.0), seed=3):
    rng = random.Random(seed)
    leaf = _leaf_mesh("nalca_leaf", mats["leaf"])
    for i in range(9):
        # back half + sides only: the camera side (-Y) stays open
        a = -0.45 + (math.pi + 0.9) * i / 8 + rng.uniform(-0.15, 0.15)
        d = rng.uniform(0.3, 0.6)
        x, y = center[0] + d * math.cos(a), center[1] + d * math.sin(a)
        h = rng.uniform(0.22, 0.5)
        st = bmesh.new()
        bmesh.ops.create_cone(st, cap_ends=False, segments=8, radius1=0.03, radius2=0.018, depth=h)
        bmesh.ops.translate(st, verts=st.verts, vec=(0, 0, h / 2))
        s = mesh_obj("nalca_stalk", st, mats["stalk"], coll)
        s.location = (x, y, 0)
        s.rotation_euler = (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 0)
        lf = link(bpy.data.objects.new("nalca_leaf", leaf), coll)
        r = rng.uniform(0.32, 0.48)
        lf.location = (x + 0.05 * math.cos(a), y + 0.05 * math.sin(a), h)
        lf.scale = (r, r, r)
        tilt = 0.45  # leaves lean outward, away from the patch centre
        lf.rotation_euler = (-tilt * math.sin(a), tilt * math.cos(a), rng.uniform(0, 6.28))


def fallen_log(coll, mats, center=(12.0, 2.75), length=3.4, radius=0.22):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius, radius2=radius * 0.85, depth=length)
    ob = mesh_obj("log", bm, mats["log"], coll)
    ob.location = (center[0], center[1], radius * 0.8)
    ob.rotation_euler = (0, math.pi / 2, 0.12)
    for i in range(5):
        rk = mesh_obj("rock", _rock_bm(i), mats["rock"], coll)
        rk.location = (center[0] - 2.4 + i * 1.2, center[1] + 0.6 + 0.3 * math.sin(i * 2.1), 0.0)
        s = 0.18 + 0.07 * (i % 3)
        rk.scale = (s * 1.3, s, s * 0.7)


def _rock_bm(i):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    rnd = random.Random(i)
    for v in bm.verts:
        v.co *= 1 + 0.25 * (rnd.random() - 0.5)
    return bm


def sky_and_moon(scene, moon_strength=1.6):
    w = bpy.data.worlds.new("night")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.5
    ramp.color_ramp.elements[0].color = (0.04, 0.075, 0.11, 1)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (0.004, 0.008, 0.02, 1)
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    w.mist_settings.start = 4.0
    w.mist_settings.depth = 30.0
    w.mist_settings.falloff = "QUADRATIC"
    # Moonlight: cool key from behind-left for rim light.
    sun = bpy.data.objects.new("moonlight", bpy.data.lights.new("moonlight", "SUN"))
    sun.data.energy = moon_strength
    sun.data.color = (0.55, 0.68, 1.0)
    sun.data.angle = math.radians(1.5)
    sun.rotation_euler = (math.radians(55), 0, math.radians(150))
    scene.collection.objects.link(sun)
    moon = bpy.data.objects.new("moon_disc", None)
    me = bpy.data.meshes.new("moon")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=2.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat("moon", (0, 0, 0), emission=(0.85, 0.9, 1.0, 8.0)))
    moon = bpy.data.objects.new("moon_disc", me)
    moon.location = (48, 78, 42)
    scene.collection.objects.link(moon)
    return sun


def spores(coll, rng_seed, region, count=50):
    """Tiny, dim floating spores; returns (objects, base positions)."""
    rng = random.Random(rng_seed)
    m = mat("spore", (0, 0, 0), emission=(0.7, 0.95, 0.75, 3.0))
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.008)
    me = bpy.data.meshes.new("spore")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    obs = []
    (x0, x1), (y0, y1), (z0, z1) = region
    for i in range(count):
        o = link(bpy.data.objects.new("spore", me), coll)
        base = (rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(z0, z1))
        o.location = base
        obs.append((o, base, rng.random() * 6.28))
    return obs
