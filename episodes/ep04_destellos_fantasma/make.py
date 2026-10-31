#!/usr/bin/env python3
"""Episode 04 end to end: render (parallel) -> audio -> 3 MP4s -> verification.

    python -m episodes.ep04_destellos_fantasma.make [--t0 0 --t1 48.5] [--jobs 4]

Outputs in output/ep04_destellos_fantasma/<range>/:
    ep04_destellos_fantasma.mp4            experimental version (B2F1 beeps)
    ep04_destellos_fantasma_sin_bips.mp4   same video, music/sfx, NO beeps
    ep04_destellos_fantasma_sin_sonido.mp4 same video, silent audio track
    verification.json, plan.json, stems, preview/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from pudulab import audio as A  # noqa: E402
from pudulab import verify as V  # noqa: E402
from pudulab.illusions import sound_flash as SF  # noqa: E402

from episodes.ep04_destellos_fantasma import episode as E  # noqa: E402
from episodes.ep04_destellos_fantasma import score  # noqa: E402

_R = None


def _init():
    global _R
    _R = E.Renderer()


def _frame(f):
    return f, _R.frame(f).tobytes()


def log(m):
    print(time.strftime("[%H:%M:%S] ") + m, flush=True)


def render_video(path, f0, f1, jobs, preview_dir):
    from PIL import Image

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{E.W}x{E.H}",
           "-r", str(E.FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-profile:v", "high",
           "-level", "4.2", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-colorspace", "bt709", "-g", "60", "-movflags", "+faststart", path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    os.makedirs(preview_dir, exist_ok=True)
    t = time.time()
    with mp.Pool(jobs, initializer=_init) as pool:
        for f, buf in pool.imap(_frame, range(f0, f1), chunksize=6):
            ff.stdin.write(buf)
            if f % 60 == 0:
                Image.frombytes("RGB", (E.W, E.H), buf).save(os.path.join(preview_dir, f"t{f / E.FPS:05.1f}.jpg"),
                                                            quality=85)
            if f % 300 == 0:
                log(f"  frame {f}/{f1} ({(time.time() - t) / max(1, f - f0 + 1):.2f} s/frame)")
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError("ffmpeg failed")


def mux(video, wav, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart",
                    out], check=True)


# ------------------------------------------------------------ verification --
def roi_series(path, fps_filter=None):
    """Mean luma (0..1) inside the flash disk, every decoded frame."""
    x, y, r = E.FLASH[0], E.FLASH[1], E.FLASH_R
    s = 2 * r
    vf = f"crop={s}:{s}:{x - r}:{y - r}"
    if fps_filter:
        vf = f"fps={fps_filter}," + vf
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, s, s).astype(np.float32) / 255
    yy, xx = np.mgrid[0:s, 0:s]
    disk = np.hypot(xx + 0.5 - r, yy + 0.5 - r) < r * 0.8
    return fr[:, disk].mean(1)


def other_changes(path, t, pad=0.5, thr=0.06):
    """Frame-to-frame changes OUTSIDE the flash region around a flash, in the
    decoded file.  Returns (max change, max number of half-res pixels above
    `thr` in one frame step).  H.264 requantises a few text edges when the
    flash frame arrives, so a handful of pixels is codec noise; a real
    second visual event (a blink, a caption change) moves thousands."""
    fr = V.decode_gray(path, max(0, t - pad), 2 * pad, E.W, E.H, scale=2)
    x, y, r = E.FLASH[0] // 2, E.FLASH[1] // 2, E.FLASH_R // 2 + 4
    m = np.ones(fr.shape[1:], bool)
    m[y - r:y + r, x - r:x + r] = False
    d = np.abs(np.diff(fr, axis=0))[:, m]
    return float(d.max()), int((d > thr).sum(1).max())


def source_only_flash(R, onset_frame, n):
    """Exact check on the rendered (pre-codec) frames: from onset-3 to
    onset+n+2 the only pixels that ever change are inside the flash disk."""
    fs = range(onset_frame - 3, onset_frame + n + 3)
    frames = [R.frame(f).astype(np.int16) for f in fs]
    y0, y1, x0, x1 = R.flash_box
    changed = 0
    for a, b in zip(frames, frames[1:]):
        d = np.abs(a - b).max(2)
        d[y0:y1, x0:x1] = 0
        changed = max(changed, int((d > 0).sum()))
    inside = int((np.abs(frames[3] - frames[2]).max(2)[y0:y1, x0:x1] > 0).sum())
    return changed, inside


def video_md5(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v", "-c", "copy", "-f", "md5", "-"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out


def verify(outs, plan, f0, f1):
    rep = {}
    exp = outs["experimental"]
    pr = V.probe(exp)
    vs = next(s for s in pr["streams"] if s["codec_type"] == "video")
    au = next(s for s in pr["streams"] if s["codec_type"] == "audio")
    num, den = map(int, vs["avg_frame_rate"].split("/"))
    rep["specs"] = {"codec": vs["codec_name"], "profile": vs.get("profile"), "w": vs["width"], "h": vs["height"],
                    "fps": num / den, "pix_fmt": vs["pix_fmt"], "audio": au["codec_name"],
                    "sample_rate": int(au["sample_rate"]), "channels": au["channels"],
                    "duration_s": float(pr["format"]["duration"])}
    s = rep["specs"]
    rep["specs_ok"] = (s["codec"] == "h264" and (s["w"], s["h"]) == (1080, 1920) and abs(s["fps"] - 60) < 1e-6 and
                       s["sample_rate"] == 48000 and s["channels"] == 2 and s["duration_s"] <= 50.0)
    # identical picture in all three versions
    md5 = {k: video_md5(v) for k, v in outs.items()}
    rep["same_video_all_versions"] = len(set(md5.values())) == 1

    # visual events, 60 fps (as delivered) and after a 30 fps re-encode
    trials = [t for t in plan["trials"] if f0 <= t["onset_frame"] < f1]
    lum = roi_series(exp)
    ev = SF.detect_flashes(lum)
    planned = [t["onset_frame"] - f0 for t in trials]
    rep["visual_events_60fps"] = [{"frame": f + f0, "t_s": (f + f0) / E.FPS, "frames": n,
                                   "peak_luma": float(lum[f:f + n].max())} for f, n in ev]
    lum30 = roi_series(exp, fps_filter=30)
    ev30 = SF.detect_flashes(lum30, win=15)
    rep["visual_events_30fps_reencode"] = [{"t_s": f / 30 + f0 / E.FPS, "frames": n} for f, n in ev30]
    rep["unplanned_visual_events"] = [{"t_s": (f + f0) / E.FPS, "frames": n} for f, n in ev if f not in planned]
    rep["visual_ok"] = ([f for f, _ in ev] == planned and all(n == t["flash_frames"] for (_, n), t in zip(ev, trials))
                        and len(ev30) == len(trials) and all(n == 1 for _, n in ev30))

    # auditory events
    x = V.decode_audio(exp)
    on, amp = SF.detect_beeps(x)
    rep["beeps_detected"] = [{"t_s": float(a) + f0 / E.FPS, "amp": float(b)} for a, b in zip(on, amp)]
    exp_beeps = sorted(b - f0 / E.FPS for t in trials for b in t["beep_times_s"])  # file time
    err = [float(min(abs(on - b)) * 1000) if len(on) else None for b in exp_beeps]
    rep["beep_count"] = {"expected": len(exp_beeps), "detected": int(len(on))}
    rep["beep_onset_err_ms_max"] = max(err) if err else 0.0
    rep["audio_ok"] = len(on) == len(exp_beeps) and (not err or max(err) < 1.0)

    # per-trial synchrony, measured: flash onset (decoded frames) vs beeps (decoded audio)
    per = []
    R = E.Renderer()
    by_frame = dict(ev)
    for t in trials:
        fe = t["onset_frame"] - f0
        n = by_frame.get(fe, 0)
        tf = fe / E.FPS  # file time
        bs = [b for b in on if tf - 0.05 < b < tf + 0.2]
        d = {"name": t["name"], "condition": t["condition"], "flashes_seen_in_video": int(n > 0), "flash_frames": n,
             "beeps_in_window": len(bs), "flash_onset_s": tf + f0 / E.FPS}
        if bs:
            d["beep1_minus_flash_ms"] = round((bs[0] - tf) * 1000, 2)
        if len(bs) > 1:
            d["inter_beep_ms"] = round((bs[1] - bs[0]) * 1000, 2)
        d["decoded_max_other_change"], d["decoded_pixels_over_0.06_outside_flash"] = other_changes(exp, tf)
        d["source_pixels_changed_outside_flash"], d["source_pixels_changed_in_flash"] = source_only_flash(
            R, t["onset_frame"], t["flash_frames"])
        d["ok"] = (len(bs) == t["beeps"] and (not bs or abs(d["beep1_minus_flash_ms"]) <= 1.0) and
                   (len(bs) < 2 or abs(d["inter_beep_ms"] - 66) <= 1.0) and
                   d["source_pixels_changed_outside_flash"] == 0 and d["decoded_pixels_over_0.06_outside_flash"] < 200)
        per.append(d)
    rep["trials"] = per
    rep["sync_ok"] = len(per) == len(trials) and all(d["ok"] for d in per)

    # other versions
    xs = V.decode_audio(outs["sin_bips"])
    on2, _ = SF.detect_beeps(xs)
    rep["sin_bips_detected_beeps"] = int(len(on2))
    xm = V.decode_audio(outs["sin_sonido"])
    rep["sin_sonido_peak"] = float(np.abs(xm).max())
    rep["versions_ok"] = rep["same_video_all_versions"] and len(on2) == 0 and rep["sin_sonido_peak"] < 1e-4

    # safety
    rep["flash"] = V.flash_check(exp, E.W, E.H, E.FPS)
    rep["flash_area_fraction"] = float(np.pi * E.FLASH_R ** 2 / (E.W * E.H))
    rep["min_gap_between_flashes_s"] = float(np.diff([t["onset_s"] for t in trials]).min()) if len(trials) > 1 else None
    rep["loudness"] = V.loudness(exp)
    rep["all_ok"] = all(rep[k] for k in ("specs_ok", "visual_ok", "audio_ok", "sync_ok", "versions_ok")) and \
        rep["flash"]["pass"]
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=E.DURATION)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--out", default=os.path.join(ROOT, "output", E.EPISODE_ID))
    ap.add_argument("--skip-render", action="store_true")
    a = ap.parse_args()
    f0, f1 = int(round(a.t0 * E.FPS)), int(round(a.t1 * E.FPS))
    tag = "full" if (a.t0, a.t1) == (0.0, E.DURATION) else f"{a.t0:g}-{a.t1:g}s"
    out = os.path.join(a.out, tag)
    os.makedirs(out, exist_ok=True)
    plan = E.plan()
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"), indent=1, default=float)
    video = os.path.join(out, "video_only.mp4")
    if not a.skip_render:
        log(f"rendering {f1 - f0} frames with {a.jobs} workers")
        render_video(video, f0, f1, a.jobs, os.path.join(out, "preview"))
    log("audio")
    stems, events = score.build_stems()
    i0, i1 = int(round(a.t0 * A.SR)), int(round(a.t1 * A.SR))
    full = sum(stems.values())
    norm = 0.8 / np.abs(full).max()
    mix = full[i0:i1] * norm
    nob = sum(v for k, v in stems.items() if k != "beeps")[i0:i1] * norm
    A.write_wav(os.path.join(out, "mix_experimental.wav"), mix)
    A.write_wav(os.path.join(out, "mix_sin_bips.wav"), nob)
    A.write_wav(os.path.join(out, "mix_sin_sonido.wav"), np.zeros_like(mix))
    A.write_wav(os.path.join(out, "stem_beeps.wav"), stems["beeps"][i0:i1] * norm)
    log(f"beep peak in mix: {np.abs(stems['beeps']).max() * norm:.3f}, music peak: "
        f"{np.abs(stems['music']).max() * norm:.3f}")
    base = E.EPISODE_ID
    outs = {"experimental": os.path.join(out, f"{base}.mp4"),
            "sin_bips": os.path.join(out, f"{base}_sin_bips.mp4"),
            "sin_sonido": os.path.join(out, f"{base}_sin_sonido.mp4")}
    mux(video, os.path.join(out, "mix_experimental.wav"), outs["experimental"])
    mux(video, os.path.join(out, "mix_sin_bips.wav"), outs["sin_bips"])
    mux(video, os.path.join(out, "mix_sin_sonido.wav"), outs["sin_sonido"])
    log("verifying the decoded MP4s")
    rep = verify(outs, plan, f0, f1)
    json.dump(rep, open(os.path.join(out, "verification.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("beeps_detected",)}, indent=1))
    log("ALL OK" if rep["all_ok"] else "VERIFICATION FAILED")
    return 0 if rep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
