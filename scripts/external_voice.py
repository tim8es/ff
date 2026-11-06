"""Verify a trusted PRIVATE Voice Engine recording before FF renders it.

Never import a voice from a public Actions artifact. The caller must obtain
WAV and receipt inside a trusted private environment, after decryption.
"""
import hashlib
import json
import math
import shutil
import wave
from pathlib import Path

from scripts.voice import script_hash

OWNER_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
MAX_VOICE_BYTES = 50_000_000


def accept_owner_voice(manifest, wav, receipt_path, workspace):
    """Validate provenance, exact narration and pacing; copy only after checks."""
    tts = manifest.get("tts", {})
    if tts.get("profile") != "ff_owner" or tts.get("provider") not in (None, "qwen3_clone"):
        raise ValueError("External FF voice must match the ff_owner profile")
    wav, receipt_path, workspace = Path(wav), Path(receipt_path), Path(workspace)
    if (not wav.is_file() or wav.is_symlink() or wav.stat().st_size > MAX_VOICE_BYTES
            or not receipt_path.is_file() or receipt_path.is_symlink()
            or receipt_path.stat().st_size > 100_000):
        raise ValueError("Private voice or receipt is missing/unsafe")
    metadata = json.loads(receipt_path.read_text(encoding="utf8"))
    scenes = manifest["scenes"]
    required = {
        "engine": "qwen3_clone", "model": OWNER_MODEL, "neural": True,
        "voice_cloned": True, "profile": "ff_owner",
        "language": manifest["language"], "scene_count": len(scenes),
        "script_sha256": script_hash(scenes),
    }
    if any(metadata.get(k) != expected for k, expected in required.items()):
        raise ValueError("Private Voice Engine provenance/script mismatch")
    if metadata.get("audio_sha256") != hashlib.sha256(wav.read_bytes()).hexdigest():
        raise ValueError("Private Voice Engine WAV integrity mismatch")
    timing = metadata.get("scene_durations")
    if (not isinstance(timing, list) or len(timing) != len(scenes)
            or any(type(s) not in (int, float) or not math.isfinite(s)
                   or not 0.3 <= s <= 30 for s in timing)
            or not 15 <= sum(timing) <= 25):
        raise ValueError("Private Voice Engine scene timing is invalid")
    with wave.open(str(wav), "rb") as sound:
        if (sound.getnchannels() != 1 or sound.getsampwidth() != 2
                or not 16000 <= sound.getframerate() <= 48000):
            raise ValueError("Private Voice Engine audio must be mono PCM16")
        seconds = sound.getnframes() / sound.getframerate()
    if abs(seconds - sum(timing)) > 0.25:
        raise ValueError("Private Voice Engine audio duration differs from scenes")
    dest = workspace / "voice.wav"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("Refusing to overwrite an existing voice")
    shutil.copyfile(wav, dest)
    dest_receipt = workspace / "voice.voice.json"
    if dest_receipt.exists() or dest_receipt.is_symlink():
        dest.unlink()
        raise FileExistsError("Refusing to overwrite an existing receipt")
    dest_receipt.write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                            encoding="utf8")
    return metadata
