"""Episode 04 - "Los destellos fantasma" (sound-induced flash illusion, B2F1).

2.5D episode (no Blender): Pillow/NumPy pudu + parallax forest, composited
at 60 fps.  `frame(f)` returns one RGB uint8 frame; everything is a pure
function of time so frames can be rendered in parallel and re-rendered
deterministically.

Stimulus rules (see pudulab/illusions/sound_flash.py, docs/EP04_CIENCIA.md):
* exactly ONE physical flash per presentation: a small cream disk, 2 frames
  (33 ms), on the right of the fixation cross, drawn last and never altered
  in post-production;
* B2F1 presentations get two 3.5 kHz / 17 ms beeps 66 ms apart, the first
  one exactly at the flash onset; the control presentation (B0F1) is silent;
* in a +-0.6 s window around every flash nothing else on screen changes
  (static camera, no blinks, no caption changes, no fireflies) and the
  music is silent;
* 5 flashes in the whole video, >= 3.5 s apart, 0.2 % of the screen area.
"""

from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw

from pudulab.compositor import Captions, font, vignette
from pudulab.illusions.sound_flash import SIFITrial
from pudulab.toon import forest2d
from pudulab.toon.pudu2d import Pudu2D

EPISODE_ID = "ep04_destellos_fantasma"
TITLE = "Los destellos fantasma"
W, H, FPS = 1080, 1920, 60
DURATION = 48.5

FIX = (540, 800)  # fixation cross
FLASH = (920, 800)  # flash centre: 380 px right of fixation
FLASH_R = 30  # px radius
FLASH_RGB = (250, 242, 220)

TRIALS = [SIFITrial("prueba1", 14.0), SIFITrial("prueba2", 17.5), SIFITrial("prueba3", 21.0),
          SIFITrial("control_sin_sonido", 35.0, beeps=0), SIFITrial("control_con_sonido", 38.5)]
QUIET = 0.6  # s around each flash with no other change on screen / no music

# ------------------------------------------------------------- utilities ---


def ease(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def track(t, keys, default=0.0):
    """keys = [(time, value), ...]; smooth (eased) interpolation, held at ends."""
    if not keys:
        return default
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t < t1:
            if isinstance(v0, str):
                return v0
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0))
    return keys[-1][1]


def step(t, keys, default):
    v = default
    for k, val in keys:
        if t >= k:
            v = val
    return v


def near_flash(t, pad=QUIET):
    return any(abs(t - tr.onset_s) < pad for tr in TRIALS)


# --------------------------------------------------------------- timeline ---
# camera (horizontal parallax offset in px)
CAM = [(0, 0), (3.0, 0), (10.0, 420), (11.4, 260), (43.0, 260), (48.5, 330)]
# background brightness (experiment = dim, never black)
DIM = [(0, 1.0), (10.2, 1.0), (11.2, 0.32), (22.6, 0.32), (24.4, 0.8), (31.6, 0.8), (32.8, 0.32), (42.6, 0.32),
       (43.6, 1.0)]
PUDU_DIM = [(0, 1.0), (10.2, 1.0), (11.2, 0.62), (22.6, 0.62), (24.4, 1.0), (31.6, 1.0), (32.8, 0.62), (42.6, 0.62),
            (43.6, 1.0)]
# pudu screen placement: x, feet y, scale
PX = [(0, 540), (48.5, 540)]
PY = [(0, 1730), (3.0, 1730), (3.8, 1760), (10.2, 1760), (11.2, 1840), (22.6, 1840), (24.4, 1740), (31.6, 1740),
      (32.8, 1840), (42.6, 1840), (43.6, 1730)]
PS = [(0, 1.18), (3.0, 1.18), (3.8, 0.95), (10.2, 0.95), (11.2, 0.78), (22.6, 0.78), (24.4, 1.05), (31.6, 1.05),
      (32.8, 0.78), (42.6, 0.78), (43.6, 1.12)]
FIX_ON = [(11.0, 22.4), (32.6, 39.7)]


