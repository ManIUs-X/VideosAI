"""Stylised night forest for 2.5D episodes: pre-rendered parallax layers.

Palette (NEXO NEUROLAB): petrol blue, turquoise, warm yellow, cream.
Layers are drawn once (Pillow), stored as premultiplied float arrays and
composited per frame with a horizontal camera offset times a per-layer
parallax factor.  Deterministic (seeded).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

PETROL_TOP = (6, 28, 38)
PETROL = (14, 62, 72)
TURQ = (64, 178, 170)
WARM = (255, 206, 110)
CREAM = (244, 232, 206)


def _grad(h, w, stops):
    """Vertical gradient; stops = [(y_frac, rgb), ...]."""
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, w, 3), np.float32)
    fr = [s[0] for s in stops]
    for c in range(3):
        out[..., c] = np.interp(ys, fr, [s[1][c] / 255 for s in stops])[:, None]
    return out


def _to_layer(im):
    a = np.asarray(im).astype(np.float32) / 255.0
    rgb, al = a[..., :3], a[..., 3:4]
    return rgb * al, al  # premultiplied


class Forest:
    def __init__(self, W=1080, H=1920, margin=640, seed=3, horizon=0.66):
        self.W, self.H, self.margin = W, H, margin
        self.LW = W + margin
        rng = np.random.default_rng(seed)
        LW, hz = self.LW, int(H * horizon)
        self.horizon = hz
        # sky -------------------------------------------------------------
        sky = _grad(H, LW, [(0, PETROL_TOP), (0.45, (10, 46, 58)), (horizon, PETROL), (1, (8, 34, 40))])
        yy, xx = np.mgrid[0:H, 0:LW].astype(np.float32)
        mx, my = 780, 300
        r = np.hypot(xx - mx, yy - my)
        sky += (np.exp(-(r / 260) ** 2) * 0.22)[..., None] * np.array(TURQ, np.float32) / 255
        moon = np.clip(78.5 - r, 0, 1)[..., None]
        sky = sky * (1 - moon) + moon * np.array(CREAM, np.float32) / 255
        crater = np.clip(20.5 - np.hypot(xx - mx - 22, yy - my + 14), 0, 1) * 0.06
        sky -= crater[..., None]
        for _ in range(140):
            x, y = rng.uniform(0, LW), rng.uniform(0, H * 0.5)
            if math.hypot(x - mx, y - my) < 120:
                continue
            b = rng.uniform(0.25, 0.8)
            sky[int(y), int(x)] = np.maximum(sky[int(y), int(x)], b)
        self.sky = sky
        # far trees -------------------------------------------------------
        self.layers = []  # (premult rgb, alpha, parallax)
        self.layers.append(self._trees(rng, (22, 84, 90), (30, 104, 106), n=16, wmin=26, wmax=52, top=0.18, base=hz + 40,
                                       canopy=(70, 140), blur=3, fog=0.55, cy_range=(0.2, 0.3)) + (0.15,))
        self.layers.append(self._trees(rng, (12, 50, 58), (20, 70, 76), n=9, wmin=46, wmax=86, top=0.0, base=hz + 110,
                                       canopy=(90, 170), blur=1, fog=0.25, rim=True, cy_range=(-0.02, 0.07)) + (0.4,))
        self.layers.append(self._ground(rng) + (0.75,))
        self.layers.append(self._front(rng) + (1.15,))

    # -------------------------------------------------------------- layers --
    def _trees(self, rng, col, canopy_col, n, wmin, wmax, top, base, canopy, blur, fog, rim=False, cy_range=(0.2, 0.3)):
        LW, H = self.LW, self.H
        im = Image.new("RGBA", (LW, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        xs = np.sort(rng.uniform(-40, LW + 40, n))
        for x in xs:
            w = rng.uniform(wmin, wmax)
            d.polygon([(x - w / 2, base), (x + w / 2, base), (x + w * 0.36, H * top), (x - w * 0.36, H * top)],
                      fill=col + (255,))
            if rim:
                d.line([(x - w / 2 + 3, base), (x - w * 0.36 + 3, H * top)], fill=(48, 140, 140, 200), width=4)
            for _ in range(int(rng.integers(3, 6))):
                cr = rng.uniform(*canopy)
                cx = x + rng.uniform(-1.4, 1.4) * cr
                cy = H * rng.uniform(*cy_range)
                d.ellipse([cx - cr, cy - cr * 0.75, cx + cr, cy + cr * 0.75], fill=canopy_col + (255,))
                if rim:
                    d.arc([cx - cr, cy - cr * 0.75, cx + cr, cy + cr * 0.75], 160, 260, fill=(52, 150, 146, 220), width=5)
        if blur:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        rgb, a = _to_layer(im)
        # atmospheric fog: blend towards turquoise, stronger near the ground
        f = np.linspace(0, 1, H)[:, None, None] ** 2 * fog
        rgb = rgb * (1 - f) + a * f * np.array((40, 120, 122), np.float32) / 255
        return rgb, a

    def _ground(self, rng):
        LW, H, hz = self.LW, self.H, self.horizon
        im = Image.new("RGBA", (LW, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pts = [(0, H)] + [(x, hz + 70 + 18 * math.sin(x / 170) + 10 * math.sin(x / 53)) for x in range(0, LW + 20, 20)] + [(LW, H)]
        d.polygon(pts, fill=(10, 42, 46, 255))
        g = _grad(H, LW, [(0, (14, 56, 60)), (hz / H + 0.05, (14, 56, 60)), (1, (6, 24, 28))])
        mask = Image.new("L", (LW, H), 0)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        im = Image.fromarray((g * 255).astype(np.uint8)).convert("RGBA")
        im.putalpha(mask)
        d = ImageDraw.Draw(im)
        # soft path lit by the moon
        p = Image.new("L", (LW, H), 0)
        ImageDraw.Draw(p).ellipse([LW / 2 - 760, H * 0.82, LW / 2 + 760, H * 1.08], fill=110)
        p = p.filter(ImageFilter.GaussianBlur(60))
        im.paste(Image.new("RGBA", (LW, H), (34, 92, 92, 255)), (0, 0), ImageChops.multiply(p, mask))
        d = ImageDraw.Draw(im)
        # grass tufts, mushrooms (warm accents)
        for _ in range(90):
            x, y = rng.uniform(0, LW), rng.uniform(hz + 80, H)
            s = 6 + (y - hz) / (H - hz) * 22
            for k in range(3):
                a = -0.6 + 0.6 * k + rng.uniform(-0.2, 0.2)
                d.line([(x, y), (x + math.sin(a) * s, y - s * 1.6)], fill=(20, 86, 82, 255), width=max(2, int(s / 6)))
        for _ in range(9):
            x, y = rng.uniform(40, LW - 40), rng.uniform(hz + 120, hz + 300)
            s = rng.uniform(9, 16)
            d.rectangle([x - s * 0.18, y - s, x + s * 0.18, y], fill=(228, 214, 186, 255))
            d.pieslice([x - s * 0.8, y - s * 1.6, x + s * 0.8, y - s * 0.4], 180, 360, fill=WARM + (255,))
        rgb, a = _to_layer(im.filter(ImageFilter.GaussianBlur(0.8)))
        return rgb, a

    def _front(self, rng):
        LW, H = self.LW, self.H
        im = Image.new("RGBA", (LW, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for cx in np.arange(-60, LW + 200, 380) + rng.uniform(-60, 60, len(np.arange(-60, LW + 200, 380))):
            for k in range(7):
                a = math.radians(-70 + k * 23 + rng.uniform(-6, 6))
                L = rng.uniform(220, 330)
                bx, by = cx, H + 20
                pts = []
                for j in range(13):
                    t = j / 12
                    px = bx + math.sin(a) * L * t + math.sin(a) * 40 * t * t
                    py = by - math.cos(a) * L * t + 60 * t * t
                    pts.append((px, py))
                for j, (px, py) in enumerate(pts[1:], 1):
                    w = 26 * (1 - j / 13)
                    d.ellipse([px - w, py - w * 0.45, px + w, py + w * 0.45], fill=(4, 22, 26, 255))
                d.line(pts, fill=(4, 22, 26, 255), width=5)
        rgb, a = _to_layer(im.filter(ImageFilter.GaussianBlur(4)))
        return rgb, a

    # ------------------------------------------------------------- compose --
    def compose(self, cam_x=0.0):
        """Return float32 sRGB (H, W, 3) for a horizontal camera offset in px."""
        W = self.W
        x0 = int(round(self.margin / 2 + cam_x * 0.05))
        out = self.sky[:, x0:x0 + W].copy()
        for rgb, a, par in self.layers:
            x0 = int(round(self.margin / 2 + cam_x * par))
            x0 = min(max(0, x0), self.LW - W)
            out *= 1 - a[:, x0:x0 + W]
            out += rgb[:, x0:x0 + W]
        return out


def glow(img, x, y, intensity, radius=10.0, color=WARM):
    """Additive soft firefly glow (core + halo) into a float sRGB image."""
    if intensity <= 0:
        return
    H, W, _ = img.shape
    R = int(radius * 6)
    x0, x1, y0, y1 = max(0, int(x) - R), min(W, int(x) + R + 1), max(0, int(y) - R), min(H, int(y) + R + 1)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.hypot(xx - x, yy - y)
    a = (np.clip(radius * 0.45 - d + 0.5, 0, 1) * 0.9 + 0.55 * np.exp(-0.5 * (d / radius) ** 2)
         + 0.25 * np.exp(-0.5 * (d / (radius * 2.6)) ** 2)) * intensity
    col = np.array(color, np.float32) / 255
    img[y0:y1, x0:x1] += a[..., None] * col
