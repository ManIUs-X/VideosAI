"""Episode 01 - "La luz que acelera" (beep-speed illusion).

Declarative plan: every downstream stage (Blender, compositor, audio,
verification) reads the dict returned by `build_plan()`.  Times in seconds.

World layout (metres, Z up): the forest path runs along +X; the clearing with
the fallen log is around (12, 0); a nalca (Gunnera) patch sits at (11.0, 1.0), front-left of the stage.
"""

from __future__ import annotations

import numpy as np

from pudulab.illusions import beep_speed as bs

EPISODE_ID = "ep01_beep_speed"
TITLE = "La luz que acelera"
FPS = 60  # output / stimulus frame rate
RENDER_FPS = 30  # 3D background frame rate (each 3D frame shown twice)
DURATION = 54.5

# --------------------------------------------------------------------------
# Stimulus segments.  All test trials use the paper's medium speed (0.25 rps)
# and physically IDENTICAL speeds for both lights (v_ratio = 1.0).
# --------------------------------------------------------------------------
TRIALS = [
    # name, start, av_side, seed, center_y, role
    ("hook", 0.0, "left", 11, 0.25, "hook"),
    ("T1a", 15.0, "left", 21, 0.06, "test"),
    ("T1b", 21.5, "left", 22, 0.06, "test"),
    ("T2a", 32.0, "right", 31, 0.06, "test"),
    ("T2b", 38.0, "right", 32, 0.06, "test"),
    ("reveal", 43.0, "right", 31, 0.06, "control"),  # silent replay of T2a
]

CHASE_START, CHASE_END = 3.0, 12.0


def trial_specs():
    out = []
    for name, start, side, seed, cy, role in TRIALS:
        spec = bs.BeepSpeedTrial(name=name, av_side=side, seed=seed, center_y=cy, fps=FPS,
                                 av_start_dir=1 if seed % 2 else -1, v_start_dir=-1 if seed % 2 else 1)
        if role == "control":
            spec = bs.control_of(spec)
            spec.name = name
        out.append((spec, start, role))
    return out


# --------------------------------------------------------------- cameras ---
def _cam(t, pos, target, lens):
    return {"t": t, "pos": list(map(float, pos)), "target": list(map(float, target)), "lens": lens}


def pudu_x_chase(t):
    """Pudu runs along the path during the chase (m)."""
    u = np.clip((t - CHASE_START) / (CHASE_END - CHASE_START), 0, 1)
    return -8.0 + 19.2 * u


def shots():
    hook = {"name": "hook", "start": 0.0, "end": 3.0, "static_during_stimulus": False,
            "keys": [_cam(0.0, (12.2, -1.3, 0.36), (12.0, 0.0, 0.44), 38),
                     _cam(3.0, (12.15, -1.08, 0.37), (12.0, 0.0, 0.45), 38)]}
    est = {"name": "establish", "start": 3.0, "end": 5.5,
           "keys": [_cam(3.0, (-10.5, -6.0, 3.4), (-6.0, 0.0, 1.2), 30),
                    _cam(5.5, (-8.0, -5.0, 1.5), (-3.5, 0.0, 0.7), 30)]}
    track_keys = []
    for t in np.arange(5.5, 12.01, 0.5):
        x = pudu_x_chase(t)
        track_keys.append(_cam(t, (x + 0.3, -3.3, 0.62), (x + 0.45, 0.0, 0.5), 26))
    track = {"name": "track", "start": 5.5, "end": 12.0, "keys": track_keys}
    stage_cam = ((12.22, -1.1, 0.5), (12.0, 3.0, 0.86), 30)
    stage = {"name": "stage", "start": 12.0, "end": 46.0,
             "keys": [_cam(12.0, (12.4, -1.55, 0.55), (12.0, 3.0, 0.86), 30),
                      _cam(14.4, *stage_cam), _cam(46.0, *stage_cam)]}
    fall = {"name": "fall", "start": 46.0, "end": 50.0,
            "keys": [_cam(46.0, (13.3, -1.6, 0.75), (11.7, 0.45, 0.3), 30),
                     _cam(50.0, (13.1, -1.4, 0.68), (11.5, 0.5, 0.28), 30)]}
    end = {"name": "end", "start": 50.0, "end": DURATION,
           "keys": [_cam(50.0, (11.1, -0.85, 0.44), (11.0, 0.62, 0.4), 36),
                    _cam(DURATION, (11.09, -0.62, 0.45), (11.0, 0.62, 0.41), 36)]}
    return [hook, est, track, stage, fall, end]


