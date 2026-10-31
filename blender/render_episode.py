"""Blender entry point: build the scene from a plan and render the 3D layer.

    blender -b -P blender/render_episode.py -- PLAN.json OUTDIR QUALITY [--device CPU|CUDA|OPTIX]

QUALITY: animatic | test | final | final_hd
Writes OUTDIR/3d/######.png (60 fps frame numbers, every 2nd frame) and
OUTDIR/projections.json (screen position of the chase light per 60 fps frame).
Resumable: frames already on disk are skipped.
"""

import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import anim  # noqa: E402
import forest  # noqa: E402
import pudu  # noqa: E402
from pudulab import lights as L  # noqa: E402

QUALITY = {
    "animatic": dict(engine="BLENDER_WORKBENCH", res=(540, 960), samples=0),
    "test": dict(engine="CYCLES", res=(540, 960), samples=8, fast=True),
    "final_cpu": dict(engine="CYCLES", res=(540, 960), samples=10, fast=True),
    "final": dict(engine="CYCLES", res=(720, 1280), samples=32, blur=True),
    "final_hd": dict(engine="CYCLES", res=(1080, 1920), samples=64, blur=True),
}


def argv():
    a = sys.argv[sys.argv.index("--") + 1:]
    dev = "CPU"
    if "--device" in a:
        i = a.index("--device")
        dev = a[i + 1]
        a = a[:i] + a[i + 2:]
    return a[0], a[1], a[2], dev


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def setup_render(scene, q, device, out):
    Q = QUALITY[q]
    r = scene.render
    r.engine = Q["engine"]
    r.resolution_x, r.resolution_y = Q["res"]
    r.resolution_percentage = 100
    r.fps = 60
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.compression = 15
    r.use_overwrite = False
    r.use_placeholder = True
    r.filepath = os.path.join(out, "3d", "######")
    vs = scene.view_settings
    vs.view_transform = "AgX"
    try:
        vs.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    vs.exposure = 1.2
    if Q["engine"] == "CYCLES":
        c = scene.cycles
        c.samples = Q["samples"]
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.05
        c.use_denoising = True
        c.denoiser = "OPENIMAGEDENOISE"
        c.max_bounces = 4
        c.diffuse_bounces = 2
        c.glossy_bounces = 2
        c.transmission_bounces = 2
        c.volume_bounces = 0
        c.sample_clamp_indirect = 3.0
        c.use_light_tree = True
        r.use_motion_blur = Q.get("blur", False)
        r.motion_blur_shutter = 1.0  # one 60 fps frame = 180 deg at 30 fps
        if Q.get("fast"):  # CPU budget preset: AO-approximated GI, fewer bounces
            c.max_bounces = 3
            c.diffuse_bounces = 1
            c.glossy_bounces = 1
            c.use_fast_gi = True
            c.fast_gi_method = "REPLACE"
            c.ao_bounces_render = 1
        if device != "CPU":
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = device
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == device
            c.device = "GPU"
            print("GPU devices:", [(d.name, d.type, d.use) for d in prefs.devices])
        else:
            c.device = "CPU"
        scene.view_layers[0].use_pass_mist = True
        compositor(scene)
    else:
        sh = scene.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_shadows = True
        sh.show_cavity = True
        sh.background_type = "VIEWPORT"
        sh.background_color = (0.03, 0.05, 0.08)
        vs.view_transform = "Standard"
        vs.exposure = 0.0


