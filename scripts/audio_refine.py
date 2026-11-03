"""Conservative iPhone voice-reference preparation for FF Qwen3 cloning.

No cloud requests. Preserve speech timbre: high-pass, moderate spectral noise
attenuation, level correction; NEVER try to "improve" voice via pitch shifting,
auto-tune, or aggressive gating. Reference transcript must match the selected
recording exactly. The report contains no transcription or personal file path.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

RATE = 24000


def _rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2) + 1e-14))


def decode(source, start, duration):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror",
               "-i", str(source), "-ss", str(start), "-t", str(duration),
               "-ac", "1", "-ar", str(RATE), "-f", "f32le", "pipe:1"]
    out = subprocess.run(command, check=True, capture_output=True).stdout
    audio = np.frombuffer(out, dtype="<f4").copy()
    if len(audio) < RATE * 3:
        raise ValueError("Voice reference must contain at least three seconds")
    return audio


def denoise_reference(audio, rate=RATE, *, reduction=0.5):
    """Return conservative speech-preserving denoising and diagnostics.

    Estimate noise from the quietest 40-ms windows. Dynamic noise reduction
    remains deliberately limited to avoid metallic voice or removed fricatives.
    """
    if not 0 <= reduction <= 0.75:
        raise ValueError("reduction must lie in [0, 0.75]")
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not np.isfinite(x).all() or len(x) < 3 * rate:
        raise ValueError("Invalid or too-short voice recording")
    x = x - float(np.mean(x))
    x = sosfiltfilt(butter(2, 75, fs=rate, btype="highpass", output="sos"), x).astype(np.float32)
    # Choose short quiet windows as an approximate noise-only profile. A frame
    # containing speech may still be selected, hence intentionally light gain.
    win = max(1, int(rate * 0.04))
    n = (len(x) // win) * win
    frames = x[:n].reshape(-1, win)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-14)
    floor = np.percentile(rms, 12)
    candidates = frames[rms <= max(floor * 1.3, np.percentile(rms, 20))]
    noise = candidates.reshape(-1) if len(candidates) >= 3 else None
    if noise is not None and len(noise) >= rate // 10 and reduction > 0:
        import noisereduce as nr
        cleaned = nr.reduce_noise(y=x, sr=rate, y_noise=noise,
                                  stationary=True, prop_decrease=reduction,
                                  freq_mask_smooth_hz=300,
                                  time_mask_smooth_ms=80).astype(np.float32)
    else:
        cleaned = x
    # Reference level: conversational speech, no hard compression. Peak limits
    # protect Qwen's conditioning from clipping and preserve microdynamics.
    before = _rms(x)
    desired = 10 ** (-21 / 20)
    gain = np.clip(desired / max(_rms(cleaned), 1e-7), 0.5, 8.0)
    peak = float(np.max(np.abs(cleaned)))
    gain = min(float(gain), .70 / max(peak, 1e-5))
    cleaned = (cleaned * gain).astype(np.float32)
    fade = min(int(rate * .035), len(cleaned) // 6)
    if fade:
        cleaned[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        cleaned[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    info = {
        "sample_rate": rate,
        "duration_s": round(len(x) / rate, 3),
        "noise_reduction_fraction": reduction,
        "estimated_noise_floor_dbfs": round(20 * np.log10(max(floor, 1e-8)), 1),
        "input_rms_dbfs": round(20 * np.log10(max(before, 1e-8)), 1),
        "output_rms_dbfs": round(20 * np.log10(max(_rms(cleaned), 1e-8)), 1),
        "output_peak_dbfs": round(20 * np.log10(max(float(np.max(np.abs(cleaned))), 1e-8)), 1),
        "over_limit_samples": int(np.sum(np.abs(cleaned) >= 0.999)),
    }
    return cleaned, info


def prepare(source, output, *, start=0.0, duration=25.0, reduction=0.5, report=None):
    """Prepare exactly the requested time range; never auto-rewrite transcript."""
    if start < 0 or not 3 <= duration <= 30:
        raise ValueError("Choose a reference range between 3 and 30 seconds")
    wav = decode(source, start, duration)
    prepared, info = denoise_reference(wav, reduction=reduction)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, prepared, RATE, subtype="PCM_16")
    info["audio_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    if report:
        Path(report).write_text(json.dumps(info, indent=2), encoding="utf8")
    return info


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--duration", type=float, default=25)
    p.add_argument("--reduction", type=float, default=0.5)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    print(json.dumps(prepare(args.input, args.output,
                             start=args.start, duration=args.duration,
                             reduction=args.reduction, report=args.report), indent=2))


if __name__ == "__main__":
    main()