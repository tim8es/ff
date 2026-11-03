"""Content-aligned FF narration pacing, with no fixed empty scene tails.

Trim ONLY silence before/after each synthetic utterance, never inside words.
Scene timing derives from synthesized audio instead of arbitrary fixed holds.
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

RATE = 48000


def trim_outer_silence(audio, rate, *, preserve_ms=65, gate_ratio=0.075):
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not np.isfinite(samples).all() or len(samples) < int(.35 * rate):
        raise ValueError("Narration clip is invalid or shorter than 350 ms")
    win = max(1, int(rate * .025))
    hop = max(1, int(rate * .01))
    amps = []
    for start in range(0, max(1, len(samples) - win + 1), hop):
        part = samples[start:start + win]
        amps.append(float(np.sqrt(np.mean(part * part) + 1e-12)))
    if not amps:
        return samples, {"trim_lead_s": 0, "trim_tail_s": 0}
    peak_voice = float(np.percentile(amps, 90))
    threshold = max(0.0018, peak_voice * gate_ratio)
    active = np.flatnonzero(np.asarray(amps) > threshold)
    if not len(active):
        raise ValueError("No speech-like signal detected in narration clip")
    margin = round(preserve_ms / 1000 * rate)
    left = max(0, int(active[0] * hop) - margin)
    right = min(len(samples), int(active[-1] * hop + win) + margin)
    if right - left < int(rate * .30):
        raise ValueError("Clip reduced to less than 300 ms; review speech")
    return samples[left:right].copy(), {
        "trim_lead_s": round(left / rate, 3),
        "trim_tail_s": round((len(samples) - right) / rate, 3),
    }


def compose_tight(parts, output, *, lead_s=.07, gap_s=.14, tail_s=.10,
                  min_scene_s=.65, max_scene_s=9.):
    """Build a gap-controlled soundtrack and return exact scene durations.

    Audio transitions happen at the scene boundaries; no hidden long silence
    from fixed-duration image scenes. The narration itself is never sped up.
    """
    if not parts or any(v < 0 for v in (lead_s, gap_s, tail_s)):
        raise ValueError("Invalid narration clips or pacing parameters")
    segments, timing = [], []
    n = len(parts)
    for index, path in enumerate(parts):
        y, src_rate = sf.read(str(path), dtype="float32")
        if y.ndim == 2:
            y = np.mean(y, axis=1)
        if src_rate != RATE:
            from math import gcd
            d = gcd(src_rate, RATE)
            y = resample_poly(y, RATE // d, src_rate // d).astype(np.float32)
        y, trim = trim_outer_silence(y, RATE)
        fade = min(round(RATE * .012), len(y) // 5)
        if fade:
            y[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            y[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        ahead = lead_s if index == 0 else gap_s
        behind = tail_s if index == n - 1 else 0.
        head = np.zeros(round(ahead * RATE), dtype=np.float32)
        foot = np.zeros(round(behind * RATE), dtype=np.float32)
        segments.append(np.concatenate([head, y, foot]))
        duration = len(segments[-1]) / RATE
        if not min_scene_s <= duration <= max_scene_s:
            raise ValueError(f"Scene {index}: actual speech needs {duration:.2f}s; revise narration")
        timing.append({"scene": index, "duration_s": round(duration, 4),
                       "speech_s": round(len(y) / RATE, 3), **trim})
    mixed = np.concatenate(segments)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output), mixed, RATE, subtype="PCM_16")
    return [entry["duration_s"] for entry in timing], timing