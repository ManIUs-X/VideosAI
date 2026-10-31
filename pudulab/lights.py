"""Frame-exact state of the stimulus lights (screen space, height units).

Shared by Blender (to place matching 3D point lights for illumination) and by
the compositor (which draws the actual stimulus at the output frame rate, so
the stimulus never depends on render noise or 3D interpolation).

Rules:
  * during a trial window, positions come verbatim from the trial arrays and
    luminance is constant (1.0) - nothing visual is locked to the beeps;
  * between trials of the same shot the lights freeze at their last position
    and fade to a dim level; a new trial starts abruptly at full intensity,
    as in the laboratory task;
  * lights only exist inside the shot that contains their trials.
"""

from __future__ import annotations


def _shot_at(plan, t):
    for s in plan["shots"]:
        if s["start"] <= t < s["end"]:
            return s
    return plan["shots"][-1]


def stimulus_state(plan, frame):
    """Return list of dicts {side, x, y, intensity, trial, active} at 60 fps frame."""
    fps = plan["fps"]
    t = frame / fps
    style = plan["light_style"]
    shot = _shot_at(plan, t)
    trials = [tr for tr in plan["trials"] if shot["start"] <= tr["start"] < shot["end"]]
    if not trials:
        return []
    trials.sort(key=lambda tr: tr["start"])
    appear = plan.get("lights_appear", {}).get(shot["name"], trials[0]["start"])
    if t < appear:
        return []
    fade = style["fade_s"]
    dim = style["dim_between"]
    out = []
    prev = None
    for tr in trials:
        f0 = int(round(tr["start"] * fps))
        if frame < f0:
            break
        prev = tr
    for side in ("left", "right"):
        if prev is None:  # before first trial: preview at first frame, faded in
            tr = trials[0]
            x, y = tr["xy"][side][0]
            k = min(1.0, (t - appear) / fade)
            out.append({"side": side, "x": x, "y": y, "intensity": dim * k, "trial": tr["name"], "active": False})
            continue
        tr = prev
        f0 = int(round(tr["start"] * fps))
        i = frame - f0
        if i < tr["frames"]:
            x, y = tr["xy"][side][i]
            out.append({"side": side, "x": x, "y": y, "intensity": 1.0, "trial": tr["name"], "active": True})
        else:
            x, y = tr["xy"][side][-1]
            k = min(1.0, (i - tr["frames"]) / fps / fade)
            out.append({"side": side, "x": x, "y": y, "intensity": 1.0 + (dim - 1.0) * k,
                        "trial": tr["name"], "active": False})
    return out


def audiovisual_side(plan, frame):
    st = stimulus_state(plan, frame)
    if not st:
        return None
    name = st[0]["trial"]
    tr = next(tr for tr in plan["trials"] if tr["name"] == name)
    return tr["spec"]["av_side"] if tr["spec"]["beeps"] else None


def chase_state(plan, frame):
    """World position of the chase light at a 60 fps frame, or None."""
    ch = plan["chase"]
    f0 = int(round(ch["start"] * plan["fps"]))
    i = frame - f0
    if 0 <= i < ch["frames"]:
        return ch["world"][i]
    return None


def to_uv(plan, x, y):
    """Height units -> normalised screen (u right, v up, 0..1)."""
    w, h = plan["resolution"]
    return 0.5 + x * h / w, 0.5 + y
