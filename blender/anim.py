"""Pudu performance evaluator: plan actions -> per-frame pose dicts.

Pure Python (no bpy) so it can be unit-tested outside Blender.  Poses are
simulated from t=0 for every frame of the episode, so rendering any sub-range
yields exactly the same motion as the full render.
"""

import bisect
import math


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def window(t, a, b, ramp=0.25):
    if t <= a or t >= b:
        return 0.0
    r = min(ramp, (b - a) / 2)
    return smooth((t - a) / r) * smooth((b - t) / r)


def lerp_angle(a, b, k):
    d = (b - a + 180) % 360 - 180
    return a + d * k


class Track:
    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k["t"])
        self.ts = [k["t"] for k in self.keys]

    def __call__(self, t):
        i = bisect.bisect_right(self.ts, t) - 1
        if i < 0:
            return dict(self.keys[0])
        if i >= len(self.keys) - 1:
            return dict(self.keys[-1])
        a, b = self.keys[i], self.keys[i + 1]
        k = (t - a["t"]) / (b["t"] - a["t"])
        if b["t"] - a["t"] > 0.3:  # long moves ease in/out
            k = smooth(k)
        return {"t": t, "x": a["x"] + (b["x"] - a["x"]) * k, "y": a["y"] + (b["y"] - a["y"]) * k,
                "heading": lerp_angle(a["heading"], b["heading"], k)}


BLINKS = [1.3, 4.6, 7.4, 10.9, 13.9, 19.1, 25.3, 28.8, 30.4, 36.6, 44.2, 51.2, 53.6]