def pudu_params(t):
    """Acting: returns pudu2d parameters for time t."""
    p = dict(eye_open=1.0, look_x=0.0, look_y=0.0, cross=0.0, brow=0.0, worry=0.0, mouth="smile", mouth_open=0.0,
             ear=0.0, tilt=0.0, head_dy=0.0, squash=0.0, hoof=0.0, blush=0.0, dizzy=0.0)
    # idle breathing (very slow, frozen during the quiet windows)
    if not near_flash(t):
        p["squash"] = 0.012 * math.sin(2 * math.pi * t / 2.6)
    if t < 3.0:  # hook: surprise, cross-eyed at the firefly on its nose
        k = ease((t - 0.35) / 0.25)
        p.update(brow=k, mouth="o" if t > 0.4 else "smile", mouth_open=0.6 * k, ear=k, cross=0.9 * k, look_y=0.5 * k)
        p["squash"] += -0.06 * math.exp(-((t - 0.5) / 0.12) ** 2) + 0.04 * math.exp(-((t - 0.75) / 0.12) ** 2)
        if t > 2.3:  # eyes follow it flying off to the upper left
            k2 = ease((t - 2.3) / 0.4)
            p.update(cross=0.9 * (1 - k2), look_x=-k2, look_y=0.5 - 1.4 * k2, tilt=-8 * k2)
    elif t < 10.2:  # counting fireflies and getting it wrong
        targets = [(3.0, (-0.7, -0.6)), (4.6, (0.8, -0.8)), (5.6, (-0.2, -1.0)), (6.5, (0.9, -0.5)),
                   (7.3, (-0.8, -0.9)), (8.1, (0.0, 0.0))]
        lx = track(t, [(a, b[0]) for a, b in targets])
        ly = track(t, [(a, b[1]) for a, b in targets])
        p.update(look_x=lx, look_y=ly, tilt=10 * lx, brow=0.3, mouth="smile")
        for tc in (3.8, 4.8, 5.8, 6.6, 7.4):  # little nod on every count
            p["head_dy"] += 10 * math.exp(-((t - tc - 0.08) / 0.1) ** 2)
        if 8.1 <= t < 9.3:
            p.update(dizzy=1.0, mouth="open", mouth_open=0.4, tilt=9 * math.sin(2 * math.pi * 1.6 * t), brow=0.0)
        if t >= 9.3:
            p.update(mouth="flat", brow=-0.2, worry=0.6, look_x=-0.3, look_y=0.3)
    elif t < 22.6:  # experiment: watching the cross
        k = ease((t - 10.2) / 0.8)
        p.update(look_y=-0.9 * k, look_x=0.0, brow=0.4 * k, mouth="o", mouth_open=0.15, ear=0.5 * k)
    elif t < 31.6:  # how many flashes? two toes... or one?
        p.update(look_y=track(t, [(22.6, -0.9), (23.6, 0.0)]), brow=0.6, mouth="smile", ear=0.6)
        if t >= 25.8:
            p["hoof"] = track(t, [(25.8, 0.0), (26.6, 1.0), (30.4, 1.0), (31.3, 0.0)])
            p.update(mouth="grin", mouth_open=0.5, brow=0.9, look_x=-0.5, look_y=-0.4)
        if t >= 28.9:
            k = ease((t - 28.9) / 0.5)
            p.update(mouth="wavy", mouth_open=0.0, brow=0.2, worry=k, tilt=11 * k, look_x=-0.5 + 1.3 * k,
                     look_y=-0.4 - 0.4 * k, ear=0.6 - 1.0 * k)
    elif t < 43.0:  # control
        k = ease((t - 31.6) / 0.8)
        p.update(look_y=-0.9 * k, brow=0.3, mouth="flat", ear=0.2, worry=0.3)
        if t >= 39.9:
            p.update(look_y=-0.2, look_x=-0.4, brow=0.8, mouth="o", mouth_open=0.4)
    else:  # punchline
        k = ease((t - 43.0) / 0.4)
        p.update(brow=-1.0 * k, mouth="wavy", ear=-0.7 * k, blush=k, look_x=0.0, look_y=0.0)
        for ts in (43.55, 44.15):  # stomps
            p["squash"] += 0.07 * math.exp(-((t - ts) / 0.07) ** 2)
        if 43.9 < t < 46.3:
            p["mouth"] = "open"
            p["mouth_open"] = 0.35 + 0.3 * abs(math.sin(2 * math.pi * 3.2 * t))
        if t >= 46.3:  # watches the firefly leave, then gives up with a smile
            k2 = ease((t - 46.3) / 0.6)
            p.update(brow=-1 + 1.6 * k2, look_x=-0.9 * k2, look_y=-0.9 * k2, mouth="smile", blush=1 - 0.5 * k2,
                     ear=-0.7 + 1.0 * k2, tilt=8 * k2)
    # blinks (never inside the quiet windows)
    for tb in (1.9, 5.2, 9.9, 12.4, 15.9, 19.3, 23.2, 27.6, 33.6, 36.8, 41.2, 45.1, 47.6):
        if not near_flash(tb, QUIET + 0.15):
            d = abs(t - tb)
            if d < 0.09:
                p["eye_open"] = min(p["eye_open"], d / 0.09)
    return p


