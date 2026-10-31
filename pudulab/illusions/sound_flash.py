"""Sound-induced flash illusion (SIFI), fission configuration B2F1.

Reference paradigm:
    Yang, H., Ding, D., Qin, H., Miao, H., Wang, C., Zang, Y., Chi, L., & Wu, B.
    (2026). Perceptual decision-making in the sound-induced flash illusion: a
    trial-level hierarchical Bayesian integration of EEG and behavior.
    Behavioral and Brain Functions, 22, 48.
    https://doi.org/10.1186/s12993-026-00344-y  (open access, PMC13637232)

Original effect: Shams, Kamitani & Shimojo (2000), Nature 408, 788.

Parameters reported by Yang et al. (Methods, "Design and stimuli"):
    * 60 Hz display; white disks (radius 2 deg) on black, presented
      simultaneously 7 deg left and right of fixation
    * flash duration 17 ms (one 60 Hz frame)
    * beeps: 3.5 kHz pure tone, 17 ms, 75 dB SPL, binaural headphones
    * inter-beep and inter-flash interval 66 ms
    * 6 conditions B0F1 B0F2 B1F1 B1F2 B2F1 B2F2, 400 trials per person
Results (Table 1, n = 25): accuracy B0F1 0.952, B2F1 0.808, i.e. one flash
was reported as two in roughly 19 % of B2F1 trials (vs. ~5 % without sound).

Deviations used for a social-media short (documented in docs/EP04_CIENCIA.md):
    * flash lasts 2 frames at 60 fps (33 ms) instead of 1 so that a platform
      re-encode to 30 fps cannot drop it (it then becomes exactly 1 frame)
    * a single small disk on one side (story: "una luz lateral"), smaller
      and dimmer than the lab disk, over a dimmed scene instead of black
    * flash onset coincides with the first beep onset (the paper says
      "simultaneous" without giving the offset; this follows Shams et al.)
    * 5 presentations in the whole video instead of 400 trials
All times are quantised to the 60 fps frame grid so a flash onset and its
beep share one exact timestamp.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

PAPER = {
    "doi": "10.1186/s12993-026-00344-y",
    "pmcid": "PMC13637232",
    "citation": "Yang H, Ding D, Qin H, Miao H, Wang C, Zang Y, Chi L, Wu B (2026). Perceptual decision-making in "
                "the sound-induced flash illusion: a trial-level hierarchical Bayesian integration of EEG and "
                "behavior. Behav Brain Funct 22:48.",
    "lab": {"refresh_hz": 60, "flash_ms": 17, "flash_radius_deg": 2, "eccentricity_deg": 7,
            "beep_hz": 3500, "beep_ms": 17, "beep_db_spl": 75, "interval_ms": 66, "trials": 400},
    "accuracy": {"B0F1": 0.952, "B0F2": 0.847, "B1F1": 0.963, "B1F2": 0.731, "B2F1": 0.808, "B2F2": 0.962},
}


@dataclass
class SIFITrial:
    name: str
    onset_s: float  # flash onset == first beep onset (snapped to the frame grid)
    beeps: int = 2
    flashes: int = 1
    fps: int = 60
    flash_frames: int = 2
    beep_hz: float = 3500.0
    beep_ms: float = 17.0
    interval_ms: float = 66.0

    def __post_init__(self):
        f = round(self.onset_s * self.fps)
        f += f % 2  # even frame: survives 60 -> 30 fps decimation as one whole frame
        self.onset_frame = int(f)
        self.onset_s = f / self.fps

    @property
    def condition(self):
        return f"B{self.beeps}F{self.flashes}"

    def flash_frames_list(self):
        step = round(self.interval_ms / 1000 * self.fps)  # 66 ms ~ 4 frames, only used for F2
        out = []
        for k in range(self.flashes):
            out += [self.onset_frame + k * step + i for i in range(self.flash_frames)]
        return out

    def beep_times_s(self):
        return [self.onset_s + k * self.interval_ms / 1000 for k in range(self.beeps)]

    def to_json(self):
        d = asdict(self)
        d.update(onset_frame=self.onset_frame, condition=self.condition, flash_frames_list=self.flash_frames_list(),
                 beep_times_s=self.beep_times_s())
        return d


def beep(hz=3500.0, ms=17.0, ramp_ms=2.0, amp=0.3, sr=48000):
    """17 ms tone burst; 2 ms raised-cosine ramps (ours) avoid speaker clicks."""
    n = int(round(ms / 1000 * sr))
    t = np.arange(n) / sr
    env = np.ones(n)
    r = int(round(ramp_ms / 1000 * sr))
    w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r))
    env[:r], env[-r:] = w, w[::-1]
    return amp * np.sin(2 * np.pi * hz * t) * env


def detect_beeps(x, sr=48000, hz=3500.0, ms=17.0, min_amp=0.03):
    """Matched filter on the decoded audio; returns (onset times s, peak
    amplitudes).  A tone burst of amplitude a gives an envelope peak of
    a * E (E = template energy); anything below `min_amp` is ignored.
    Minimum distance 30 ms so two beeps 66 ms apart are resolved."""
    from scipy import signal

    m = x.mean(1).astype(np.float64) if x.ndim == 2 else x.astype(np.float64)
    tmpl = beep(hz, ms, amp=1.0, sr=sr)
    E = (tmpl ** 2).sum()
    env = np.abs(signal.hilbert(signal.fftconvolve(m, tmpl[::-1], mode="full")))
    peaks, _ = signal.find_peaks(env, height=min_amp * E, distance=int(0.03 * sr))
    return (peaks - (len(tmpl) - 1)) / sr, env[peaks] / E


def detect_flashes(roi_lum, thr=0.06, win=31):
    """roi_lum: per-frame mean luminance of the flash region.  An event is a
    run of frames exceeding a running median by `thr` (slow scene changes,
    fades and parallax do not trigger it).  Returns list of (start, length)."""
    from scipy.ndimage import median_filter

    base = median_filter(roi_lum, size=win, mode="nearest")
    on = (roi_lum - base) > thr
    ev, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            ev.append((i, j - i))
            i = j
        else:
            i += 1
    return ev
