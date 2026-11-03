"""Fan-aware noise suppression for an authorized private speech reference.

All processing is local. No model download, key, or identity data is stored.
Prefer mild processing for Qwen speaker conditioning; strong gating is for auditions.
"""
import numpy as np
from scipy import ndimage, signal


def _quiet_reference(x, sr):
    """Select low-energy 220ms windows to learn stationary background noise."""
    step = max(1, round(.22 * sr))
    count = len(x) // step
    if count < 8:
        raise ValueError("Need at least two seconds of speech to estimate fan noise")
    chunks = x[:count * step].reshape(count, step)
    rms = np.sqrt(np.mean(chunks * chunks, axis=1) + 1e-14)
    # Use the lower-energy quartile; keep enough windows for a reliable noise print.
    order = np.argsort(rms)
    selected = order[:max(4, int(np.ceil(count * .14)))]
    return chunks[selected].ravel()


def fan_reduce(audio, sr, *, noise_audio=None, strength=.75,
               notch_hz=None, strong=False):
    """High-pass -> optional narrow fan-tone notch -> smoothed noise print.

    `strength` is the stationary noise suppression 0..1; optional soft gate
    only attenuates the quietest frames, with limited attenuation and smoothing.
    The PCM signal length, pitch and phoneme timing are preserved.
    """
    try:
        import noisereduce as nr
    except ImportError as e:
        raise RuntimeError("For fan cleaning: pip install noisereduce>=3,<4") from e
    if not (0 <= strength <= 1):
        raise ValueError("strength must be between zero and one")
    if sr < 16000 or sr > 96000:
        raise ValueError("Expected voice sample rate 16..96 kHz")
    if notch_hz is not None and not (400 <= float(notch_hz) <= min(3500, sr * .4)):
        raise ValueError("Fan tone must be between 400 and 3500 Hz")
    y = np.asarray(audio, dtype=np.float64).reshape(-1)
    if len(y) < sr * 3 or not np.all(np.isfinite(y)):
        raise ValueError("Need at least three seconds of finite speech")
    noise = (_quiet_reference(y, sr) if noise_audio is None else
             np.asarray(noise_audio, dtype=np.float64).reshape(-1))
    if len(noise) < sr * .30:
        raise ValueError("Room tone sample too short; provide at least 0.3 s")
    sos = signal.butter(3, 75, fs=sr, btype="highpass", output="sos")
    y = signal.sosfiltfilt(sos, y)
    noise = signal.sosfiltfilt(sos, noise)
    if notch_hz:
        b, a = signal.iirnotch(float(notch_hz), 45, fs=sr)
        y, noise = signal.filtfilt(b, a, y), signal.filtfilt(b, a, noise)
    y = nr.reduce_noise(
        y=y, sr=sr, y_noise=noise, stationary=True,
        prop_decrease=strength, n_std_thresh_stationary=1.30,
        freq_mask_smooth_hz=120, time_mask_smooth_ms=120,
        n_fft=2048, win_length=2048, hop_length=512,
    )
    if strong:
        # A limited expander, not a hard noise gate. Slow transitions keep
        # plosives, vowels and breaths from being abruptly truncated.
        power = ndimage.uniform_filter1d(y * y, size=max(1, round(sr * .03)))
        level = 20 * np.log10(np.sqrt(np.maximum(power, 0)) + 1e-8)
        quiet_db = float(np.percentile(level, 12))
        g = np.clip((level - quiet_db - 3) / 9, 0, 1)
        g = g * g * (3 - 2 * g)
        g = ndimage.gaussian_filter1d(.25 + .75 * g, max(1, round(sr * .065)))
        y *= g
    # Keep output close to -25 dBFS RMS without over-amplifying the noise.
    rms = float(np.sqrt(np.mean(y * y)) + 1e-12)
    factor = min(10 ** (-25 / 20) / rms, 4.0, .70 / (np.max(abs(y)) + 1e-12))
    y *= factor
    return y.astype(np.float32)