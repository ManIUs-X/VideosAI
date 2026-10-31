"""Fast checks that run without Blender:  python -m pytest -q tests  (or python tests/test_pipeline.py)."""

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "blender"))

from pudulab import audio as A  # noqa: E402
from pudulab import lights as L  # noqa: E402
from pudulab import verify as V  # noqa: E402
from pudulab.illusions import beep_speed as bs  # noqa: E402


def test_trial_constraints_many_seeds():
    for seed in range(200):
        for ratio in bs.PAPER["ratios"] + [1.0]:
            res = bs.generate(bs.BeepSpeedTrial(seed=seed, v_ratio=ratio))
            bs.verify(res)  # raises on any violation
            for side in ("left", "right"):
                assert len(res.reversal_frames[side]) == 3


def test_control_identical_trajectories():
    spec = bs.BeepSpeedTrial(seed=42, v_ratio=1.24)
    a, b = bs.generate(spec), bs.generate(bs.control_of(spec))
    for side in ("left", "right"):
        assert np.array_equal(a.xy[side], b.xy[side])
    assert a.beep_times and not b.beep_times


def test_chase_constant_speed():
    ch = bs.LinearChase().generate()
    f, z = np.array(ch["forward"]), np.array(ch["zig"])
    sp = np.hypot(np.diff(f), np.diff(z)) * 60
    assert np.allclose(sp, ch["speed_mps"])


def test_beep_spec_and_detector():
    b = A.beep()
    assert len(b) == int(round(0.068 * A.SR))
    k = np.argmax(np.abs(np.fft.rfft(b)))
    assert abs(k * A.SR / len(b) - 440) < 15
    tr = A.Track(3.0)
    times = [0.4567, 1.3011, 2.5]
    for t in times:
        tr.add(b, t)
    tr.buf += 0.01 * np.random.default_rng(0).standard_normal(tr.buf.shape)
    got = V.beep_onsets(tr.buf.astype(np.float32))
    assert len(got) == 3 and np.max(np.abs(got - times)) < 0.002


def test_plan_and_light_states():
    from episodes.ep01_beep_speed import episode as ep

    plan = ep.build_plan()
    assert plan["duration"] <= 60
    for tr in plan["trials"]:
        n = tr["frames"]
        f0 = int(round(tr["start"] * 60))
        for k in (0, n // 2, n - 1):
            st = L.stimulus_state(plan, f0 + k)
            assert all(s["active"] and s["intensity"] == 1.0 for s in st)
        # luminance never varies inside a trial
        assert {s["intensity"] for k in range(n) for s in L.stimulus_state(plan, f0 + k)} == {1.0}
    assert L.stimulus_state(plan, int(5 * 60)) == []  # no stimulus during the chase


def test_animation_deterministic():
    import anim
    from episodes.ep01_beep_speed import episode as ep

    plan = ep.build_plan()
    fn = lambda n, t: (12.0, 3.0, 1.0)  # noqa: E731
    a, b = anim.compute(plan, fn), anim.compute(plan, fn)
    assert a[1234] == b[1234]


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
