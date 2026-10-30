"""Qwen3-TTS zero-shot voice cloning adapter (optional dependency).

Only local reference audio is accepted. Do not upload personal recordings to
public repositories or GitHub Actions artifacts.
"""
from pathlib import Path

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
LANGUAGES = {"ru": "Russian", "en": "English"}


def validate_reference(reference, reference_text):
    from scripts.voice import media_duration
    if not reference:
        raise ValueError("Qwen3 voice cloning requires a local --reference audio file")
    ref = Path(reference).expanduser()
    if not ref.is_file() or ref.is_symlink():
        raise ValueError("Reference must be an existing regular local audio file")
    if ref.suffix.lower() not in (".wav", ".mp3", ".m4a", ".flac", ".ogg"):
        raise ValueError("Unsupported reference format; use WAV, MP3, M4A, FLAC or OGG")
    if not isinstance(reference_text, str) or len(reference_text.strip()) < 5:
        raise ValueError("Accurate --reference-text-file transcript is required")
    duration = media_duration(ref)
    if not 3 <= duration <= 30:
        raise ValueError("Voice reference must be between 3 and 30 seconds")
    if ref.stat().st_size > 30_000_000:
        raise ValueError("Voice reference exceeds 30MB")
    return ref


class Qwen3VoiceCloner:
    """Load Base model once; reuse the same speaker conditioning per scene."""

    def __init__(self, reference, reference_text, *, model=None):
        self.reference = validate_reference(reference, reference_text)
        self.reference_text = reference_text.strip()
        if model is None:
            import torch
            from qwen_tts import Qwen3TTSModel
            torch.set_num_threads(min(4, torch.get_num_threads()))
            # CPU-compatible fallback: no FlashAttention, CUDA, or paid API.
            model = Qwen3TTSModel.from_pretrained(
                MODEL_ID, device_map="cpu", dtype=torch.float32)
        self.model = model
        self.prompt = model.create_voice_clone_prompt(
            ref_audio=str(self.reference),
            ref_text=self.reference_text,
            x_vector_only_mode=False,
        )

    def synthesize(self, text, language):
        import numpy as np
        if language not in LANGUAGES:
            raise ValueError("Unsupported clone language " + str(language))
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Narration text cannot be empty")
        audio, rate = self.model.generate_voice_clone(
            text=text.strip(), language=LANGUAGES[language],
            voice_clone_prompt=self.prompt,
        )
        if not audio:
            raise RuntimeError("Qwen3 produced no speech")
        return np.asarray(audio[0], dtype=np.float32).reshape(-1), rate, MODEL_ID
