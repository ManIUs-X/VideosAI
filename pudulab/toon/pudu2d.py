"""2.5D cut-out pudu (NEXO NEUROLAB house style), drawn with Pillow.

Big head, expressive eyes, compact body, soft brown fur, round ears, short
spike antlers.  Every frame is drawn from a small set of pose/expression
parameters (see DEFAULT), supersampled 2x and down-filtered, with a cool
turquoise rim light (moon, upper left) and warm-brown core shading so the
flat shapes read as volumes.  Re-usable across episodes.

Local coordinates: 1 unit = 1 output pixel at scale 1, origin between the
front hooves on the ground, +y down (Pillow convention, so the head is at
negative y).
"""

from __future__ import annotations

import math
from collections import OrderedDict

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 2  # supersampling
FUR = (139, 90, 55)
FUR_D = (92, 57, 35)
FUR_L = (184, 132, 88)
CREAM = (240, 222, 190)
NOSE = (38, 26, 24)
HOOF = (50, 35, 30)
EAR_IN = (222, 166, 146)
ANTLER = (218, 200, 162)
RIM = (120, 226, 214)
IRIS = (78, 46, 24)
INK = (44, 28, 20)
BLUSH = (240, 128, 116)
SCLERA = (252, 248, 238)

DEFAULT = dict(
    eye_open=1.0,  # 0 closed .. 1 open
    look_x=0.0, look_y=0.0,  # pupils, -1..1
    cross=0.0,  # 0..1 cross-eyed (looking at something on the nose)
    brow=0.0,  # -1 angry .. +1 raised (surprise)
    worry=0.0,  # 0..1 inner brow ends up
    mouth="smile",  # smile | o | flat | grin | frown | wavy | open
    mouth_open=0.0,
    ear=0.0,  # -1 droop .. +1 perked
    tilt=0.0,  # head roll in degrees (+ = clockwise on screen)
    head_dy=0.0,
    squash=0.0,  # body squash (+) / stretch (-)
    hoof=0.0,  # 0..1 raise the (viewer-left) front leg to show its two toes
    blush=0.0,
    dizzy=0.0,  # 0..1 spiral eyes
    rim=1.0,
)

W_LOC, H_LOC, OX, OY = 760, 840, 380, 800  # local canvas (1x) and origin


def _ell(d, cx, cy, rx, ry, fill):
    d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S], fill=fill)


def _rot_ellipse_poly(cx, cy, rx, ry, ang_deg, n=48):
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append(((cx + x * ca - y * sa) * S, (cy + x * sa + y * ca) * S))
    return pts


class Canvas:
    """RGBA supersampled canvas; parts are painted through masks."""

    def __init__(self, w, h, ox, oy):
        self.w, self.h, self.ox, self.oy = w, h, ox, oy
        self.im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))

    def mask(self):
        m = Image.new("L", self.im.size, 0)
        return m, ImageDraw.Draw(m)

    def paint(self, m, color, shade=0.32, rim=0.4, light=(-1, -1), soft=6, rim_w=4, shade_w=16):
        """Fill mask with color, darker core shading away from the light and a
        turquoise rim on the lit edge."""
        bb = m.getbbox()
        if not bb:
            return
        pad = (shade_w + soft) * S + 4
        x0, y0 = max(0, bb[0] - pad), max(0, bb[1] - pad)
        x1, y1 = min(self.im.width, bb[2] + pad), min(self.im.height, bb[3] + pad)
        mc = m.crop((x0, y0, x1, y1))
        base = Image.new("RGBA", mc.size, color + (255,))
        layer = Image.new("RGBA", mc.size, (0, 0, 0, 0))
        layer.paste(base, (0, 0), mc)
        lx, ly = light
        if shade > 0:
            sh = ImageChops.subtract(mc, ImageChops.offset(mc, int(lx * shade_w * S), int(ly * shade_w * S)))
            sh = sh.filter(ImageFilter.GaussianBlur(soft * S))
            sh = ImageChops.multiply(sh, mc).point(lambda v: int(v * shade))
            dark = Image.new("RGBA", mc.size, tuple(int(c * 0.55) for c in color) + (255,))
            layer = Image.composite(dark, layer, sh)
            layer.putalpha(mc)
        if rim > 0:
            rm = ImageChops.subtract(mc, ImageChops.offset(mc, int(-lx * rim_w * S), int(-ly * rim_w * S)))
            rm = rm.filter(ImageFilter.GaussianBlur(2.5 * S))
            rm = ImageChops.multiply(rm, mc).point(lambda v: int(v * rim))
            rl = Image.new("RGBA", mc.size, RIM + (255,))
            a = layer.getchannel("A")
            layer = Image.composite(rl, layer, rm)
            layer.putalpha(a)
        self.im.alpha_composite(layer, (x0, y0))

    def flat(self, m, color, alpha=1.0):
        bb = m.getbbox()
        if not bb:
            return
        mc = m.crop(bb)
        if alpha < 1:
            mc = mc.point(lambda v: int(v * alpha))
        layer = Image.new("RGBA", mc.size, color + (255,))
        layer.putalpha(mc)
        self.im.alpha_composite(layer, bb[:2])