# ----------------------------------------------------------------- pudu ----
def pudu_track():
    """Root keys: t, x, y, heading (deg, 0 = facing +X, 90 = facing +Y)."""
    keys = [{"t": 0.0, "x": 12.0, "y": 0.0, "heading": -90.0},
            {"t": 2.99, "x": 12.0, "y": 0.0, "heading": -90.0}]
    for t in np.arange(3.0, 12.01, 0.25):
        keys.append({"t": float(t), "x": float(pudu_x_chase(t)), "y": 0.0, "heading": 0.0})
    keys += [{"t": 12.0, "x": 12.0, "y": 0.0, "heading": 90.0},
             {"t": 24.8, "x": 12.0, "y": 0.0, "heading": 90.0},
             {"t": 26.0, "x": 11.85, "y": 0.25, "heading": 100.0},  # hops toward the left light
             {"t": 29.5, "x": 12.0, "y": 0.0, "heading": 90.0},
             {"t": 46.6, "x": 12.0, "y": 0.0, "heading": 90.0},
             {"t": 47.6, "x": 11.55, "y": 0.45, "heading": 90.0},  # tumbles into the nalcas
             {"t": 49.99, "x": 11.5, "y": 0.5, "heading": 90.0},
             {"t": 50.0, "x": 11.0, "y": 0.62, "heading": -90.0},  # end shot: in the nalcas
             {"t": DURATION, "x": 11.0, "y": 0.62, "heading": -90.0}]
    return keys


def pudu_actions():
    """Body performance.  'look' targets: 'light:L', 'light:R', 'lights',
    'camera', 'chase' or an [x,y,z] point.  During every stimulus window the
    pudu only breathes/blinks (no motion locked to the beeps)."""
    return [
        {"type": "idle", "start": 0.0, "end": 3.0},
        {"type": "look", "start": 0.0, "end": 3.0, "target": "lights"},
        {"type": "ears_up", "start": 0.2, "end": 2.8},
        {"type": "run", "start": 3.0, "end": 12.0, "stride_hz": 3.2},
        {"type": "look", "start": 3.0, "end": 12.0, "target": "chase"},
        {"type": "idle", "start": 12.0, "end": 46.0},
        {"type": "surprise", "start": 12.6, "end": 13.4},
        {"type": "look", "start": 12.0, "end": 18.4, "target": "lights"},
        {"type": "look", "start": 18.4, "end": 21.3, "target": "light:L"},
        {"type": "nod", "start": 19.6, "end": 20.8},
        {"type": "look", "start": 21.3, "end": 24.6, "target": "lights"},
        {"type": "hop", "start": 24.8, "end": 26.0},
        {"type": "hop", "start": 26.6, "end": 27.6},
        {"type": "look", "start": 24.6, "end": 30.0, "target": "light:L"},
        {"type": "tail_wag", "start": 24.6, "end": 29.5},
        {"type": "look", "start": 30.0, "end": 35.2, "target": "lights"},
        {"type": "look", "start": 35.2, "end": 36.0, "target": "light:R"},
        {"type": "look", "start": 36.0, "end": 36.8, "target": "light:L"},
        {"type": "look", "start": 36.8, "end": 37.6, "target": "light:R"},
        {"type": "tilt", "start": 36.0, "end": 37.9},
        {"type": "look", "start": 37.6, "end": 46.0, "target": "lights"},
        {"type": "shake", "start": 41.1, "end": 42.0},
        {"type": "surprise", "start": 45.9, "end": 46.6},
        {"type": "fall", "start": 46.6, "end": 50.0},
        {"type": "pop_up", "start": 50.0, "end": 51.0},
        {"type": "look", "start": 50.0, "end": 51.6, "target": "light:L"},
        {"type": "look", "start": 51.6, "end": DURATION, "target": "camera"},
        {"type": "tilt", "start": 52.0, "end": DURATION},
        {"type": "idle", "start": 50.0, "end": DURATION},
    ]


