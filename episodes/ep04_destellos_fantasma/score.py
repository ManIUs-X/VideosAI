"""Original score + sound design for episode 04 (all synthesised).

Stems: 'beeps' (the stimulus only), 'music', 'sfx', 'ambience'.
Rules:
* the 3.5 kHz beep is the only 3.5 kHz event in the episode: every other
  stem is low-passed at 2.4 kHz (4th order) before mixing;
* music and sfx are silent within +-QUIET+0.4 s of every flash; ambience is
  ducked to 25 % there, so the beeps are the only transient sounds;
* beep level is moderate: peak about 6 dB below the music peaks.
"""

from __future__ import annotations

import math

import numpy as np

from pudulab import audio as A
from pudulab.illusions.sound_flash import beep

from .episode import DURATION, QUIET, TRIALS

D_MAJ = [62, 64, 66, 67, 69, 71, 73, 74, 76, 78, 79, 81]


def _box(n, a, b, ramp):
    t = np.arange(n) / A.SR
    return np.minimum(np.clip((t - (a - ramp)) / ramp, 0, 1), np.clip(((b + ramp) - t) / ramp, 0, 1))


def quiet_gain(n, pad, floor=0.0, ramp=0.25):
    g = np.ones(n)
    for tr in TRIALS:
        g *= 1 - (1 - floor) * _box(n, tr.onset_s - pad, tr.onset_s + 0.2 + pad, ramp)
    return g


def beeps():
    T = A.Track(DURATION)
    events = []
    for tr in TRIALS:
        for bt in tr.beep_times_s():
            T.add(beep(tr.beep_hz, tr.beep_ms, amp=0.22), bt)
            events.append(bt)
    return T.buf, sorted(events)


def music():
    T = A.Track(DURATION)
    # hook 0-3: mysterious pad + twinkle
    for m in (50, 57):
        T.add(A.pad(A.midi_hz(m), 3.0), 0.0, gain=0.07)
    for k, m in enumerate((74, 78, 81)):
        T.add(A.pluck(A.midi_hz(m), 1.2, bright=0.4), 0.45 + 0.18 * k, gain=0.09)
    # counting 3-10: playful pizzicato-like ostinato, 112 bpm
    beat = 60 / 112
    pat = [0, 4, 2, 4, 1, 4, 2, 5]
    t, i = 3.0, 0
    while t < 9.9:
        m = D_MAJ[pat[i % 8]] - 12
        T.add(A.pluck(A.midi_hz(m), 0.6, bright=0.3), t, gain=0.15, pan=-0.3 + 0.6 * (i % 2))
        if i % 4 == 0:
            T.add(A.bass(A.midi_hz(38 + (5 if (i // 8) % 2 else 0)), beat * 3.5), t, gain=0.2)
        t += beat / 2
        i += 1
    T.add(A.glide(700, 300, 0.9, amp=0.06) * (1 + 0.5 * np.sin(np.linspace(0, 50, int(0.9 * A.SR)))), 8.1)
    # experiment intro 10-11.4: suspended chord that dies away before the trials
    for m in (50, 55, 57, 62):
        T.add(A.pad(A.midi_hz(m), 1.2), 10.0, gain=0.045)
    # question 22.8-31.6: curious walking bass + plucks
    t, i = 23.0, 0
    while t < 31.4:
        T.add(A.bass(A.midi_hz([38, 42, 45, 43][i % 4]), 0.45), t, gain=0.16)
        if i % 2 == 0:
            T.add(A.pluck(A.midi_hz([74, 78, 76, 73][(i // 2) % 4]), 0.5, bright=0.3), t + 0.27, gain=0.08)
        t += 0.55
        i += 1
    T.add(A.glide(240, 520, 0.35, amp=0.10), 25.9)  # hoof "boing"
    T.add(A.glide(520, 330, 0.7, amp=0.08), 29.0)  # doubt
    # diagram 39.9-43: calm pad
    for m in (50, 57, 62, 66):
        T.add(A.pad(A.midi_hz(m), 2.6), 40.2, gain=0.04)
    # punchline 43-48.5: comic "wah-wah" + resolution
    for k, (f0, f1) in enumerate(((147, 139), (139, 131), (131, 110))):
        x = A.glide(f0, f1, 0.42, shape="lin", amp=0.16) * (1 + 0.6 * np.sin(np.linspace(0, 30, int(0.42 * A.SR))))
        T.add(x, 44.0 + 0.45 * k)
    t = 46.4
    for m in (62, 66, 69, 74):
        T.add(A.pluck(A.midi_hz(m), 1.6, bright=0.3), t, gain=0.1)
        t += 0.14
    for m in (50, 57, 62, 66):
        T.add(A.pad(A.midi_hz(m), 1.6), 46.9, gain=0.04)
    x = A.reverb(T.buf, 2.0, wet=0.28)
    return x * quiet_gain(T.n, QUIET + 0.4)[:, None]


def sfx():
    T = A.Track(DURATION)
    T.add(A.glide(620, 1150, 0.16, amp=0.10), 0.38)  # surprised "eep"
    T.add(A.whoosh(0.6, 3), 2.3, gain=0.08)  # firefly zips away
    for tc in (3.8, 4.8, 5.8, 6.6, 7.4):  # counting pips
        T.add(A.glide(800, 1250, 0.07, amp=0.08), tc)
    T.add(A.glide(1250, 600, 0.3, amp=0.07), 8.1)  # "¿7?"
    for ts in (43.55, 44.15):  # stomps
        T.add(A.thud(), ts - 0.02, gain=0.3)
    # "cha-ching" (cash register, kept below 2.4 kHz)
    for k, f in enumerate((1047, 1568)):
        T.add(A.pluck(f, 0.9, bright=0.0), 43.9 + 0.09 * k, gain=0.08)
    T.add(A.whoosh(0.7, 8), 46.3, gain=0.07)  # firefly leaves
    return T.buf * quiet_gain(T.n, QUIET + 0.4)[:, None]


def ambience():
    x = A.ambience(DURATION, seed=4) * 0.10
    T = A.Track(DURATION)
    for t in (5.4, 26.0, 47.2):  # distant owl (low, two notes)
        T.add(A.glide(420, 380, 0.35, amp=0.03), t, pan=-0.5)
        T.add(A.glide(400, 360, 0.5, amp=0.03), t + 0.45, pan=-0.5)
    x = x + T.buf
    return x * quiet_gain(len(x), QUIET + 0.6, floor=0.25, ramp=0.5)[:, None]


def build_stems():
    b, events = beeps()
    stems = {"beeps": b, "music": music(), "sfx": sfx(), "ambience": ambience()}
    for k in ("music", "sfx", "ambience"):  # keep 3.5 kHz exclusive to the stimulus
        stems[k] = np.stack([A.lowpass(A.lowpass(stems[k][:, c], 2400), 2400) for c in range(2)], 1)
    return stems, events
