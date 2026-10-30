"""Optional, on-demand voice identity backends for FF.

No voice samples, prompt embeddings or personal reference bytes are committed.
Both engines run locally on a CPU runner, but may exceed hosted Actions limits.
Do not cache or upload real-person reference files as build artifacts.
"""
from functools import lru_cache
from pathlib import Path


QWEN_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"


def validate_reference(audio, *, transcript=None, require_transcript=False):
    """Validate explicit authorized voice example, fail before model downloads."""
    from scripts.voice import media_duration
    if audio is None:
        raise ValueError("Voice cloning requires --reference-audio or FF_VOICE_REFERENCE")
    path = Path(audio).expanduser()
    if not path.is_file():
        raise FileNotFoundError("Voice reference audio not found")
    seconds = media_duration(path)
    if not 3 <= seconds <= 30:
        raise ValueError("Voice reference must contain 3–30 seconds of clean speech")
    if require_transcript and not (transcript and transcript.strip()):
        raise ValueError("Qwen voice cloning needs the exact reference transcript")
    return path


@lru_cache(maxsize=1)
def qwen_model():
    import torch
    from qwen_tts import Qwen3TTSModel
    torch.set_num_threads(2)
    return Qwen3TTSModel.from_pretrained(
        QWEN_MODEL, device_map="cpu", dtype=torch.float32,
        attn_implementation="sdpa")


def qwen_clone(text, language, reference, reference_text):
    """Qwen3 0.6B Base, true few-shot cloning: English and Russian."""
    import numpy as np
    path = validate_reference(reference, transcript=reference_text,
                              require_transcript=True)
    if language not in ("ru", "en"):
        raise ValueError("Qwen cloning supports ru and en in FF")
    output, rate = qwen_model().generate_voice_clone(
        text=text, language={"ru": "Russian", "en": "English"}[language],
        ref_audio=str(path), ref_text=reference_text.strip())
    if len(output) != 1:
        raise RuntimeError("Qwen returned an unexpected number of clips")
    return np.asarray(output[0], dtype=np.float32).reshape(-1), rate, QWEN_MODEL


@lru_cache(maxsize=1)
def converter_model():
    from chatterbox.vc import ChatterboxVC
    import torch
    torch.set_num_threads(2)
    return ChatterboxVC.from_pretrained(device="cpu")


def chatterbox_convert(source, reference, output):
    """Convert the already synthesized speech timbre via ChatterboxVC."""
    import numpy as np
    import soundfile as sf
    path = validate_reference(reference)
    audio = converter_model().generate(
        audio=str(source), target_voice_path=str(path))
    samples = audio.detach().cpu().numpy()
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if samples.size < 16000 or not np.isfinite(samples).all():
        raise RuntimeError("Voice converter returned invalid audio")
    sf.write(str(output), samples, converter_model().sr, subtype="PCM_16")
    return output