# --- fireflies: (path fn t -> (x_world, y), intensity fn) ------------------
def _ff_hook(t):
    if t >= 3.2:
        return None
    if t < 2.35:
        x, y = 540 + 6 * math.sin(2 * math.pi * 0.7 * t), 1300 + 8 * math.sin(2 * math.pi * 0.45 * t)
    else:
        k = ease((t - 2.35) / 0.8)
        x, y = 540 - 440 * k, 1300 - 900 * k - 150 * math.sin(math.pi * k)  # away from the flash spot
    return x, y, 0.75 + 0.25 * math.sin(2 * math.pi * t / 1.6), 9.0


def _ff_count(i, t):
    """Three fireflies drifting in the forest during 3-10 s; #0 fades out and
    back in elsewhere, so the pudu counts it twice."""
    spec = [  # world x (moves with mid-layer parallax), y, on, off
        (330, 1060, 3.4, 5.9), (820, 1180, 4.4, 10.3), (460, 1320, 5.4, 10.3), (980, 1020, 6.3, 10.3)]
    x0, y0, on, off = spec[i]
    if not (on <= t < off):
        return None
    a = min(1.0, (t - on) / 0.45, (off - t) / 0.45)
    x = x0 + 30 * math.sin(0.9 * t + i) - 0.4 * track(t, CAM)
    y = y0 + 22 * math.sin(1.3 * t + 2 * i)
    return x, y, a * (0.8 + 0.2 * math.sin(2 * math.pi * t / 1.9 + i)), 8.0


def _ff_punch(t):
    if not (43.2 <= t < 47.6):
        return None
    if t < 46.3:
        k = ease((t - 43.2) / 0.8)
        x, y = 760 - 20 * math.sin(1.7 * t), 1150 + 40 * math.sin(1.1 * t)
        return x, y, k * (0.8 + 0.2 * math.sin(2 * math.pi * t / 1.4)), 9.0
    k = ease((t - 46.3) / 1.2)
    return 760 - 480 * k, 1150 - 850 * k, 1 - k, 9.0  # leaves away from the flash spot


def fireflies(t):
    out = []
    for f in (_ff_hook(t), *(_ff_count(i, t) for i in range(4)), _ff_punch(t)):
        if f:
            out.append(f)
    return out


# --- speech bubbles ---------------------------------------------------------
BUBBLES = [(3.8, 4.7, "1"), (4.8, 5.7, "2"), (5.8, 6.5, "3"), (6.6, 7.3, "4"), (7.4, 8.1, "5…"),
           (8.1, 9.3, "¿¡7!?"), (26.6, 28.8, "¡2!"), (29.3, 31.4, "¿…1?")]

# --- captions -----------------------------------------------------------------


def captions():
    C = []

    def cap(start, end, text, y=0.1, size=0.05, style="title"):
        C.append({"start": start, "end": end, "text": text, "y": y, "size": size, "style": style})

    cap(0.0, 3.0, "¿Viste UNO o DOS?", y=0.09, size=0.062)
    cap(0.0, 3.0, "Sube el volumen", y=0.17, size=0.03, style="small")
    cap(3.2, 8.0, "Contar luciérnagas…\n¿fácil?", y=0.09, size=0.048)
    cap(8.4, 10.1, "(eran 4)", y=0.09, size=0.04, style="small")
    cap(10.4, 13.1, "EXPERIMENTO\nMira la cruz.\nLa luz aparece a un lado.", y=0.08, size=0.042)
    cap(12.9, 15.2, "Prueba 1 de 3", y=0.29, size=0.034, style="small")
    cap(16.3, 18.7, "Prueba 2 de 3", y=0.29, size=0.034, style="small")
    cap(19.8, 22.2, "Prueba 3 de 3", y=0.29, size=0.034, style="small")
    cap(23.0, 31.6, "¿Cuántos destellos\nviste?", y=0.09, size=0.056)
    cap(32.0, 34.1, "CONTROL\nla MISMA luz física", y=0.08, size=0.048)
    cap(34.0, 36.3, "SIN sonido", y=0.29, size=0.04)
    cap(37.3, 39.6, "CON 2 bips", y=0.29, size=0.04)
    cap(39.9, 42.9, "En pantalla hubo\nUN solo destello", y=0.09, size=0.05)
    cap(43.3, 46.6, "¡Me cobraron dos\nluciérnagas y había\nuna sola!", y=0.08, size=0.054)
    cap(46.6, 48.5, "Ilusión del destello inducido por sonido (B2F1)\nYang et al. (2026), Behav Brain Funct 22:48\n"
        "doi:10.1186/s12993-026-00344-y", y=0.2, size=0.02, style="small")
    cap(46.6, 48.5, "No todos la ven: en laboratorio,\n~1 de cada 5 ensayos", y=0.09, size=0.038)
    cap(0.0, DURATION, "NEXO NEUROLAB", y=0.035, size=0.016, style="brand")
    return C


