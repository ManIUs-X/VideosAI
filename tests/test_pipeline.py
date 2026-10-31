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


def test_sifi_schedule_and_detectors():
    from pudulab.illusions import sound_flash as SF
    from episodes.ep04_destellos_fantasma import episode as ep4

    for tr in ep4.TRIALS:
        assert tr.onset_frame % 2 == 0 and len(tr.flash_frames_list()) == tr.flash_frames == 2
        assert abs(tr.onset_s - tr.onset_frame / 60) < 1e-12
        bt = tr.beep_times_s()
        assert len(bt) == tr.beeps and (not bt or bt[0] == tr.onset_s)
    on = [t.onset_s for t in ep4.TRIALS]
    assert min(np.diff(on)) >= 3.0 and ep4.DURATION <= 50
    sr = A.SR
    x = np.random.default_rng(1).standard_normal(sr * 2) * 0.02
    b = SF.beep(amp=0.2)
    for t in (0.5, 0.566):
        x[int(round(t * sr)):int(round(t * sr)) + len(b)] += b
    t, _ = SF.detect_beeps(x)
    assert len(t) == 2 and abs(t[1] - t[0] - 0.066) < 1e-3
    lum = np.full(200, 0.1)
    lum[100:102] = 0.9
    assert SF.detect_flashes(lum) == [(100, 2)]
    # nothing but the flash disk changes around a flash (exact, pre-codec)
    R = ep4.Renderer()
    f = ep4.TRIALS[0].onset_frame
    a, c = R.frame(f - 1).astype(int), R.frame(f).astype(int)
    d = np.abs(a - c).max(2)
    y0, y1, x0, x1 = R.flash_box
    assert d[y0:y1, x0:x1].max() > 100
    d[y0:y1, x0:x1] = 0
    assert d.max() == 0


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
