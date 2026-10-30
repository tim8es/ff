"""CPU voice-timbre conversion with upstream Resemble ChatterboxVC.

This is an optional post-processing stage, NOT a Kokoro cloning feature.
The voice reference remains a local private input; no reference bytes are
included in the output receipt or public-repository artifacts.
"""
from pathlib import Path


def validate_reference(reference):
    from scripts.voice import media_duration
    if reference is None:
        raise ValueError("Voice conversion requires private --reference audio")
    path = Path(reference).expanduser()
    if not path.is_file() or path.is_symlink():
        raise ValueError("Reference must be a regular existing local audio file")
    if path.suffix.lower() not in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
        raise ValueError("Unsupported reference audio format")
    if path.stat().st_size > 30_000_000:
        raise ValueError("Reference audio exceeds 30 MB")
    duration = media_duration(path)
    if not 3 <= duration <= 30:
        raise ValueError("Reference must contain 3–30 seconds of clean speech")
    return path


class ChatterboxVoiceConverter:
    """Reuse one model and target voice embedding across all FF scenes."""

    def __init__(self, reference):
        self.reference = validate_reference(reference)
        import torch
        from chatterbox.vc import ChatterboxVC
        torch.set_num_threads(2)
        self.model = ChatterboxVC.from_pretrained(device="cpu")
        self.model.set_target_voice(str(self.reference))

    def convert(self, source, output):
        import numpy as np
        import soundfile as sf
        speech = self.model.generate(audio=str(source))
        samples = np.asarray(speech.detach().cpu().numpy(),
                             dtype=np.float32).reshape(-1)
        if samples.size < 16000 or not np.isfinite(samples).all():
            raise RuntimeError("Voice converter returned invalid/empty audio")
        sf.write(str(output), samples, self.model.sr, subtype="PCM_16")
        return output
