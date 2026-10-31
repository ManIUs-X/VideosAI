#!/usr/bin/env python3
"""Pudu Perceptual Shorts - one-command episode pipeline.

    python run.py --episode ep01_beep_speed --mode test       # 8 s prototype
    python run.py --episode ep01_beep_speed --mode animatic   # full, fast preview
    python run.py --episode ep01_beep_speed --mode final      # full, Cycles
    python run.py ... --device OPTIX   (or CUDA) on an NVIDIA machine

Stages: plan -> Blender 3D layer -> 2D composite (60 fps) -> audio -> mux
(illusion + control) -> verification report.  Re-running resumes the render.
"""

import argparse
import glob
import importlib
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from pudulab import audio as A  # noqa: E402
from pudulab import compositor, verify  # noqa: E402

MODES = {"test": ("test", 0.0, 8.0), "animatic": ("animatic", None, None), "final_cpu": ("final_cpu", None, None), "final": ("final", None, None),
         "final_hd": ("final_hd", None, None)}


def find_blender(explicit=None):
    for c in [explicit, os.environ.get("BLENDER"), shutil.which("blender"),
              *sorted(glob.glob("/opt/blender/*/blender")), *sorted(glob.glob(os.path.join(ROOT, ".blender/*/blender")))]:
        if c and os.path.exists(c):
            return c
    raise SystemExit("Blender not found: run tools/install_blender.sh or pass --blender")


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", default="ep01_beep_speed")
    ap.add_argument("--mode", default="test", choices=MODES)
    ap.add_argument("--t0", type=float)
    ap.add_argument("--t1", type=float)
    ap.add_argument("--device", default="CPU", choices=["CPU", "CUDA", "OPTIX"])
    ap.add_argument("--blender")
    ap.add_argument("--out", default=os.path.join(ROOT, "output"))
    ap.add_argument("--skip-render", action="store_true")
    a = ap.parse_args()

    ep = importlib.import_module(f"episodes.{a.episode}.episode")
    score = importlib.import_module(f"episodes.{a.episode}.score")
    quality, t0, t1 = MODES[a.mode]
    t0 = a.t0 if a.t0 is not None else (t0 if t0 is not None else 0.0)
    t1 = a.t1 if a.t1 is not None else (t1 if t1 is not None else ep.DURATION)
    out = os.path.join(a.out, a.episode, a.mode)
    os.makedirs(out, exist_ok=True)

    log(f"plan {a.episode} [{t0:.1f}, {t1:.1f}] s, quality={quality}")
    plan = ep.build_plan(t0, t1)
    plan_path = os.path.join(out, "plan.json")
    json.dump(plan, open(plan_path, "w"), default=float)

    if not a.skip_render:
        blender = find_blender(a.blender)
        log(f"blender: {blender}  device={a.device}")
        cmd = [blender, "-b", "--python-exit-code", "1", "-P", os.path.join(ROOT, "blender", "render_episode.py"),
               "--", plan_path, out, quality, "--device", a.device]
        with open(os.path.join(out, "blender.log"), "a") as fh:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:
                fh.write(line)
                if any(k in line for k in ("Saved:", "RENDER_DONE", "poses computed", "scene built", "Error", "GPU")):
                    print("   blender:", line.strip()[:160], flush=True)
            if p.wait():
                raise SystemExit("Blender failed, see blender.log")

    log("compositing 60 fps video")
    video = os.path.join(out, "video_only.mp4")
    compositor.render(plan, out, video, preview_png_dir=os.path.join(out, "preview"), log=log)

    log("synthesising audio")
    stems, events = score.build_stems(plan)
    i0, i1 = int(round(t0 * A.SR)), int(round(t1 * A.SR))
    gains = {"beeps": 1.0, "music": 0.9, "sfx": 1.0, "ambience": 1.0}
    mix = sum(stems[k] * g for k, g in gains.items())[i0:i1]
    ctrl = sum(stems[k] * g for k, g in gains.items() if k != "beeps")[i0:i1]
    norm = 0.89 / max(1e-9, np.abs(mix).max())
    A.write_wav(os.path.join(out, "mix_illusion.wav"), mix * norm)
    A.write_wav(os.path.join(out, "mix_control.wav"), ctrl * norm)
    A.write_wav(os.path.join(out, "stem_beeps.wav"), stems["beeps"][i0:i1] * norm)

    name = f"{a.episode}_{a.mode}"
    outs = {}
    for tag, wav in (("", "mix_illusion.wav"), ("_control", "mix_control.wav")):
        mp4 = os.path.join(out, f"{name}{tag}.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", os.path.join(out, wav), "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        "-shortest", "-movflags", "+faststart", mp4], check=True)
        outs[tag] = mp4
    log(f"wrote {outs['']} and control")

    log("verifying the decoded MP4")
    rep = verify.run(plan, outs[""], events, control_mp4=outs["_control"])
    rep["mode"] = a.mode
    rep["range_s"] = [t0, t1]
    json.dump(rep, open(os.path.join(out, "verification.json"), "w"), indent=1)
    print(json.dumps({k: rep[k] for k in ("specs", "specs_ok", "audio_ok", "stimulus_ok", "flash", "loudness",
                                          "all_ok") if k in rep}, indent=1))
    for tr in rep["trials"]:
        print("  ", json.dumps(tr))
    log("done" if rep["all_ok"] else "VERIFICATION FAILED - see verification.json")
    return 0 if rep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