class Pudu2D:
    def __init__(self, cache_size=64):
        self.cache = OrderedDict()
        self.cache_size = cache_size

    # ------------------------------------------------------------- public --
    def render(self, **kw):
        """Return (RGBA image at 1x, (origin_x, origin_y)) for these params."""
        p = dict(DEFAULT)
        p.update(kw)
        # quantise first, then draw from the quantised values: the output is a
        # pure function of the key, independent of cache history
        p = {k: round(v, 3) if isinstance(v, float) else v for k, v in p.items()}
        key = tuple(sorted(p.items()))
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        im = self._draw(p).resize((W_LOC, H_LOC), Image.LANCZOS)
        out = (im, (OX, OY))
        self.cache[key] = out
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return out

    # ------------------------------------------------------------ drawing --
    def _draw(self, p):
        c = Canvas(W_LOC, H_LOC, OX, OY)
        X = lambda x: OX + x  # noqa: E731
        Y = lambda y: OY + y  # noqa: E731
        sq = p["squash"]
        # ground contact shadow
        m, d = c.mask()
        _ell(d, X(0), Y(4), 150, 18, 255)
        c.flat(m.filter(ImageFilter.GaussianBlur(8 * S)), (0, 0, 0), 0.45)
        # back legs
        for sx in (-1, 1):
            m, d = c.mask()
            d.rounded_rectangle([X(sx * 78 - 13) * S, Y(-110) * S, X(sx * 78 + 13) * S, Y(-6) * S], 12 * S, fill=255)
            c.paint(m, FUR_D, rim=0.3)
            self._hoof(c, X(sx * 78), Y(-4), 14, 0.0, dark=True)
        # body
        m, d = c.mask()
        _ell(d, X(0), Y(-152 + 30 * sq), 120 * (1 + 0.5 * sq), 100 * (1 - sq), 255)
        c.paint(m, FUR, shade_w=26, soft=14)
        m, d = c.mask()
        _ell(d, X(0), Y(-128 + 30 * sq), 62, 56 * (1 - sq), 255)
        c.paint(m, FUR_L, shade=0.2, rim=0, soft=10)
        # front legs (viewer-left one can be raised)
        self._leg(c, X(48), Y(0), 0.0)
        if p["hoof"] < 0.02:
            self._leg(c, X(-48), Y(0), 0.0)
        # head
        head = self._head(p)
        hx, hy = X(0), Y(-218 + 18 * sq + p["head_dy"])  # neck pivot
        hr = head.rotate(-p["tilt"], resample=Image.BICUBIC, center=(head.width / 2, head.height * 0.78))
        c.im.alpha_composite(hr, (int(hx * S - hr.width / 2), int(hy * S - hr.height * 0.78)))
        if p["hoof"] >= 0.02:
            self._raised_leg(c, X(-56), Y(-150 + 30 * sq), p["hoof"])
        return c.im

    def _hoof(self, c, x, y, w, spread, dark=False, big=1.0):
        """Cloven hoof: two rounded toes ("dos dedos")."""
        m, d = c.mask()
        g = 2.5 + spread * 9
        for sx in (-1, 1):
            cx = x + sx * (w * 0.5 + g) * big * 0.5
            d.rounded_rectangle([(cx - w * 0.5 * big) * S, (y - 15 * big) * S, (cx + w * 0.5 * big) * S, (y + 3) * S],
                                7 * big * S, fill=255)
        c.paint(m, HOOF, shade=0.2, rim=0.35 if not dark else 0.15, rim_w=3)

    def _leg(self, c, x, y, _):
        m, d = c.mask()
        d.rounded_rectangle([(x - 16) * S, (y - 118) * S, (x + 16) * S, (y - 8) * S], 14 * S, fill=255)
        c.paint(m, FUR, rim=0.45, shade_w=10)
        self._hoof(c, x, y - 4, 16, 0.0)

    def _raised_leg(self, c, px, py, k):
        th = math.radians(125 * _ease(k))  # from straight down, swinging out and up
        L = 118
        ex, ey = px - L * math.sin(th), py + L * math.cos(th)
        m, d = c.mask()
        d.line([px * S, py * S, ex * S, ey * S], fill=255, width=34 * S)
        _ell(d, px, py, 16, 16, 255)
        _ell(d, ex, ey, 16, 16, 255)
        c.flat(m.filter(ImageFilter.MaxFilter(7)), INK, 0.8)  # outline separates it from the body
        c.paint(m, FUR, rim=0.5, shade_w=10)
        # hoof seen from the front when raised: two spread toes ("dos dedos")
        big = 1.0 + 1.2 * _ease(k)
        spread = _ease(max(0.0, (k - 0.55) / 0.45))
        ux, uy = -math.sin(th), math.cos(th)  # along the leg
        nx, ny = math.cos(th), math.sin(th)  # across the leg
        for sx in (-1, 1):
            m, d = c.mask()
            off = (6 + 6 * spread) * big
            cx = ex + ux * 10 * big + nx * sx * off
            cy = ey + uy * 10 * big + ny * sx * off
            d.polygon(_rot_ellipse_poly(cx, cy, 9 * big, 16 * big, math.degrees(th) + sx * 14 * spread), fill=255)
            c.paint(m, HOOF, shade=0.25, rim=0.5, rim_w=3, shade_w=5, soft=3)

    def _head(self, p):
        HW, HH = 440, 400
        h = Canvas(HW, HH, HW // 2, 0)
        cx, cy = HW / 2, 210  # head centre in head canvas; neck pivot at 0.78*HH = 312
        ear = p["ear"]
        # antlers (behind)
        for sx in (-1, 1):
            m, d = h.mask()
            bx, by = cx + sx * 44, cy - 92
            a = math.radians(sx * 12)
            tip = (bx + 58 * math.sin(a), by - 58 * math.cos(a))
            d.polygon([((bx - 9) * S, by * S), ((bx + 9) * S, by * S), (tip[0] * S, tip[1] * S)], fill=255)
            h.paint(m, ANTLER, shade=0.25, rim=0.4, rim_w=3, shade_w=5, soft=2)
        # ears (behind)
        for sx in (-1, 1):
            ang = sx * (22 - 22 * ear)
            ex, ey = cx + sx * 140, cy - 62 + 14 * max(0, -ear)
            m, d = h.mask()
            d.polygon(_rot_ellipse_poly(ex, ey, 62, 36, ang), fill=255)
            h.paint(m, FUR, shade_w=10, soft=5)
            m, d = h.mask()
            d.polygon(_rot_ellipse_poly(ex + sx * 6, ey + 2, 42, 22, ang), fill=255)
            h.paint(m, EAR_IN, shade=0.25, rim=0, soft=4, shade_w=6)
        # skull + cheeks
        m, d = h.mask()
        _ell(d, cx, cy, 140, 118, 255)
        _ell(d, cx, cy + 34, 122, 88, 255)
        h.paint(m, FUR, shade_w=24, soft=14)
        # tuft
        m, d = h.mask()
        for k, (dx, ln) in enumerate(((-14, 26), (0, 34), (14, 24))):
            d.polygon([((cx + dx - 10) * S, (cy - 108) * S), ((cx + dx + 10) * S, (cy - 108) * S),
                       ((cx + dx * 1.6) * S, (cy - 108 - ln) * S)], fill=255)
        h.paint(m, FUR_D, shade=0, rim=0.5, rim_w=3)
        # muzzle
        m, d = h.mask()
        _ell(d, cx, cy + 62, 66, 48, 255)
        h.paint(m, CREAM, shade=0.18, rim=0, shade_w=10, soft=8)
        # blush
        if p["blush"] > 0:
            for sx in (-1, 1):
                m, d = h.mask()
                _ell(d, cx + sx * 96, cy + 48, 24, 13, 255)
                h.flat(m.filter(ImageFilter.GaussianBlur(5 * S)), BLUSH, 0.6 * p["blush"])
        # nose
        m, d = h.mask()
        d.rounded_rectangle([(cx - 24) * S, (cy + 30) * S, (cx + 24) * S, (cy + 56) * S], 13 * S, fill=255)
        h.paint(m, NOSE, shade=0, rim=0.25, rim_w=3)
        m, d = h.mask()
        _ell(d, cx - 8, cy + 36, 7, 4, 255)
        h.flat(m, (255, 255, 255), 0.7)
        self._mouth(h, cx, cy + 74, p)
        for sx in (-1, 1):
            self._eye(h, cx + sx * 56, cy - 22, sx, p)
            self._brow(h, cx + sx * 56, cy - 78, sx, p)
        return h.im

    def _eye(self, h, ex, ey, sx, p):
        rx, ry = 34, 40
        m, d = h.mask()
        _ell(d, ex, ey, rx, ry, 255)
        e = Image.new("RGBA", h.im.size, (0, 0, 0, 0))
        de = ImageDraw.Draw(e)
        _ell(de, ex, ey, rx, ry, SCLERA + (255,))
        if p["dizzy"] > 0.5:
            pts = []
            for k in range(60):
                t = k / 59 * 4 * math.pi
                r = 2 + 24 * k / 59
                pts.append(((ex + r * math.cos(t * sx)) * S, (ey + r * math.sin(t)) * S))
            de.line(pts, fill=IRIS + (255,), width=5 * S)
        else:
            ix = ex + 11 * p["look_x"] - sx * 12 * p["cross"]
            iy = ey + 12 * p["look_y"] + 3
            _ell(de, ix, iy, 25, 27, IRIS + (255,))
            _ell(de, ix, iy, 15, 16, (16, 10, 8, 255))
            _ell(de, ix - 8, iy - 10, 8, 8, (255, 255, 255, 255))
            _ell(de, ix + 8, iy + 8, 3.5, 3.5, (255, 255, 255, 230))
        # eyelid
        lid = 1 - p["eye_open"]
        if lid > 0.01:
            ly = ey - ry + 2 * ry * lid
            de.rectangle([(ex - rx - 2) * S, (ey - ry - 4) * S, (ex + rx + 2) * S, ly * S], fill=FUR + (255,))
            de.line([(ex - rx) * S, ly * S, (ex + rx) * S, ly * S], fill=INK + (255,), width=4 * S)
        a = ImageChops.multiply(e.getchannel("A"), m)
        e.putalpha(a)
        h.im.alpha_composite(e)
        # outline
        o = Image.new("RGBA", h.im.size, (0, 0, 0, 0))
        ImageDraw.Draw(o).ellipse([(ex - rx) * S, (ey - ry) * S, (ex + rx) * S, (ey + ry) * S], outline=INK + (255,),
                                  width=4 * S)
        h.im.alpha_composite(o)

    def _brow(self, h, bx, by, sx, p):
        br, wo = p["brow"], p["worry"]
        y = by - 14 * max(0, br) + 6 * max(0, -br)
        inner = 10 * max(0, -br) - 12 * wo  # inner end down (angry) / up (worry)
        x_in, x_out = bx - sx * 26, bx + sx * 24
        m, d = h.mask()
        d.line([x_in * S, (y + inner) * S, bx * S, (y - 3) * S, x_out * S, (y + 2 - 4 * wo) * S], fill=255,
               width=10 * S, joint="curve")
        for (x, yy) in ((x_in, y + inner), (x_out, y + 2 - 4 * wo)):
            _ell(d, x, yy, 5, 5, 255)
        h.flat(m, INK)

    def _mouth(self, h, mx, my, p):
        kind, op = p["mouth"], p["mouth_open"]
        m, d = h.mask()
        w = 9 * S
        if kind == "o":
            _ell(d, mx, my + 6, 10 + 6 * op, 12 + 8 * op, 255)
            h.flat(m, INK)
            return
        if kind in ("open", "grin"):
            _ell(d, mx, my, 30, 6 + 22 * max(op, 0.3), 255)
            d.rectangle([(mx - 34) * S, (my - 30) * S, (mx + 34) * S, my * S], fill=0)
            h.flat(m, INK)
            m2, d2 = h.mask()
            _ell(d2, mx, my + 6 + 14 * max(op, 0.3), 16, 9, 255)
            h.flat(ImageChops.multiply(m2, m), (214, 96, 96))
            return
        if kind == "smile":
            pts = [(mx - 26 + 52 * k / 20, my + 10 * math.sin(math.pi * k / 20)) for k in range(21)]
        elif kind == "frown":
            pts = [(mx - 22 + 44 * k / 20, my + 10 - 10 * math.sin(math.pi * k / 20)) for k in range(21)]
        elif kind == "wavy":
            pts = [(mx - 28 + 56 * k / 30, my + 6 + 5 * math.sin(3 * math.pi * k / 30)) for k in range(31)]
        else:  # flat
            pts = [(mx - 18, my + 4), (mx + 18, my + 4)]
        d.line([(x * S, y * S) for x, y in pts], fill=255, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):
            _ell(d, x, y, 4.5, 4.5, 255)
        h.flat(m, INK)


def _ease(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)
