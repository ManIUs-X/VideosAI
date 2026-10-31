"""Procedural stylised pudu (Pudu puda) built from metaballs + a pivot rig.

The character is deterministic (no randomness) so it stays identical across
episodes.  The rig is a hierarchy of empties; `apply_pose` sets every channel
from a plain dict so animation can be computed outside Blender.

Local axes: the pudu faces +X, Z up.  Real pudu: ~35-44 cm at the shoulder;
this model is ~0.45 m to the top of the head.
"""

import math

import bpy

FUR = (0.13, 0.05, 0.022)
FUR_DARK = (0.075, 0.035, 0.018)
SNOUT = (0.05, 0.028, 0.018)
EAR_IN = (0.14, 0.06, 0.045)
ANTLER = (0.16, 0.10, 0.06)


def _mat(name, color, rough=0.75, sheen=0.0, emission=None, bump=0.0, sss=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    if sheen:
        p.inputs["Sheen Weight"].default_value = sheen
        p.inputs["Sheen Roughness"].default_value = 0.4
    if sss:
        p.inputs["Subsurface Weight"].default_value = sss
        p.inputs["Subsurface Radius"].default_value = (0.02, 0.008, 0.004)
    if emission:
        p.inputs["Emission Color"].default_value = (*emission[:3], 1)
        p.inputs["Emission Strength"].default_value = emission[3]
    if bump:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 420.0
        tex.inputs["Detail"].default_value = 4.0
        b = nt.nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump
        b.inputs["Distance"].default_value = 0.002
        nt.links.new(tex.outputs["Fac"], b.inputs["Height"])
        nt.links.new(b.outputs["Normal"], p.inputs["Normal"])
    return m


def _empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.03
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    e.rotation_mode = "XYZ"
    return e


def _blob(name, ellipsoids, parent, mat, voxel=0.006, smooth=6):
    """Union of ellipsoids -> voxel remesh -> smooth: one organic surface."""
    import bmesh

    bm = bmesh.new()
    for (x, y, z), (sx, sy, sz) in ellipsoids:
        geom = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)
        vs = geom["verts"]
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=vs)
        bmesh.ops.translate(bm, vec=(x, y, z), verts=vs)
    me = bpy.data.meshes.new(name + "_src")
    bm.to_mesh(me)
    bm.free()
    tmp = bpy.data.objects.new(name + "_tmp", me)
    bpy.context.scene.collection.objects.link(tmp)
    rm = tmp.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel
    sm = tmp.modifiers.new("smooth", "SMOOTH")
    sm.factor = 0.9
    sm.iterations = smooth
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    for poly in out.polygons:
        poly.use_smooth = True
    out.materials.append(mat)
    ob = bpy.data.objects.new(name, out)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob


def _sphere(name, parent, loc, scale, mat, seg=24):
    me = bpy.data.meshes.new(name)
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.scale = scale
    return ob