# -------------------------------------------------------------- renderer ---
class Renderer:
    def __init__(self):
        self.forest = forest2d.Forest(W, H)
        self.pudu = Pudu2D(cache_size=32)
        self.caps = Captions(W, H, captions())
        self.vig = vignette(W, H)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.hypot(xx + 0.5 - FLASH[0], yy + 0.5 - FLASH[1])
        self.flash_a = np.clip(FLASH_R + 0.5 - d, 0, 1)[..., None]
        self.flash_box = (FLASH[1] - FLASH_R - 2, FLASH[1] + FLASH_R + 3, FLASH[0] - FLASH_R - 2, FLASH[0] + FLASH_R + 3)
        self.flash_frames = {f for tr in TRIALS for f in tr.flash_frames_list()}
        self.bubble_font = font(64, 800)
        self.diag = self._diagram()
        self._scaled = {}

    # -- pieces --
    def _bubble(self, text):
        f = self.bubble_font
        tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
        b = tmp.textbbox((0, 0), text, font=f)
        w, h = b[2] - b[0] + 60, b[3] - b[1] + 44
        im = Image.new("RGBA", (w + 8, h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([4, 4, w + 4, h + 4], 30, fill=(244, 232, 206, 245), outline=(30, 20, 14, 255), width=5)
        d.polygon([(w / 2 - 14, h + 2), (w / 2 + 14, h + 2), (w / 2 - 4, h + 34)], fill=(244, 232, 206, 245))
        d.line([(w / 2 - 14, h + 4), (w / 2 - 4, h + 34), (w / 2 + 14, h + 4)], fill=(30, 20, 14, 255), width=5)
        d.text((w / 2 + 4 - (b[0] + b[2]) / 2, 4 + 22 - b[1]), text, font=f, fill=(40, 26, 18))
        return np.asarray(im).astype(np.float32) / 255

    def _diagram(self):
        """Static 'what was physically emitted' chart (no motion, fades in)."""
        w, h = 940, 470
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 36, fill=(8, 30, 36, 235), outline=(64, 178, 170, 255), width=4)
        fl, fs = font(40, 800), font(30, 600)
        d.text((40, 30), "Lo que se emitió (una prueba):", font=fl, fill=(244, 232, 206))
        x0, cw = 250, 52  # one cell = one 60 fps frame (16.7 ms)
        d.text((40, 128), "LUZ", font=fl, fill=(255, 206, 110))
        for k in range(12):
            lit = k in (0, 1)
            d.rounded_rectangle([x0 + k * cw, 120, x0 + k * cw + cw - 8, 180], 8,
                                fill=(250, 242, 220) if lit else (24, 60, 66), outline=(64, 178, 170))
        d.text((40, 238), "SONIDO", font=fl, fill=(120, 226, 214))
        d.line([(x0, 262), (x0 + 12 * cw, 262)], fill=(64, 178, 170), width=3)
        for k, ms in enumerate((0, 66)):
            x = x0 + ms / (1000 / 60) * cw
            d.rounded_rectangle([x, 226, x + 17 / (1000 / 60) * cw, 298], 8, fill=(120, 226, 214))
            d.text((x - 6, 308), "bip", font=fs, fill=(120, 226, 214))
        for ms in (0, 66, 133, 200):
            x = x0 + ms / (1000 / 60) * cw
            d.text((x - (60 if ms == 200 else 10), 352), f"{ms} ms" if ms == 200 else f"{ms}", font=fs, fill=(170, 200, 196))
        d.text((40, 404), "1 destello (33 ms)  ·  2 bips (17 ms, cada 66 ms)", font=fs, fill=(244, 232, 206))
        return np.asarray(im).astype(np.float32) / 255

    def _pudu_layer(self, p, scale):
        s = round(scale, 3)
        key = (tuple(sorted((k, round(v, 3) if isinstance(v, float) else v) for k, v in p.items())), s)
        if key not in self._scaled:
            im, (ox, oy) = self.pudu.render(**p)
            if len(self._scaled) > 64:
                self._scaled.clear()
            w, h = max(1, int(im.width * s)), max(1, int(im.height * s))
            arr = np.asarray(im.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255
            self._scaled[key] = (arr, ox * s, oy * s)
        return self._scaled[key]

    @staticmethod
    def _over(img, arr, x, y, alpha=1.0, mul=1.0):
        h, w = arr.shape[:2]
        x, y = int(round(x)), int(round(y))
        X0, Y0, X1, Y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if X0 >= X1 or Y0 >= Y1:
            return
        sub = arr[Y0 - y:Y1 - y, X0 - x:X1 - x]
        a = sub[..., 3:4] * alpha
        img[Y0:Y1, X0:X1] = img[Y0:Y1, X0:X1] * (1 - a) + sub[..., :3] * mul * a

    # -- frame --
    def frame(self, f):
        t = f / FPS
        cam = track(t, CAM)
        img = self.forest.compose(cam) * track(t, DIM)
        p = pudu_params(t)
        arr, ox, oy = self._pudu_layer(p, track(t, PS))
        px, py = track(t, PX), track(t, PY)
        self._over(img, arr, px - ox, py - oy, mul=track(t, PUDU_DIM))
        for x, y, inten, r in fireflies(t):
            forest2d.glow(img, x, y, inten, r)
        img *= self.vig
        # fixation cross
        for a, b in FIX_ON:
            if a <= t < b:
                k = min(1.0, (t - a) / 0.4, (b - t) / 0.4)
                fx, fy = FIX
                img[fy - 3:fy + 3, fx - 18:fx + 18] = img[fy - 3:fy + 3, fx - 18:fx + 18] * (1 - k) + 0.85 * k
                img[fy - 18:fy + 18, fx - 3:fx + 3] = img[fy - 18:fy + 18, fx - 3:fx + 3] * (1 - k) + 0.85 * k
        # THE stimulus: one small disk, drawn last, full intensity on its frames only
        if f in self.flash_frames:
            y0, y1, x0, x1 = self.flash_box
            a = self.flash_a[y0:y1, x0:x1]
            img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - a) + a * (np.array(FLASH_RGB, np.float32) / 255)
        for a, b, text in BUBBLES:
            if a <= t < b:
                k = min(1.0, (t - a) / 0.15, (b - t) / 0.15)
                bub = self._bubble_cached(text)
                bx = px - bub.shape[1] / 2 + 150 * track(t, PS)
                by = py - 690 * track(t, PS) - bub.shape[0]
                self._over(img, bub, bx, by, alpha=k)
        if 39.9 <= t < 42.95:
            k = min(1.0, (t - 39.9) / 0.4, (42.95 - t) / 0.3)
            self._over(img, self.diag, (W - self.diag.shape[1]) / 2, 900, alpha=k)
        self.caps.draw(img, t)
        return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)

    def _bubble_cached(self, text):
        if not hasattr(self, "_bub"):
            self._bub = {}
        if text not in self._bub:
            self._bub[text] = self._bubble(text)
        return self._bub[text]


def plan():
    return {"episode": EPISODE_ID, "title": TITLE, "resolution": [W, H], "fps": FPS, "duration": DURATION,
            "fixation_px": FIX, "flash_px": FLASH, "flash_radius_px": FLASH_R, "flash_rgb": FLASH_RGB,
            "trials": [tr.to_json() for tr in TRIALS], "quiet_window_s": QUIET, "captions": captions()}


if __name__ == "__main__":  # quick stills
    import sys

    R = Renderer()
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for t in [float(x) for x in (sys.argv[2:] or ["1", "6", "14", "27", "30", "41", "44.5", "47"])]:
        Image.fromarray(R.frame(int(round(t * FPS)))).save(os.path.join(out, f"still_{t:05.1f}.jpg"), quality=88)