# -------------------------------------------------------------- captions ---
def captions():
    C = []

    def cap(start, end, text, y=0.14, size=0.042, style="title"):
        C.append({"start": start, "end": end, "text": text, "y": y, "size": size, "style": style})

    cap(0.0, 3.0, "¿Cuál luz va más rápido?", y=0.07, size=0.044)
    cap(0.0, 3.0, "Activa el sonido", y=0.73, size=0.03, style="small")
    cap(3.3, 7.4, "Bosque valdiviano, sur de Chile", y=0.13, size=0.04)
    cap(7.6, 11.8, "Una luz que cambia de velocidad…\n¿o no?", y=0.13, size=0.042)
    cap(12.3, 14.6, "PRUEBA 1\nMira las dos luces", y=0.12, size=0.045)
    cap(18.2, 21.3, "¿Cuál fue más rápida?", y=0.12, size=0.045)
    cap(19.4, 21.3, "El pudú elige: IZQUIERDA", y=0.72, size=0.036, style="small")
    cap(21.4, 24.6, "Otra vez", y=0.12, size=0.04)
    cap(24.8, 29.8, "¡Clarísimo! La izquierda\nes la veloz", y=0.12, size=0.042)
    cap(30.0, 32.0, "PRUEBA 2\nEl sonido cambia de lado", y=0.12, size=0.045)
    cap(35.1, 37.9, "¿¡Ahora la derecha!?", y=0.12, size=0.045)
    cap(38.0, 41.0, "Otra vez", y=0.12, size=0.04)
    cap(41.1, 42.9, "REVELACIÓN", y=0.12, size=0.055)
    cap(43.0, 46.0, "Sin sonido. Misma trayectoria.", y=0.12, size=0.04)
    cap(46.2, 50.0, "Ambas luces van SIEMPRE a 0,25 vueltas/s.\nEl «bip» en cada giro hace que una\nPAREZCA más rápida (≈5–14 % en laboratorio).",
        y=0.11, size=0.031)
    cap(50.3, DURATION, "¿Cuál te pareció más rápida\nen la Prueba 1?\nComenta: IZQ o DER", y=0.12, size=0.042)
    cap(50.3, DURATION, "Ilusión beep-speed · Merz et al. (2026)\nAtten Percept Psychophys · doi:10.3758/s13414-025-03211-6",
        y=0.75, size=0.019, style="small")
    cap(0.0, DURATION, "NEXO NEUROLAB", y=0.035, size=0.016, style="brand")
    return C


def overlays():
    """Extra graphic overlays drawn by the compositor."""
    return [
        {"type": "fixation", "start": 14.5, "end": 15.0},
        {"type": "fixation", "start": 21.1, "end": 21.5},
        {"type": "fixation", "start": 31.5, "end": 32.0},
        {"type": "fixation", "start": 37.6, "end": 38.0},
        {"type": "speed_readout", "start": 43.0, "end": 46.0, "text": "0,25 vueltas/s"},
    ]


# ----------------------------------------------------------- assemble ------
def build_plan(t0=0.0, t1=DURATION):
    trials = []
    for spec, start, role in trial_specs():
        res = bs.generate(spec)
        check = bs.verify(res)
        trials.append({"name": spec.name, "start": start, "role": role, "check": check, **res.to_json()})
    chase = bs.LinearChase(duration_s=CHASE_END - CHASE_START, fps=FPS, seed=5).generate()
    chase["start"] = CHASE_START
    # Light world position: ahead of the pudu, zig-zagging vertically.
    xs = np.array(chase["forward"]) + pudu_x_chase(CHASE_START) + 0.95
    chase["world"] = [[float(x), 0.0, float(0.62 + z)] for x, z in zip(xs, chase["zig"])]
    return {
        "episode": EPISODE_ID,
        "title": TITLE,
        "fps": FPS,
        "render_fps": RENDER_FPS,
        "duration": DURATION,
        "range": [t0, t1],
        "resolution": [1080, 1920],
        "reference": bs.PAPER,
        "trials": trials,
        "chase": chase,
        "shots": shots(),
        "pudu_track": pudu_track(),
        "pudu_actions": pudu_actions(),
        "captions": captions(),
        "overlays": overlays(),
        "light_style": {"core_radius": 0.0075, "halo_sigma": 0.022, "color": [1.0, 0.86, 0.55],
                        "fade_s": 0.35, "dim_between": 0.55},
        "lights_appear": {"hook": 0.0, "stage": 12.6},
        # Depth (m from camera) at which the 3D illumination lights are placed
        # behind the screen-space stimulus, per shot.
        "light_depth": {"hook": 1.2, "stage": 3.9},
    }
