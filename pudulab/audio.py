"""Procedural, original audio: stimulus beeps, score, ambience and foley.

Everything is synthesised from code (no samples), stereo float32 at 48 kHz.
Stimulus beeps are written to a dedicated stem so the control version can be
produced by simply omitting that stem.
"""

from __future__ import annotations

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000


def _t(n):
    return np.arange(n) / SR


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


class Track:
    def __init__(self, duration_s: float):
        self.n = int(round(duration_s * SR))
        self.buf = np.zeros((self.n, 2), np.float64)

    def add(self, x, start_s, gain=1.0, pan=0.0):
        """Add mono (N,) or stereo (N,2) signal; constant-power pan in [-1,1]."""
        i0 = int(round(start_s * SR))
        if x.ndim == 1:
            a = (pan + 1) * np.pi / 4
            x = np.stack([x * np.cos(a), x * np.sin(a)], 1) * np.sqrt(2)
        i1 = min(self.n, i0 + len(x))
        if i1 <= max(i0, 0):
            return
        s = max(0, -i0)
        self.buf[max(i0, 0):i1] += gain * x[s:i1 - i0]


# --------------------------------------------------------------- stimulus ---
def beep(hz=440.0, ms=68.0, ramp_ms=5.0, amp=0.5):
    """Pure tone burst. The paper specifies 440 Hz / 68 ms; the 5 ms raised
    cosine on/off ramps are our addition to avoid speaker clicks."""
    n = int(round(ms / 1000 * SR))
    x = np.sin(2 * np.pi * hz * _t(n))
    r = int(round(ramp_ms / 1000 * SR))
    env = np.ones(n)
    w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r))
    env[:r] = w
    env[-r:] = w[::-1]
    return amp * x * env


# ------------------------------------------------------------ instruments ---
def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    ns = max(0, n - na - nd)
    env = np.concatenate([np.linspace(0, 1, na, endpoint=False), np.linspace(1, s, nd, endpoint=False), np.full(ns, s)])[:n]
    tail = s * np.exp(-np.arange(nr) / (nr / 5 + 1))
    return np.concatenate([env, tail])


def pluck(hz, dur=0.9, bright=1.0):
    """Kalimba-like: inharmonic partials with fast exponential decay."""
    n = int(dur * SR)
    t = _t(n)
    x = np.sin(2 * np.pi * hz * t) * np.exp(-t * 4)
    x += 0.35 * bright * np.sin(2 * np.pi * hz * 5.4 * t) * np.exp(-t * 18)
    x += 0.15 * np.sin(2 * np.pi * hz * 2 * t) * np.exp(-t * 8)
    att = np.minimum(1, t / 0.003)
    return x * att


def pad(hz, dur, detune=0.006, harmonics=10):
    n = int((dur + 0.8) * SR)
    t = _t(n)
    x = np.zeros(n)
    for dt in (-detune, 0, detune):
        f = hz * (1 + dt)
        for k in range(1, harmonics + 1):
            x += np.sin(2 * np.pi * f * k * t + k * 1.3 + dt * 900) / (k ** 1.6)
    x /= 3
    env = adsr(int(dur * SR), a=0.6, d=0.3, s=0.8, r=0.8)
    env = np.pad(env, (0, max(0, n - len(env))))[:n]
    return x * env


def bass(hz, dur):
    n = int(dur * SR)
    t = _t(n)
    x = np.sin(2 * np.pi * hz * t) + 0.25 * np.sin(4 * np.pi * hz * t)
    return x * adsr(n, a=0.01, d=0.15, s=0.6, r=0.15)[:n]


def glide(f0, f1, dur, shape="exp", amp=1.0):
    n = int(dur * SR)
    k = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** k if shape == "exp" else f0 + (f1 - f0) * k
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.sin(np.pi * k) ** 0.5
    return amp * np.sin(ph) * env


def noise(n, seed=0, color="pink"):
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    if color == "white":
        return w
    if color == "brown":
        b = np.cumsum(w)
        b = signal.detrend(b)
        return b / (np.abs(b).max() + 1e-9)
    # pink via Voss-McCartney approximation (filter)
    b, a = [0.049922035, -0.095993537, 0.050612699, -0.004408786], [1, -2.494956002, 2.017265875, -0.522189400]
    p = signal.lfilter(b, a, w)
    return p / (np.abs(p).max() + 1e-9)


def bandpass(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lowpass(x, hz, order=2):
    sos = signal.butter(order, hz, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def hoof(seed=0):
    n = int(0.05 * SR)
    x = bandpass(noise(n, seed, "white"), 700, 2600) * np.exp(-_t(n) * 90)
    x += 0.6 * np.sin(2 * np.pi * 140 * _t(n)) * np.exp(-_t(n) * 60)
    return x


def rustle(dur=0.8, seed=0):
    n = int(dur * SR)
    x = bandpass(noise(n, seed, "white"), 1500, 7000)
    rng = np.random.default_rng(seed)
    grains = np.convolve((rng.random(n) < 0.004).astype(float), np.hanning(400), "same")
    return x * grains * np.exp(-_t(n) * 2.5)


def thud():
    n = int(0.35 * SR)
    t = _t(n)
    return np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 20)) * t) * np.exp(-t * 12)


def whoosh(dur=0.5, seed=0):
    n = int(dur * SR)
    x = noise(n, seed, "white")
    k = np.linspace(0, 1, n)
    lo, hi = bandpass(x, 250, 900), bandpass(x, 1500, 5000)
    mix = np.sin(np.pi * k)
    return (lo * (1 - mix) + hi * mix) * np.sin(np.pi * k) ** 2


def ambience(duration_s, seed=0):
    """Night forest bed: brown-noise wind with slow gusts, stereo-decorrelated."""
    n = int(duration_s * SR)
    out = np.zeros((n, 2))
    for ch in range(2):
        w = lowpass(noise(n, seed + ch, "brown"), 500)
        gust = 0.6 + 0.4 * np.sin(2 * np.pi * _t(n) * (0.07 + 0.02 * ch) + ch)
        out[:, ch] = w * gust
    return out / (np.abs(out).max() + 1e-9)


def reverb(x, seconds=2.2, wet=0.25, seed=7):
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal((n, 2)) * np.exp(-_t(n) * 6.9 / seconds)[:, None]
    ir[:, 0] = lowpass(ir[:, 0], 6000)
    ir[:, 1] = lowpass(ir[:, 1], 6000)
    ir /= np.sqrt((ir ** 2).sum(0))
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)
    return (1 - wet) * x + wet * y


def gain_curve(n, points):
    """Piecewise-linear gain automation: points = [(t_s, gain), ...]."""
    ts = np.array([p[0] for p in points]) * SR
    gs = np.array([p[1] for p in points])
    return np.interp(np.arange(n), ts, gs)


def write_wav(path, x, peak=None):
    x = np.asarray(x, np.float64)
    if peak is not None:
        m = np.abs(x).max()
        if m > 0:
            x = x * (peak / m)
    x = np.clip(x, -1, 1)
    wavfile.write(path, SR, (x * 32767).astype(np.int16))
