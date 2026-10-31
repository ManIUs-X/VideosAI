"""Beep-speed illusion stimulus generator.

Reference paradigm (circular motion variant):
    Merz, S., Sommerfeld, J., Frings, C., & Meyerhoff, H. S. (2026).
    Not proportional after all: Investigating speed perception with the
    beep-speed illusion. Attention, Perception, & Psychophysics, 88(2).
    https://doi.org/10.3758/s13414-025-03211-6  (open access, PMC12795862)

Original linear-motion paradigm:
    Meyerhoff, H. S., Gehrer, N. A., Merz, S., & Frings, C. (2022).
    The beep-speed illusion: Non-spatial tones increase perceived speed of
    visual objects in a forced-choice paradigm. Cognition, 219, 104978.

Paradigm parameters reproduced here (Merz et al., 2026, Exp. 1/2):
    * two dots on invisible circular paths, side by side
    * audiovisual (AV) object speed 0.25 rps (Exp. 2 also 1/24 and 1.5 rps)
    * visual-only (V) object speed = ratio * AV speed,
      ratios 0.2, 0.6, 0.76, 0.92, 1.08, 1.24, 1.4, 1.8
    * 3 s presentation; in every 1000 ms interval each object reverses its
      direction exactly once, never in the first or last 100 ms
    * AV and V reversals at least 200 ms apart, so a beep never coincides
      with a V reversal
    * 440 Hz sine beep, 68 ms, simultaneous with every AV reversal,
      non-spatial (identical on both channels)

All geometry is in "height" units (as PsychoPy's `height` unit): 1.0 equals
the frame height, origin at the frame centre, +y up.  Time is quantised to the
video frame grid so a reversal and its beep onset share one exact timestamp.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

import numpy as np

PAPER = {
    "doi": "10.3758/s13414-025-03211-6",
    "citation": "Merz, Sommerfeld, Frings & Meyerhoff (2026). Not proportional "
    "after all: Investigating speed perception with the beep-speed illusion. "
    "Atten Percept Psychophys 88(2).",
    "speeds_rps": [1 / 24, 0.25, 1.5],
    "ratios": [0.2, 0.6, 0.76, 0.92, 1.08, 1.24, 1.4, 1.8],
    # Reported PSE (V speed / AV speed judged equal) and 50-75% JND.
    "results": {
        "exp1_0.25rps": {"pse": 1.05, "jnd": 0.27, "d": 0.57},
        "exp2_1/24rps": {"pse": 1.14, "jnd": 0.59, "d": 1.00},
        "exp2_0.25rps": {"pse": 1.13, "jnd": 0.32, "d": 0.90},
        "exp2_1.5rps": {"pse": 1.02, "jnd": 0.14, "d": 0.69},
    },
    "paper_geometry_height_units": {"radius": 0.1, "center_offset_x": 0.2, "dot_diameter": 0.0125},
}


@dataclass
class BeepSpeedTrial:
    name: str = "trial"
    duration_s: float = 3.0
    fps: int = 60
    av_speed_rps: float = 0.25
    v_ratio: float = 1.0
    av_side: str = "left"  # which object carries the beeps
    av_start_dir: int = 1  # +1 counter-clockwise, -1 clockwise
    v_start_dir: int = -1
    interval_s: float = 1.0
    edge_margin_s: float = 0.1
    min_separation_s: float = 0.2
    beeps: bool = True  # False -> control with identical trajectories
    beep_hz: float = 440.0
    beep_ms: float = 68.0
    # Geometry, adapted to a 9:16 frame (paper: r=0.1, offset 0.2 in 16:9).
    radius: float = 0.07
    center_offset_x: float = 0.13
    center_y: float = 0.08
    seed: int = 0
    start_angles: tuple | None = None


@dataclass
class TrialResult:
    spec: BeepSpeedTrial
    frames: int
    times: np.ndarray
    angle: dict = field(default_factory=dict)  # side -> rad per frame
    xy: dict = field(default_factory=dict)  # side -> (N,2) height units
    reversal_frames: dict = field(default_factory=dict)  # side -> list[int]
    beep_times: list = field(default_factory=list)  # seconds from trial start

    def to_json(self) -> dict:
        return {
            "spec": asdict(self.spec),
            "frames": self.frames,
            "reversal_frames": self.reversal_frames,
            "beep_times_s": self.beep_times,
            "xy": {k: v.round(6).tolist() for k, v in self.xy.items()},
        }


def _schedule(rng, spec: BeepSpeedTrial):
    """Frame indices of AV and V reversals obeying the paper's constraints."""
    fps = spec.fps
    n_int = int(round(spec.duration_s / spec.interval_s))
    lo = spec.edge_margin_s
    hi = spec.interval_s - spec.edge_margin_s
    # Frames strictly inside (lo, hi) of every interval.
    for _ in range(10000):
        av, v = [], []
        for k in range(n_int):
            base = k * spec.interval_s
            av.append(int(round((base + rng.uniform(lo, hi)) * fps)))
            v.append(int(round((base + rng.uniform(lo, hi)) * fps)))
        av_t = np.array(av) / fps
        v_t = np.array(v) / fps
        rel_av = av_t % spec.interval_s
        rel_v = v_t % spec.interval_s
        inside = np.all((rel_av >= lo) & (rel_av <= hi)) and np.all((rel_v >= lo) & (rel_v <= hi))
        sep = np.min(np.abs(av_t[:, None] - v_t[None, :]))
        if inside and sep >= spec.min_separation_s - 1e-9:
            return av, v
    raise RuntimeError("could not satisfy reversal constraints")