def compositor(scene):
    scene.use_nodes = True
    nt = scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    mr = nt.nodes.new("CompositorNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 1.0
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 0.8
    nt.links.new(rl.outputs["Mist"], mr.inputs["Value"])
    mix = nt.nodes.new("CompositorNodeMixRGB")
    mix.inputs[2].default_value = (0.022, 0.04, 0.06, 1)
    nt.links.new(mr.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[1])
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "MEDIUM"
    glare.threshold = 0.8
    glare.size = 7
    nt.links.new(mix.outputs[0], glare.inputs[0])
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(glare.outputs[0], comp.inputs[0])


# ----------------------------------------------------------- cameras ------
def look_quat(pos, target):
    d = Vector(target) - Vector(pos)
    return d.to_track_quat("-Z", "Y")


def cam_state(shot, t):
    keys = shot["keys"]
    if t <= keys[0]["t"]:
        k = keys[0]
        return Vector(k["pos"]), Vector(k["target"]), k["lens"]
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            u = (t - a["t"]) / max(1e-9, b["t"] - a["t"])
            if len(keys) == 2 or shot["name"] != "track":
                u = anim.smooth(u)
            p = Vector(a["pos"]).lerp(Vector(b["pos"]), u)
            g = Vector(a["target"]).lerp(Vector(b["target"]), u)
            return p, g, a["lens"] + (b["lens"] - a["lens"]) * u
    k = keys[-1]
    return Vector(k["pos"]), Vector(k["target"]), k["lens"]


def shot_at(plan, t):
    for s in plan["shots"]:
        if s["start"] <= t < s["end"]:
            return s
    return plan["shots"][-1]


def screen_to_world(plan, shot, t, u, v, depth):
    pos, tgt, lens = cam_state(shot, t)
    q = look_quat(pos, tgt)
    w, h = plan["resolution"]
    half_h = 18.0 / lens  # sensor_fit AUTO: 36 mm on the larger (vertical) side
    half_w = half_h * w / h
    local = Vector(((u - 0.5) * 2 * half_w, (v - 0.5) * 2 * half_h, -1.0)) * depth
    return pos + q @ local


def world_to_screen(plan, shot, t, p):
    pos, tgt, lens = cam_state(shot, t)
    q = look_quat(pos, tgt)
    local = q.inverted() @ (Vector(p) - pos)
    if local.z >= -1e-6:
        return None
    w, h = plan["resolution"]
    half_h = 18.0 / lens
    half_w = half_h * w / h
    x = local.x / -local.z
    y = local.y / -local.z
    return 0.5 + x / (2 * half_w), 0.5 + y / (2 * half_h), -local.z


def main():
    plan_path, out, quality, device = argv()
    plan = json.load(open(plan_path))
    os.makedirs(os.path.join(out, "3d"), exist_ok=True)
    fps = plan["fps"]
    t0, t1 = plan["range"]
    f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
    for s in plan["shots"]:
        assert round(s["start"] * fps) % 2 == 0, "cuts must fall on even frames"

    clear()
    scene = bpy.context.scene
    setup_render(scene, quality, device, out)
    scene.frame_start, scene.frame_end, scene.frame_step = f0, f1 - 1, 2

    keepout = [(12.0, 1.2, 1.4), (11.0, 1.0, 0.9), (13.3, -1.6, 0.8), (12.2, -1.3, 0.8)]
    coll, mats = forest.build(seed=7, keepout=keepout)
    forest.nalca_patch(coll, mats)
    forest.fallen_log(coll, mats)
    forest.sky_and_moon(scene)
    spore_list = forest.spores(coll, 5, ((-12, 16), (-1.5, 3.5), (0.1, 1.6)), count=60)
    R = pudu.build()

    # Cameras: one per shot, bound with timeline markers.
    cams = {}
    for s in plan["shots"]:
        cam = bpy.data.objects.new("cam_" + s["name"], bpy.data.cameras.new("cam_" + s["name"]))
        cam.data.sensor_fit = "AUTO"
        cam.data.sensor_width = 36
        cam.data.clip_start = 0.02
        cam.data.clip_end = 400
        cam.rotation_mode = "QUATERNION"
        scene.collection.objects.link(cam)
        cams[s["name"]] = cam
        m = scene.timeline_markers.new(s["name"], frame=int(round(s["start"] * fps)))
        m.camera = cam
    scene.camera = cams[shot_at(plan, t0)["name"]]

    # 3D lights that illuminate the scene behind the 2D stimulus sprites.
    col = plan["light_style"]["color"]
    lamps = {}
    for name in ("left", "right", "chase"):
        ld = bpy.data.lights.new("stim_" + name, "POINT")
        ld.color = col
        ld.shadow_soft_size = 0.15
        ob = bpy.data.objects.new("stim_" + name, ld)
        ob.visible_camera = False
        scene.collection.objects.link(ob)
        lamps[name] = ob

    def light_world(side, t):
        f = int(round(t * fps))
        st = L.stimulus_state(plan, f)
        shot = shot_at(plan, t)
        for s in st:
            if s["side"] == side:
                u, v = L.to_uv(plan, s["x"], s["y"])
                return screen_to_world(plan, shot, t, u, v, plan["light_depth"][shot["name"]]), s["intensity"]
        return None, 0.0

    def target_fn(name, t):
        if name == "chase":
            return L.chase_state(plan, int(round(t * fps)))
        if name == "camera":
            return tuple(cam_state(shot_at(plan, t), t)[0])
        if name.startswith("light:"):
            p, _ = light_world("left" if name.endswith("L") else "right", t)
            return tuple(p) if p is not None else None
        if name == "lights":
            a, _ = light_world("left", t)
            b, _ = light_world("right", t)
            return tuple((a + b) / 2) if a is not None else None
        return tuple(name)

    t_start = time.time()
    poses = anim.compute(plan, target_fn, fps)
    print(f"poses computed in {time.time() - t_start:.1f}s")

    proj = {}
    for f in range(f0, f1):
        t = f / fps
        shot = shot_at(plan, t)
        P = dict(poses[f])
        for k, v in P.pop("legs").items():
            P["leg_" + k] = v
        pudu.apply_pose(R, P, f)
        cam = cams[shot["name"]]
        pos, tgt, lens = cam_state(shot, t)
        cam.location = pos
        cam.rotation_quaternion = look_quat(pos, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
        cam.data.keyframe_insert("lens", frame=f)
        for side in ("left", "right"):
            p, inten = light_world(side, t)
            ob = lamps[side]
            if p is not None:
                ob.location = p
            ob.data.energy = (0.5 if shot["name"] == "hook" else 9.0) * inten
            ob.keyframe_insert("location", frame=f)
            ob.data.keyframe_insert("energy", frame=f)
        c = L.chase_state(plan, f)
        ob = lamps["chase"]
        if c is not None:
            ob.location = c
            sp = world_to_screen(plan, shot, t, c)
            if sp:
                proj[f] = [sp[0], sp[1], sp[2]]
        ob.data.energy = 12.0 if c is not None else 0.0
        ob.keyframe_insert("location", frame=f)
        ob.data.keyframe_insert("energy", frame=f)
        if f % 10 == 0:
            hide = 12.0 <= t < 46.0  # no extra moving lights near the test stimuli
            for o, base, ph in spore_list:
                o.location = (base[0] + 0.15 * math.sin(0.3 * t + ph), base[1] + 0.1 * math.cos(0.23 * t + ph),
                              base[2] + 0.12 * math.sin(0.4 * t + 2 * ph))
                o.keyframe_insert("location", frame=f)
                o.hide_render = hide
                o.keyframe_insert("hide_render", frame=f)
    stills = os.environ.get("PUDU_STILLS")
    if stills:
        scene.render.use_overwrite = True
        scene.render.use_placeholder = False
        for f in map(int, stills.split(",")):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out, "stills", f"{f:06d}.png")
            bpy.ops.render.render(write_still=True)
            print("Saved still", f)
        return
    json.dump({"fps": fps, "chase": proj}, open(os.path.join(out, "projections.json"), "w"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "scene.blend"))
    print(f"scene built in {time.time() - t_start:.1f}s; rendering {f0}..{f1 - 1} step 2")
    t_r = time.time()
    bpy.ops.render.render(animation=True)
    print(f"RENDER_DONE {time.time() - t_r:.1f}s")


main()
