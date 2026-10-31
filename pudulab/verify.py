"""Independent checks on the final MP4 (decoded back from the file itself).

1. container/stream specs (H.264, 1080x1920, fps, AAC 48 kHz stereo, <= 60 s)
2. beep onsets measured in the decoded audio vs. the scheduled events
3. light reversals measured in the decoded video vs. the scheduled reversals,
   and the lag between each measured visual reversal and its measured beep
4. constant physical angular speed of both lights in the decoded video
5. photosensitive flash heuristic (WCAG 2.3.1-style general-flash count)
6. integrated loudness / true peak (EBU R128)
"""

from __future__ import annotations

import json
import re
import subprocess

import numpy as np
from scipy import signal

from . import lights as L


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def decode_audio(path, sr=48000):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def beep_onsets(x, sr=48000, t_offset=0.0, hz=440.0, ms=68.0):
    """Matched filter: correlate with the exact beep template; the peak of the
    correlation envelope marks the onset without filter-delay bias."""
    from .audio import beep

    m = x.mean(1).astype(np.float64)
    tmpl = beep(hz, ms, amp=1.0)
    c = signal.fftconvolve(m, tmpl[::-1], mode="full")
    env = np.abs(signal.hilbert(c))
    ref = (tmpl ** 2).sum()  # envelope height of a full-scale, isolated beep
    peaks, _ = signal.find_peaks(env, height=0.08 * ref, distance=int(0.15 * sr))
    return (peaks - (len(tmpl) - 1)) / sr + t_offset


def decode_gray(path, t0, dur, W, H, scale=2):
    w, h = W // scale, H // scale
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.4f}", "-i", path, "-t", f"{dur:.4f}",
                          "-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32) / 255.0


def track_trial(plan, tr, path, scale=2):
    """Measure light angles in the decoded video for one trial."""
    W, H = plan["resolution"]
    fps = plan["fps"]
    sp = tr["spec"]
    # decode with a 0.5 frame margin so frame k of the stream lands at index k
    frames = decode_gray(path, tr["start"] - plan["range"][0] + 0.5 / fps, tr["frames"] / fps, W, H, scale)
    n = min(len(frames), tr["frames"])
    res = {}
    for side, sx in (("left", -1), ("right", 1)):
        cx = (0.5 + sx * sp["center_offset_x"] * H / W) * W / scale
        cy = (0.5 - sp["center_y"]) * H / scale
        r = sp["radius"] * H / scale
        yy, xx = np.mgrid[0:frames.shape[1], 0:frames.shape[2]]
        ring = np.abs(np.hypot(xx - cx, yy - cy) - r) < r * 0.45
        angs = []
        for k in range(n):
            fr = frames[k] * ring
            thr = fr.max() * 0.92
            m = fr >= thr
            px, py = (xx[m] * fr[m]).sum() / fr[m].sum(), (yy[m] * fr[m]).sum() / fr[m].sum()
            angs.append(np.arctan2(-(py - cy), px - cx))
        a = np.unwrap(np.array(angs))
        d = np.diff(a)
        sgn = np.sign(signal.medfilt(d, 5))
        flips = np.where(sgn[1:] * sgn[:-1] < 0)[0] + 1
        # Speed: robust median of |d| away from reversals
        mask = np.ones(len(d), bool)
        for fl in flips:
            mask[max(0, fl - 3):fl + 3] = False
        speed = float(np.median(np.abs(d[mask])) * fps / (2 * np.pi))
        res[side] = {"measured_reversal_frames": flips.tolist(), "expected": tr["reversal_frames"][side],
                     "speed_rps": speed}
    return res