def generate(spec: BeepSpeedTrial) -> TrialResult:
    rng = np.random.default_rng(spec.seed)
    fps = spec.fps
    n = int(round(spec.duration_s * fps))
    av_rev, v_rev = _schedule(rng, spec)
    sides = {"left": -1.0, "right": 1.0}
    other = "right" if spec.av_side == "left" else "left"
    role = {spec.av_side: "av", other: "v"}
    speeds = {"av": spec.av_speed_rps, "v": spec.av_speed_rps * spec.v_ratio}
    revs = {"av": av_rev, "v": v_rev}
    dirs0 = {"av": spec.av_start_dir, "v": spec.v_start_dir}
    if spec.start_angles is None:
        a0 = dict(zip(("av", "v"), rng.uniform(0, 2 * np.pi, 2)))
    else:
        a0 = dict(zip(("av", "v"), spec.start_angles))

    res = TrialResult(spec=spec, frames=n, times=np.arange(n) / fps)
    for side, sx in sides.items():
        r = role[side]
        step = 2 * np.pi * speeds[r] / fps
        d = np.full(n, float(dirs0[r]))
        for f in revs[r]:
            d[f:] *= -1.0
        # angle[f] is the position displayed at frame f; the move from f to f+1
        # uses direction d[f], so frame f of a reversal is the turning point.
        ang = a0[r] + np.concatenate([[0.0], np.cumsum(d[:-1] * step)])
        cx = sx * spec.center_offset_x
        res.angle[side] = ang
        res.xy[side] = np.stack([cx + spec.radius * np.cos(ang), spec.center_y + spec.radius * np.sin(ang)], 1)
        res.reversal_frames[side] = list(revs[r])
    if spec.beeps:
        res.beep_times = [f / fps for f in av_rev]
    return res


def verify(res: TrialResult) -> dict:
    """Independent checks of a generated trial (raises on failure)."""
    s = res.spec
    out = {}
    for side in ("left", "right"):
        role = "av" if side == s.av_side else "v"
        speed = s.av_speed_rps * (1.0 if role == "av" else s.v_ratio)
        da = np.diff(res.angle[side])
        mag = np.abs(da) * s.fps / (2 * np.pi)
        assert np.allclose(mag, speed, rtol=1e-9), f"{side}: speed not constant"
        flips = (np.where(np.sign(da[1:]) != np.sign(da[:-1]))[0] + 1).tolist()
        assert flips == res.reversal_frames[side], f"{side}: reversal mismatch {flips}"
        out[f"{side}_{role}_speed_rps"] = float(np.mean(mag))
        out[f"{side}_reversal_times_s"] = [round(f / s.fps, 4) for f in flips]
    av_t = np.array(res.reversal_frames[s.av_side]) / s.fps
    other = "right" if s.av_side == "left" else "left"
    v_t = np.array(res.reversal_frames[other]) / s.fps
    out["min_av_v_separation_s"] = float(np.min(np.abs(av_t[:, None] - v_t[None, :])))
    assert out["min_av_v_separation_s"] >= s.min_separation_s - 1e-9
    if s.beeps:
        assert np.allclose(res.beep_times, av_t), "beeps not on AV reversals"
    else:
        assert not res.beep_times
    out["beep_times_s"] = [round(t, 4) for t in res.beep_times]
    return out


def control_of(spec: BeepSpeedTrial) -> BeepSpeedTrial:
    """Same seed -> identical physical trajectories, no sound."""
    d = asdict(spec)
    d.update(beeps=False, name=spec.name + "_control")
    return BeepSpeedTrial(**d)


@dataclass
class LinearChase:
    """Single light moving back and forth along a line (narrative use of the
    original linear paradigm of Meyerhoff et al., 2022).  Positions are in
    world metres along the X axis; reversals obey the same 1-per-second rule."""

    duration_s: float = 9.0
    fps: int = 60
    zig_mps: float = 0.45  # vertical zig-zag speed (reverses once per second)
    drift_mps: float = 2.1  # constant forward drift so the pudu has to chase it
    max_excursion_m: float = 0.32
    seed: int = 1
    beeps: bool = True

    def generate(self):
        """Velocity = (drift, +-zig): its magnitude is constant at every frame,
        so only the direction changes at the beeps, never the physical speed."""
        n = int(round(self.duration_s * self.fps))
        seed = self.seed
        while True:
            rng = np.random.default_rng(seed)
            revs = [int(round((k + rng.uniform(0.1, 0.9)) * self.fps)) for k in range(int(self.duration_s))]
            d = np.ones(n)
            for f in revs:
                d[f:] *= -1.0
            zig = np.concatenate([[0.0], np.cumsum(d[:-1] * self.zig_mps / self.fps)])
            zig -= (zig.max() + zig.min()) / 2
            if np.abs(zig).max() <= self.max_excursion_m:
                break
            seed += 1000
        forward = np.arange(n) * self.drift_mps / self.fps
        return {
            "frames": n,
            "seed_used": seed,
            "speed_mps": float(np.hypot(self.drift_mps, self.zig_mps)),
            "forward": forward.round(6).tolist(),
            "zig": zig.round(6).tolist(),
            "reversal_frames": revs,
            "beep_times_s": [f / self.fps for f in revs] if self.beeps else [],
        }


def dump(obj, path):
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=float)


if __name__ == "__main__":
    t = generate(BeepSpeedTrial(seed=3))
    print(json.dumps(verify(t), indent=1))
    c = generate(control_of(t.spec))
    assert np.allclose(c.xy["left"], t.xy["left"]) and np.allclose(c.xy["right"], t.xy["right"])
    print("control trajectories identical:", True)
    print("hz-check", math.isclose(t.spec.beep_hz, 440.0))
