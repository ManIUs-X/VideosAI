"""Final 2D compositing at the output frame rate (60 fps).

Inputs: 3D layer frames (every 2nd frame), the plan, projections.json.
Adds: stimulus lights (frame-exact, constant luminance), captions, fixation
cross, speed read-outs, vignette.  Streams raw RGB to FFmpeg.
"""

from __future__ import annotations

import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import lights as L

FONT = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Baloo2.ttf")


def font(px, weight=800):
    f = ImageFont.truetype(FONT, px)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


class GlowSprite:
    """Additive light: solid core + gaussian halo, sub-pixel positioned."""

    def __init__(self, H, style):
        self.core = style["core_radius"] * H
        self.sigma = style["halo_sigma"] * H
        self.color = np.array(style["color"], np.float32)
        self.R = int(self.sigma * 2.2 * 4.5 + self.core + 2)  # covers the wide halo tail

    def draw(self, img, cx, cy, intensity):
        if intensity <= 0:
            return
        h, w, _ = img.shape
        x0, x1 = int(cx) - self.R, int(cx) + self.R + 1
        y0, y1 = int(cy) - self.R, int(cy) + self.R + 1
        X0, X1, Y0, Y1 = max(0, x0), min(w, x1), max(0, y0), min(h, y1)
        if X0 >= X1 or Y0 >= Y1:
            return
        yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(np.float32)
        d = np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
        core = np.clip(self.core + 0.5 - d, 0, 1)  # anti-aliased disc
        halo = 0.55 * np.exp(-0.5 * (d / self.sigma) ** 2) + 0.25 * np.exp(-0.5 * (d / (self.sigma * 2.2)) ** 2)
        a = (core * 1.0 + halo) * intensity
        patch = img[Y0:Y1, X0:X1]
        white = np.array([1.0, 0.98, 0.93], np.float32)
        add = a[..., None] * self.color * 0.85 + (core * intensity)[..., None] * white * 0.6
        patch += add


class Captions:
    def __init__(self, W, H, caps):
        self.W, self.H = W, H
        self.items = []
        for c in caps:
            self.items.append((c, self._render(c)))

    def _render(self, c):
        px = int(c["size"] * self.H)
        style = c["style"]
        lines = c["text"].split("\n")
        tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
        while True:  # shrink until the widest line fits 86 % of the frame width
            f = font(px, 800 if style != "small" else 600)
            boxes = [tmp.textbbox((0, 0), ln, font=f) for ln in lines]
            lw = max(b[2] - b[0] for b in boxes)
            if lw <= 0.86 * self.W or px <= 12:
                break
            px -= 2
        spacing = int(px * 0.12)
        lh = px + spacing
        pad = int(px * 0.5)
        Wc, Hc = lw + 2 * pad, lh * len(lines) + 2 * pad
        im = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        fill = (255, 246, 225, 255) if style != "brand" else (255, 215, 140, 200)
        stroke = max(2, px // 9)
        for i, ln in enumerate(lines):
            b = tmp.textbbox((0, 0), ln, font=f)
            x = (Wc - (b[2] - b[0])) // 2 - b[0]
            y = pad + i * lh
            d.text((x, y), ln, font=f, fill=fill, stroke_width=stroke, stroke_fill=(20, 12, 6, 255))
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        shadow.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(px / 6)).point(lambda v: int(v * 0.6)))
        out = Image.alpha_composite(shadow, im)
        arr = np.asarray(out).astype(np.float32) / 255.0
        return arr

    def draw(self, img, t):
        for c, arr in self.items:
            if not (c["start"] <= t < c["end"]):
                continue
            fade = min(1.0, (t - c["start"]) / 0.2, (c["end"] - t) / 0.2)
            if c["start"] == 0.0:
                fade = min(1.0, (c["end"] - t) / 0.2)
            h, w, _ = arr.shape
            x0 = (self.W - w) // 2
            y0 = int(c["y"] * self.H)
            X0, Y0 = max(0, x0), max(0, y0)
            X1, Y1 = min(self.W, x0 + w), min(self.H, y0 + h)
            sub = arr[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
            a = sub[..., 3:4] * fade
            img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - a) + sub[..., :3] * a