def flash_check(path, W, H, fps, t0=0.0):
    frames = decode_gray(path, t0, 1e6, W, H, scale=8)
    lum = frames ** 2.2  # approx relative luminance
    q = []
    h, w = lum.shape[1:]
    for (y0, y1, x0, x1) in ((0, h, 0, w), (0, h // 2, 0, w), (h // 2, h, 0, w)):
        m = lum[:, y0:y1, x0:x1].mean((1, 2))
        d = np.diff(m)
        big = np.where(np.abs(d) > 0.1)[0]
        worst = 0
        for i in big:
            win = big[(big >= i) & (big < i + fps)]
            # pairs of opposing changes
            s = np.sign(d[win])
            worst = max(worst, int(np.sum(s[1:] != s[:-1])) // 1)
        q.append(worst)
    return {"max_opposing_large_transitions_per_s": max(q), "pass": max(q) < 3,
            "max_mean_luma_step": float(np.abs(np.diff(lum.mean((1, 2)))).max())}


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null",
                          "-"], capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return {"integrated_lufs": float(i[-1]) if i else None, "true_peak_dbfs": float(tp[-1]) if tp else None}


def run(plan, mp4, events, control_mp4=None):
    W, H = plan["resolution"]
    fps = plan["fps"]
    t0, t1 = plan["range"]
    rep = {"file": mp4}
    pr = probe(mp4)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next(s for s in pr["streams"] if s["codec_type"] == "audio")
    num, den = map(int, v["r_frame_rate"].split("/"))
    rep["specs"] = {"video_codec": v["codec_name"], "profile": v.get("profile"), "pix_fmt": v["pix_fmt"],
                    "width": v["width"], "height": v["height"], "fps": num / den,
                    "audio_codec": a["codec_name"], "sample_rate": int(a["sample_rate"]), "channels": a["channels"],
                    "duration_s": float(pr["format"]["duration"])}
    s = rep["specs"]
    rep["specs_ok"] = (s["video_codec"] == "h264" and s["width"] == 1080 and s["height"] == 1920
                       and abs(s["fps"] - fps) < 1e-6 and s["sample_rate"] == 48000 and s["channels"] == 2
                       and s["duration_s"] <= 60.0)
    # --- audio events
    x = decode_audio(mp4)
    meas = beep_onsets(x, t_offset=t0)
    exp = np.array([e for e in events if t0 <= e < t1])
    errs = []
    for e in exp:
        j = np.argmin(np.abs(meas - e)) if len(meas) else None
        errs.append(float(meas[j] - e) if j is not None else None)
    rep["audio"] = {"expected_beeps": len(exp), "detected_beeps": int(len(meas)),
                    "onset_error_ms": [round(1000 * e, 2) for e in errs if e is not None]}
    rep["audio"]["max_abs_error_ms"] = max((abs(e) for e in rep["audio"]["onset_error_ms"]), default=None)
    rep["audio_ok"] = (len(meas) == len(exp) and rep["audio"]["max_abs_error_ms"] is not None
                       and rep["audio"]["max_abs_error_ms"] < 5.0)
    if control_mp4:
        xc = decode_audio(control_mp4)
        rep["control_detected_beeps"] = int(len(beep_onsets(xc, t_offset=t0)))
        rep["control_ok"] = rep["control_detected_beeps"] == 0
    # --- visual stimulus
    rep["trials"] = []
    ok = True
    for tr in plan["trials"]:
        st, en = tr["start"], tr["start"] + tr["frames"] / fps
        if st < t0 or en > t1:
            continue
        m = track_trial(plan, tr, mp4)
        entry = {"name": tr["name"], "av_side": tr["spec"]["av_side"], "beeps": tr["spec"]["beeps"]}
        for side in ("left", "right"):
            mm = m[side]
            e = mm["expected"]
            got = mm["measured_reversal_frames"]
            ferr = [min((abs(g - x) for g in got), default=99) for x in e]
            entry[side] = {"speed_rps": round(mm["speed_rps"], 4), "reversal_frame_errors": ferr,
                           "extra_reversals": max(0, len(got) - len(e))}
            ok &= max(ferr) <= 1 and abs(mm["speed_rps"] - tr["spec"]["av_speed_rps"]) < 0.01
        if tr["spec"]["beeps"]:
            av = tr["spec"]["av_side"]
            lags = []
            for fr in m[av]["measured_reversal_frames"]:
                tv = st + fr / fps
                j = np.argmin(np.abs(meas - tv)) if len(meas) else None
                if j is not None:
                    lags.append(round(1000 * (meas[j] - tv), 2))
            entry["beep_minus_visual_reversal_ms"] = lags
            ok &= all(abs(l) <= 1000 / fps + 1 for l in lags)
        rep["trials"].append(entry)
    rep["stimulus_ok"] = bool(ok)
    rep["flash"] = flash_check(mp4, W, H, fps)
    rep["loudness"] = loudness(mp4)
    rep["all_ok"] = bool(rep["specs_ok"] and rep["audio_ok"] and rep["stimulus_ok"] and rep["flash"]["pass"]
                         and rep.get("control_ok", True))
    return rep
