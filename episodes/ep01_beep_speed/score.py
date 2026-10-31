"""Original score + sound design for episode 01 (all synthesised).

Stems: 'beeps' (stimulus only), 'music', 'sfx', 'ambience'.  During test
trials the music is silent and the ambience is ducked, so the only salient
sound is the paradigm's 440 Hz beep.  No sound other than the beep is ever
scheduled within +-250 ms of a trial reversal.
"""

from __future__ import annotations

import math

import numpy as np

from pudulab import audio as A

D_DORIAN = [62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81]


def trial_windows(plan, pad=0.25):
    return [(tr["start"] - pad, tr["start"] + tr["frames"] / plan["fps"] + pad) for tr in plan["trials"]
            if tr["role"] != "hook"]


def beeps(plan):
    tr = A.Track(plan["duration"])
    b = A.beep(440.0, 68.0, amp=0.5)
    events = []
    for t in plan["trials"]:
        for bt in t["beep_times_s"]:
            tr.add(b, t["start"] + bt)
            events.append(t["start"] + bt)
    ch = plan["chase"]
    for bt in ch["beep_times_s"]:
        tr.add(b, ch["start"] + bt, gain=0.8)
        events.append(ch["start"] + bt)
    return tr.buf, sorted(events)


def music(plan):
    T = A.Track(plan["duration"])
    rng = np.random.default_rng(4)
    # Hook: low mysterious drone only (no rhythmic notes competing with beeps).
    T.add(A.pad(A.midi_hz(38), 3.2), 0.0, gain=0.10)
    T.add(A.pad(A.midi_hz(45), 3.2), 0.0, gain=0.06)
    # Chase 3-12 s: playful kalimba ostinato at 120 bpm in D dorian.
    beat = 0.5
    motif = [0, 2, 4, 2, 5, 4, 2, 1, 0, 2, 4, 6, 5, 4, 2, 4]
    t = 3.0
    i = 0
    while t < 11.8:
        deg = motif[i % len(motif)]
        T.add(A.pluck(A.midi_hz(D_DORIAN[deg]), 0.8), t, gain=0.16, pan=-0.3 + 0.6 * (i % 2))
        if i % 2 == 0:
            T.add(A.pluck(A.midi_hz(D_DORIAN[deg] + 12), 0.5, bright=0.6), t + 0.25, gain=0.05, pan=0.4)
        if i % 4 == 0:
            T.add(A.bass(A.midi_hz(38 + (0 if (i // 8) % 2 == 0 else 5)), 1.8), t, gain=0.22)
        t += beat / 2 if 5.5 < t < 11 else beat
        i += 1
    for root, start, dur in ((50, 3.0, 4.5), (55, 7.5, 4.6)):
        for m in (root, root + 3, root + 7):
            T.add(A.pad(A.midi_hz(m), dur), start, gain=0.035)
    # Arrival 12-14.5: suspended chord, fades before the first trial.
    for m in (50, 55, 57, 62):
        T.add(A.pad(A.midi_hz(m), 1.9), 12.0, gain=0.04)
    T.add(A.pluck(A.midi_hz(74), 1.5), 12.6, gain=0.12)
    T.add(A.pluck(A.midi_hz(81), 1.5), 12.75, gain=0.08)
    # Question motif after T1a (18.2): rising two notes.
    for k, m in enumerate((69, 74, 76)):
        T.add(A.pluck(A.midi_hz(m), 0.9), 18.3 + 0.28 * k, gain=0.13)
    T.add(A.pluck(A.midi_hz(81), 1.2), 19.6, gain=0.12)  # the pudu decides
    # Happy hop 24.8-29.8: bouncy major-ish arpeggio.
    t = 24.8
    for k in range(16):
        m = [62, 66, 69, 74, 69, 66, 64, 67][k % 8]
        T.add(A.pluck(A.midi_hz(m + 12), 0.6), t, gain=0.12, pan=0.25 * math.sin(k))
        t += 0.3
    T.add(A.pad(A.midi_hz(50), 4.6), 24.8, gain=0.05)
    T.add(A.pad(A.midi_hz(54), 4.6), 24.8, gain=0.04)
    # Prueba 2 card 30-31.5: short call.
    T.add(A.pluck(A.midi_hz(69), 0.9), 30.1, gain=0.12)
    T.add(A.pluck(A.midi_hz(70), 0.9), 30.45, gain=0.12)
    # Confusion 35.1-37.9: descending chromatic + tilt.
    for k, m in enumerate((76, 75, 74, 73, 72)):
        T.add(A.pluck(A.midi_hz(m), 0.7), 35.25 + 0.45 * k, gain=0.11, pan=(-1) ** k * 0.5)
    # Dizzy wobble 41.1-42.
    T.add(A.glide(600, 380, 0.9, amp=0.05) * (1 + 0.5 * np.sin(np.linspace(0, 40, int(0.9 * A.SR)))), 41.1)
    # Reveal sting 41.1 + drone during silent replay (no rhythm, no beeps).
    for m in (38, 45, 50, 53):
        T.add(A.pad(A.midi_hz(m), 4.6), 41.2, gain=0.045)
    # Comedy: slide whistle on the fall + resolution.
    T.add(A.glide(1400, 300, 0.9, amp=0.07), 46.7)
    for m in (62, 65, 69, 72):
        T.add(A.pluck(A.midi_hz(m), 1.6), 48.4 + 0.12 * (m - 62) / 3, gain=0.1)
    # Outro 50-54.5: theme restated, ending on an open question chord.
    t = 50.2
    for deg in (0, 2, 4, 6, 5, 4, 2, 4):
        T.add(A.pluck(A.midi_hz(D_DORIAN[deg]), 0.9), t, gain=0.14)
        t += 0.3
    for m in (50, 57, 62, 64, 67):
        T.add(A.pad(A.midi_hz(m), 2.6), 51.6, gain=0.035)
    T.add(A.pluck(A.midi_hz(76), 2.0), 52.8, gain=0.12)
    T.add(A.pluck(A.midi_hz(79), 2.0), 53.1, gain=0.1)
    x = A.reverb(T.buf, 2.4, wet=0.3)
    # Hard silence in trial windows (except hook, which only has a drone).
    g = np.ones(T.n)
    for a, b in trial_windows(plan):
        g *= 1 - _box(T.n, a, b, 0.15)
    return x * g[:, None]


def _box(n, a, b, ramp):
    t = np.arange(n) / A.SR
    up = np.clip((t - (a - ramp)) / ramp, 0, 1)
    down = np.clip(((b + ramp) - t) / ramp, 0, 1)
    return np.minimum(up, down)


def sfx(plan):
    T = A.Track(plan["duration"])
    # Hoof-steps: 4 contacts per stride during the run (skip 250 ms around beeps
    # so the beep stays the only sharp event at a reversal).
    run = next(a for a in plan["pudu_actions"] if a["type"] == "run")
    chase_beeps = [plan["chase"]["start"] + b for b in plan["chase"]["beep_times_s"]]
    hz = run["stride_hz"]
    k = 0
    t = run["start"] + 0.1
    while t < run["end"] - 0.1:
        for off in (0.0, 0.06, 0.5 / hz, 0.5 / hz + 0.06):
            tt = t + off
            if all(abs(tt - b) > 0.12 for b in chase_beeps):
                T.add(A.hoof(k), tt, gain=0.10, pan=-0.2 + 0.4 * (k % 2))
            k += 1
        t += 1 / hz
    for t0 in (3.0, 5.5):  # whooshes on the camera moves
        T.add(A.whoosh(0.6, int(t0 * 10)), t0 - 0.2, gain=0.12)
    T.add(A.glide(500, 1100, 0.15, amp=0.12), 12.6)  # surprise "pip"
    for a in plan["pudu_actions"]:
        if a["type"] == "hop":
            T.add(A.hoof(7), a["end"] - 0.02, gain=0.12)
            T.add(A.rustle(0.3, 3), a["end"] - 0.02, gain=0.05)
    T.add(A.glide(500, 1100, 0.15, amp=0.12), 45.9)
    T.add(A.thud(), 47.55, gain=0.35)
    T.add(A.rustle(1.2, 9), 47.5, gain=0.25, pan=-0.3)
    T.add(A.rustle(0.6, 11), 50.0, gain=0.2)
    T.add(A.glide(300, 900, 0.12, amp=0.12), 50.2)  # pop!
    return T.buf


def ambience(plan):
    x = A.ambience(plan["duration"], seed=2) * 0.12
    # occasional distant bird (chucao-like two-note call) outside trials
    T = A.Track(plan["duration"])
    for t in (4.2, 9.7, 26.5, 52.0):
        T.add(A.glide(1400, 900, 0.12, amp=0.04), t, pan=0.6)
        T.add(A.glide(1300, 800, 0.16, amp=0.035), t + 0.16, pan=0.6)
    x = x + T.buf
    g = np.ones(len(x))
    for a, b in trial_windows(plan, pad=0.4):
        g *= 1 - 0.8 * _box(len(x), a, b, 0.4)
    return x * g[:, None]


def build_stems(plan):
    b, events = beeps(plan)
    return {"beeps": b, "music": music(plan), "sfx": sfx(plan), "ambience": ambience(plan)}, events