def vignette(W, H):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    return (1 - 0.35 * np.clip(r - 0.55, 0, 1) ** 1.5)[..., None].astype(np.float32)


def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0, None)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def tonemap_add(bg_srgb, add_linear):
    """Additive light in linear space, soft-clipped, back to sRGB."""
    lin = srgb_to_linear(bg_srgb) + add_linear
    lin = lin / (1 + np.maximum(lin - 0.8, 0) * 0.8)
    return linear_to_srgb(lin)


def render(plan, render_dir, out_path, crf=17, preview_png_dir=None, log=print):
    W, H = plan["resolution"]
    fps = plan["fps"]
    t0, t1 = plan["range"]
    f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
    proj = {}
    pj = os.path.join(render_dir, "projections.json")
    if os.path.exists(pj):
        proj = {int(k): v for k, v in json.load(open(pj))["chase"].items()}
    glow = GlowSprite(H, plan["light_style"])
    caps = Captions(W, H, plan["captions"])
    vig = vignette(W, H)
    fix_font = font(int(0.04 * H), 700)
    read_font = font(int(0.024 * H), 700)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", out_path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    cache_key, cache = None, None
    stim_log = []
    for f in range(f0, f1):
        t = f / fps
        src = f - ((f - f0) % 2)
        if src != cache_key:
            p = os.path.join(render_dir, "3d", f"{src:06d}.png")
            if not os.path.exists(p):
                p = os.path.join(render_dir, "3d", f"{src + 1:06d}.png")
            im = Image.open(p).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            cache = np.asarray(im).astype(np.float32) / 255.0
            cache_key = src
        add = np.zeros((H, W, 3), np.float32)
        for s in L.stimulus_state(plan, f):
            u, v = L.to_uv(plan, s["x"], s["y"])
            glow.draw(add, u * W, (1 - v) * H, s["intensity"])
            stim_log.append((f, s["side"], u * W, (1 - v) * H, s["intensity"], s["active"]))
        if f in proj:
            u, v, depth = proj[f]
            glow.draw(add, u * W, (1 - v) * H, 1.0)
        img = cache.copy()
        nz = np.nonzero(add.max(2) > 1e-4)
        if len(nz[0]):
            y0, y1, x0, x1 = nz[0].min(), nz[0].max() + 1, nz[1].min(), nz[1].max() + 1
            img[y0:y1, x0:x1] = tonemap_add(cache[y0:y1, x0:x1], add[y0:y1, x0:x1])
        img *= vig
        img = overlays(plan, img, t, W, H, fix_font, read_font)
        caps.draw(img, t)
        frame = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
        ff.stdin.write(frame.tobytes())
        if preview_png_dir and (f - f0) % 60 == 0:
            os.makedirs(preview_png_dir, exist_ok=True)
            Image.fromarray(frame).save(os.path.join(preview_png_dir, f"t{t:05.1f}.jpg"), quality=88)
        if (f - f0) % 300 == 0:
            log(f"  composited t={t:.1f}s")
    ff.stdin.close()
    ff.wait()
    if ff.returncode:
        raise RuntimeError("ffmpeg failed")
    return stim_log


def overlays(plan, img, t, W, H, fix_font, read_font):
    for o in plan["overlays"]:
        if not (o["start"] <= t < o["end"]):
            continue
        pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(pil)
        if o["type"] == "fixation":
            cy = (0.5 - 0.06) * H
            d.text((W / 2, cy), "+", font=fix_font, fill=(255, 240, 210), anchor="mm")
        elif o["type"] == "speed_readout":
            tr = next(tr for tr in plan["trials"] if tr["start"] <= o["start"] < tr["start"] + tr["frames"] / plan["fps"] + 1e-6)
            for side in ("left", "right"):
                x = (0.5 + tr["spec"]["center_offset_x"] * (H / W) * (-1 if side == "left" else 1)) * W
                y = (0.5 - tr["spec"]["center_y"] + tr["spec"]["radius"] + 0.035) * H
                d.text((x, y), o["text"], font=read_font, fill=(255, 235, 190), anchor="mm",
                       stroke_width=3, stroke_fill=(20, 12, 6))
        img = np.asarray(pil).astype(np.float32) / 255.0
    return img