def _cone(name, parent, loc, r1, r2, depth, mat, rot=(0, 0, 0)):
    import bmesh

    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r1, radius2=r2, depth=depth)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, depth / 2))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def build(name="pudu"):
    fur = _mat("pudu_fur", FUR, rough=0.85, sheen=0.6, bump=0.25, sss=0.05)
    dark = _mat("pudu_dark", FUR_DARK, rough=0.7, sheen=0.4, bump=0.2)
    snout = _mat("pudu_snout", SNOUT, rough=0.45)
    eye = _mat("pudu_eye", (0.004, 0.003, 0.003), rough=0.04)
    glint = _mat("pudu_glint", (1, 1, 1), emission=(1, 1, 1, 6.0))
    ear_in = _mat("pudu_ear_in", EAR_IN, rough=0.6, sss=0.3)
    antler = _mat("pudu_antler", ANTLER, rough=0.55)
    hoof = _mat("pudu_hoof", (0.02, 0.015, 0.012), rough=0.35)

    R = {}
    root = R["root"] = _empty(name + "_root")
    body = R["body"] = _empty(name + "_body", root, (0, 0, 0.27))
    # Compact, arched body: rump slightly higher than the shoulders.
    _blob(name + "_torso", [
        ((0.0, 0, 0.0), (0.17, 0.105, 0.105)),
        ((-0.11, 0, 0.02), (0.12, 0.112, 0.112)),
        ((0.11, 0, 0.0), (0.11, 0.098, 0.108)),
        ((0.19, 0, 0.06), (0.065, 0.06, 0.08)),
        ((0.0, 0, -0.05), (0.13, 0.085, 0.07)),
    ], body, fur, smooth=16)
    tail = R["tail"] = _empty(name + "_tailp", body, (-0.22, 0, 0.06))
    _sphere(name + "_tail", tail, (-0.015, 0, 0.0), (0.03, 0.022, 0.02), dark)

    neck = R["neck"] = _empty(name + "_neck", body, (0.19, 0, 0.06))
    _blob(name + "_neckm", [
        ((0.0, 0, 0.0), (0.06, 0.058, 0.07)),
        ((0.025, 0, 0.06), (0.055, 0.05, 0.07)),
        ((0.045, 0, 0.11), (0.048, 0.045, 0.05)),
    ], neck, fur)
    head = R["head"] = _empty(name + "_head", neck, (0.05, 0, 0.13))
    _blob(name + "_headm", [
        ((0.0, 0, 0.02), (0.078, 0.07, 0.068)),
        ((0.075, 0, -0.012), (0.06, 0.046, 0.044)),
        ((0.035, 0, -0.02), (0.06, 0.06, 0.05)),
        ((-0.015, 0, -0.06), (0.05, 0.048, 0.07)),  # throat, hides the neck seam
    ], head, fur, voxel=0.004)
    _sphere(name + "_snout", head, (0.118, 0, -0.022), (0.034, 0.033, 0.03), snout)
    _sphere(name + "_nose", head, (0.143, 0, -0.012), (0.014, 0.019, 0.012), snout)
    for s, side in ((1, "L"), (-1, "R")):
        ep = R["eye" + side] = _empty(f"{name}_eye{side}", head, (0.055, s * 0.05, 0.032))
        _sphere(f"{name}_eyeball{side}", ep, (0, 0, 0), (0.019, 0.017, 0.02), eye)
        _sphere(f"{name}_glint{side}", ep, (0.012, s * 0.008, 0.01), (0.004, 0.004, 0.004), glint, seg=8)
        ea = R["ear" + side] = _empty(f"{name}_ear{side}", head, (-0.03, s * 0.045, 0.06))
        _blob(f"{name}_earm{side}", [((0, s * 0.025, 0.03), (0.014, 0.03, 0.042))], ea, fur, voxel=0.003, smooth=3)
        _sphere(f"{name}_earin{side}", ea, (0.009, s * 0.026, 0.032), (0.006, 0.02, 0.03), ear_in)
        _cone(f"{name}_antler{side}", head, (-0.015, s * 0.026, 0.06), 0.009, 0.0015, 0.065, antler,
              rot=(s * -0.2, -0.45, 0))
    # Legs: hip/shoulder pivot (inside the torso) -> knee pivot -> hoof.
    for key, (x, y, z) in {"FL": (0.12, 0.058, -0.04), "FR": (0.12, -0.058, -0.04),
                           "HL": (-0.12, 0.06, -0.03), "HR": (-0.12, -0.06, -0.03)}.items():
        up = R["leg" + key] = _empty(f"{name}_leg{key}", body, (x, y, z))
        hind = key[0] == "H"
        _blob(f"{name}_thigh{key}", [((0, 0, -0.02), (0.05 if hind else 0.042, 0.036, 0.07)),
                                     ((0.0, 0, -0.085), (0.022, 0.02, 0.035))], up, fur, voxel=0.004)
        kn = R["knee" + key] = _empty(f"{name}_knee{key}", up, (0, 0, -0.11))
        _cone(f"{name}_shin{key}", kn, (0, 0, -0.105), 0.011, 0.016, 0.11, dark)
        _cone(f"{name}_hoof{key}", kn, (0, 0, -0.122), 0.015, 0.011, 0.02, hoof)
    # Optional nalca leaf hat (comedy ending), hidden by default.
    leaf = _mat("nalca_leaf", (0.06, 0.22, 0.03), rough=0.5, sss=0.2)
    hat = _sphere(name + "_leafhat", head, (0.0, 0.0, 0.11), (0.11, 0.1, 0.012), leaf)
    hat.rotation_euler = (0.2, -0.25, 0)
    R["hat"] = hat
    return R


def apply_pose(R, P, frame):
    """Set and keyframe every rig channel from pose dict P at `frame`."""
    root = R["root"]
    root.location = (P["x"], P["y"], 0.0)
    root.rotation_euler = (0, 0, math.radians(P["heading"]))
    body = R["body"]
    body.location = (0, 0, 0.27 + P.get("body_z", 0.0))
    body.rotation_euler = (math.radians(P.get("body_roll", 0)), math.radians(-P.get("body_pitch", 0)), 0)
    R["neck"].rotation_euler = (0, math.radians(-P.get("neck_pitch", 0)), math.radians(P.get("neck_yaw", 0)))
    R["head"].rotation_euler = (math.radians(P.get("head_roll", 0)), math.radians(-P.get("head_pitch", 0)),
                                math.radians(P.get("head_yaw", 0)))
    R["tail"].rotation_euler = (0, math.radians(-P.get("tail_lift", 10)), math.radians(P.get("tail_yaw", 0)))
    for s, side in ((1, "L"), (-1, "R")):
        ear = R["ear" + side]
        ear.rotation_euler = (math.radians(s * P.get("ear_out", 20)), math.radians(P.get("ear_back", 15)), 0)
        es = P.get("eye_scale", 1.0)
        R["eye" + side].scale = (es, es, es * P.get("blink", 1.0))
    for key in ("FL", "FR", "HL", "HR"):
        a, b = P.get("leg_" + key, (0.0, 0.0))
        R["leg" + key].rotation_euler = (0, math.radians(a), 0)
        R["knee" + key].rotation_euler = (0, math.radians(b), 0)
    R["hat"].hide_render = not P.get("hat", False)
    R["hat"].hide_viewport = R["hat"].hide_render
    for k in ("root", "body", "neck", "head", "tail", "earL", "earR"):
        o = R[k]
        o.keyframe_insert("location", frame=frame)
        o.keyframe_insert("rotation_euler", frame=frame)
    for k in ("eyeL", "eyeR"):
        R[k].keyframe_insert("scale", frame=frame)
    for key in ("FL", "FR", "HL", "HR"):
        R["leg" + key].keyframe_insert("rotation_euler", frame=frame)
        R["knee" + key].keyframe_insert("rotation_euler", frame=frame)
    R["hat"].keyframe_insert("hide_render", frame=frame)