def compute(plan, target_fn, fps=60):
    """Return list of pose dicts for frames 0..N-1.

    target_fn(name, t) -> (x, y, z) world point or None.
    """
    n = int(round(plan["duration"] * fps))
    track = Track(plan["pudu_track"])
    acts = plan["pudu_actions"]
    by = {}
    for a in acts:
        by.setdefault(a["type"], []).append(a)

    def active(kind, t):
        return [a for a in by.get(kind, []) if a["start"] <= t < a["end"]]

    poses = []
    yaw_s = pitch_s = 0.0
    dt = 1.0 / fps
    for f in range(n):
        t = f / fps
        tr = track(t)
        P = {"x": tr["x"], "y": tr["y"], "heading": tr["heading"], "body_z": 0.0, "body_pitch": 0.0,
             "body_roll": 0.0, "neck_pitch": 8.0, "neck_yaw": 0.0, "head_pitch": 0.0, "head_yaw": 0.0,
             "head_roll": 0.0, "ear_out": 25.0, "ear_back": 12.0, "eye_scale": 1.0, "blink": 1.0,
             "tail_yaw": 0.0, "tail_lift": 15.0, "hat": t >= 50.0}
        legs = {k: [0.0, 0.0] for k in ("FL", "FR", "HL", "HR")}
        # breathing + blinks (never tied to stimulus events)
        P["body_z"] += 0.003 * math.sin(2 * math.pi * 0.3 * t)
        for b in BLINKS:
            if b <= t < b + 0.16:
                P["blink"] = 0.12 + 0.88 * abs((t - b) / 0.08 - 1)
        # --- run cycle (bounding gait)
        for a in active("run", t):
            w = window(t, a["start"], a["end"], 0.2)
            ph = 2 * math.pi * a.get("stride_hz", 3.0) * (t - a["start"])
            for k, off in (("FL", 0.0), ("FR", 0.25), ("HL", math.pi), ("HR", math.pi + 0.25)):
                s = math.sin(ph + off)
                legs[k][0] += w * 38 * s
                knee = 45 * max(0.0, math.sin(ph + off + math.pi / 2))
                legs[k][1] += w * (knee if k[0] == "F" else -knee)
            P["body_z"] += w * (0.028 * abs(math.sin(ph)) + 0.01)
            P["body_pitch"] += w * 5 * math.sin(ph + 0.5)
            P["head_pitch"] += w * 4 * math.sin(2 * ph)
            P["ear_back"] += w * 40
            P["tail_lift"] += w * 30
        # --- look (smoothed, split neck/head)
        tgt = None
        for a in active("look", t):
            tgt = target_fn(a["target"], t)
        yaw_t, pitch_t = 0.0, 0.0
        if tgt is not None:
            h = math.radians(tr["heading"])
            hx = tr["x"] + math.cos(h) * 0.26
            hy = tr["y"] + math.sin(h) * 0.26
            dx, dy, dz = tgt[0] - hx, tgt[1] - hy, tgt[2] - 0.46
            lx = math.cos(-h) * dx - math.sin(-h) * dy
            ly = math.sin(-h) * dx + math.cos(-h) * dy
            yaw_t = max(-80, min(80, math.degrees(math.atan2(ly, lx))))
            pitch_t = max(-35, min(32, math.degrees(math.atan2(dz, math.hypot(lx, ly)))))
        if f == 0:
            yaw_s, pitch_s = yaw_t, pitch_t
        k = 1 - math.exp(-dt / 0.12)
        yaw_s += (yaw_t - yaw_s) * k
        pitch_s += (pitch_t - pitch_s) * k
        P["neck_yaw"] += 0.35 * yaw_s
        P["head_yaw"] += 0.65 * yaw_s
        P["neck_pitch"] += 0.4 * pitch_s
        P["head_pitch"] += 0.6 * pitch_s
        # --- expressive layers
        for a in active("ears_up", t):
            w = window(t, a["start"], a["end"], 0.3)
            P["ear_back"] -= 25 * w
            P["ear_out"] -= 10 * w
        for a in active("surprise", t):
            u = (t - a["start"]) / (a["end"] - a["start"])
            w = window(t, a["start"], a["end"], 0.12)
            P["eye_scale"] += 0.35 * w
            P["ear_back"] -= 30 * w
            P["ear_out"] -= 12 * w
            P["head_pitch"] += 8 * w
            if u < 0.5:
                P["body_z"] += 0.07 * math.sin(math.pi * u / 0.5)
        for a in active("nod", t):
            u = (t - a["start"]) / (a["end"] - a["start"])
            P["head_pitch"] -= 14 * math.sin(2 * math.pi * 2 * u) * window(t, a["start"], a["end"], 0.1)
        for a in active("hop", t):
            u = (t - a["start"]) / (a["end"] - a["start"])
            air = math.sin(math.pi * u)
            P["body_z"] += 0.13 * air
            P["body_pitch"] += 10 * math.cos(math.pi * u)
            for kk in ("FL", "FR"):
                legs[kk][0] -= 25 * air
                legs[kk][1] += 50 * air
            for kk in ("HL", "HR"):
                legs[kk][0] += 30 * air
                legs[kk][1] -= 40 * air
            P["ear_back"] += 20 * air
        for a in active("tail_wag", t):
            w = window(t, a["start"], a["end"], 0.3)
            P["tail_yaw"] += 35 * math.sin(2 * math.pi * 7 * t) * w
            P["tail_lift"] += 35 * w
        for a in active("tilt", t):
            P["head_roll"] += 20 * window(t, a["start"], a["end"], 0.3)
        for a in active("shake", t):
            u = (t - a["start"]) / (a["end"] - a["start"])
            w = window(t, a["start"], a["end"], 0.08)
            P["head_yaw"] += 30 * math.sin(2 * math.pi * 5 * u) * (1 - 0.6 * u) * w
            P["ear_out"] += 35 * abs(math.sin(2 * math.pi * 5 * u)) * w
        for a in active("fall", t):
            s = t - a["start"]
            rear = smooth(s / 0.3) * (1 - smooth((s - 0.3) / 0.4))
            P["body_pitch"] += 22 * rear
            down = smooth((s - 0.35) / 0.55)
            P["body_roll"] -= 82 * down
            P["body_z"] -= 0.15 * down
            P["eye_scale"] += 0.3
            P["ear_out"] += 30 * down
            P["head_pitch"] -= 10 * down
            kick = max(0.0, 1 - (s - 1.0) / 1.8) if s > 1.0 else 0.0
            for kk, off in (("FL", 0), ("FR", 1.3), ("HL", 2.1), ("HR", 0.7)):
                legs[kk][0] += 30 * kick * math.sin(2 * math.pi * 6 * s + off) - 20 * down
                legs[kk][1] += 30 * down
        for a in active("pop_up", t):
            u = (t - a["start"]) / (a["end"] - a["start"])
            spring = 1 - math.exp(-6 * u) * math.cos(14 * u)
            P["body_z"] += -0.34 * (1 - spring) + 0.04
            P["ear_out"] += 30 * math.exp(-4 * u) * math.sin(25 * u)
        if t >= 51.0:
            P["body_z"] += 0.04
        P["legs"] = legs
        poses.append(P)
    return poses
