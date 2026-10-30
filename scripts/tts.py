"""FF provider-neutral neural TTS backed by upstream engines.

Run: python -m scripts.tts --provider kokoro --text-file story.txt --output voice.wav
No robotic, silent or language-switching fallback is permitted.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

VOICES = {
    "silero": {"en": "en_0", "ru": "xenia"},
    "kokoro": {"en": "af_heart"},
    "piper": {"en": "en_US-lessac-medium", "ru": "ru_RU-irina-medium"},
    "edge": {"en": "en-US-GuyNeural", "ru": "ru-RU-DmitryNeural"},
    "qwen_clone": {"en": "reference", "ru": "reference"},
}
LICENSES = {
    "silero": "CC BY-NC 4.0: noncommercial only unless separately licensed",
    "kokoro": "Apache-2.0",
    "piper": "GPL-3.0 engine; voice/model training data license varies",
    "edge": "Microsoft online speech service terms",
    "qwen_clone": "Apache-2.0 model weights; respect speaker consent",
}


def resolve_voice(provider, language, voice=None):
    if provider not in VOICES:
        raise ValueError("Unknown provider: " + provider)
    if language not in VOICES[provider]:
        raise ValueError(provider + " does not support language " + language)
    return voice or VOICES[provider][language]


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    if not parts or not all(x.strip() for x in parts):
        raise ValueError("Empty narration text")
    return parts


def join_audio(parts, rate):
    import numpy as np
    if not parts:
        raise RuntimeError("TTS returned no audio chunks")
    gap = np.zeros(round(0.16 * rate), dtype=np.float32)
    return np.concatenate(
        [x for i, sound in enumerate(parts) for x in ((gap, sound) if i else (sound,))])


def _silero(text, voice, language):
    import numpy as np
    import torch
    torch.set_num_threads(2)
    model_id = "v3_en" if language == "en" else "v5_ru"
    model, _ = torch.hub.load("snakers4/silero-models", "silero_tts",
                              language=language, speaker=model_id, trust_repo=True)
    model.to(torch.device("cpu"))
    chunks = [np.asarray(model.apply_tts(text=sentence, speaker=voice, sample_rate=24000),
                         dtype=np.float32).reshape(-1)
              for sentence in split_sentences(text)]
    return join_audio(chunks, 24000), 24000, model_id


def _kokoro(text, voice, language):
    import numpy as np
    from kokoro import KPipeline
    if language != "en":
        raise ValueError("Kokoro English model cannot narrate Russian")
    pipeline = KPipeline(lang_code="a")
    chunks = []
    for sentence in split_sentences(text):
        for _, _, audio in pipeline(sentence, voice=voice):
            chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
    return join_audio(chunks, 24000), 24000, "hexgrad/Kokoro-82M"


def _piper(text, voice, language):
    import sys
    import wave
    import soundfile as sf
    from piper import PiperVoice
    cache = Path.home() / ".cache" / "ff" / "piper"
    cache.mkdir(parents=True, exist_ok=True)
    model = cache / (voice + ".onnx")
    if not model.is_file() or not Path(str(model) + ".json").is_file():
        subprocess.run([sys.executable, "-m", "piper.download_voices", voice],
                       cwd=cache, check=True)
    if not model.is_file():
        raise FileNotFoundError(model)
    engine = PiperVoice.load(str(model))
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "piper.wav"
        with wave.open(str(output), "wb") as wav:
            engine.synthesize_wav(text, wav)
        audio, rate = sf.read(str(output), dtype="float32")
    return audio, rate, voice


def _edge(text, voice, language):
    import soundfile as sf
    import edge_tts
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "speech.mp3"
        wav = Path(tmp) / "speech.wav"
        asyncio.run(edge_tts.Communicate(text, voice=voice).save(str(mp3)))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)],
                       check=True)
        audio, rate = sf.read(str(wav), dtype="float32")
    return audio, rate, "edge-tts"


BACKENDS = {"silero": _silero, "kokoro": _kokoro, "piper": _piper, "edge": _edge}


def speech(text, provider, language, voice, target, *,
           reference_audio=None, reference_text=None, voice_conversion=None):
    import numpy as np
    import soundfile as sf
    if provider == "qwen_clone":
        from scripts.voice_clone import qwen_clone
        samples, rate, model_id = qwen_clone(
            text, language, reference_audio, reference_text)
    else:
        samples, rate, model_id = BACKENDS[provider](text, voice, language)
    samples = np.asarray(samples, dtype=np.float32).reshape(-1)
    if rate < 16000 or samples.size < int(rate):
        raise RuntimeError("Audio unexpectedly short")
    if not np.isfinite(samples).all() or np.max(np.abs(samples)) < .001:
        raise RuntimeError("Invalid/silent model output")
    sf.write(str(target), samples, rate, subtype="PCM_16")
    if voice_conversion == "chatterbox":
        from scripts.voice_clone import chatterbox_convert
        target = Path(target)
        converted = target.with_name(target.stem + "_converted.wav")
        try:
            chatterbox_convert(target, reference_audio, converted)
            converted.replace(target)
        finally:
            converted.unlink(missing_ok=True)
    return model_id


def generate(text, output, *, provider, language="en", voice=None, durations=None,
             reference_audio=None, reference_text=None, voice_conversion=None):
    from scripts.voice import compose_timeline, media_duration, script_hash
    provider = provider.lower()
    selected = resolve_voice(provider, language, voice)
    if voice_conversion not in (None, "chatterbox"):
        raise ValueError("Unsupported voice conversion: " + str(voice_conversion))
    if provider == "qwen_clone" or voice_conversion:
        from scripts.voice_clone import validate_reference
        validate_reference(
            reference_audio, transcript=reference_text,
            require_transcript=(provider == "qwen_clone"))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ff_tts_") as directory:
        tmp = Path(directory)
        if durations is None:
            raw = tmp / "raw.wav"
            model_id = speech(
                text, provider, language, selected, raw,
                reference_audio=reference_audio, reference_text=reference_text,
                voice_conversion=voice_conversion)
            transcript = text.strip()
        else:
            if len(durations) != len(text):
                raise ValueError("durations and text must match")
            fragments = []
            for i, utterance in enumerate(text):
                target = tmp / f"segment_{i}.wav"
                speech(
                    utterance, provider, language, selected, target,
                    reference_audio=reference_audio, reference_text=reference_text,
                    voice_conversion=voice_conversion)
                fragments.append(target)
            raw = tmp / "aligned.wav"
            compose_timeline(fragments, durations, raw)
            transcript = "\n".join(t.strip() for t in text)
            model_id = selected
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=9",
                        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(output)],
                       check=True)
    duration = media_duration(output)
    if duration < 8:
        raise RuntimeError(f"Narration unexpectedly short: {duration:.1f}s")
    metadata = {
        "engine": provider, "model": model_id, "neural": True,
        "voice": selected, "language": language,
        "license_note": LICENSES[provider],
        "voice_conversion": voice_conversion,
        "cloned_from_reference": provider == "qwen_clone" or bool(voice_conversion),
        "duration": round(duration, 3),
        "text_sha256": hashlib.sha256(transcript.encode("utf8")).hexdigest(),
        "audio_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "status": "generated_not_auditioned",
    }
    if durations is not None:
        metadata["scene_count"] = len(text)
        metadata["script_sha256"] = script_hash([{"narration": s} for s in text])
    output.with_suffix(".voice.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf8")
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--text-file", type=Path)
    source.add_argument("--manifest", type=Path)
    p.add_argument("--provider", choices=tuple(VOICES))
    p.add_argument("--language", choices=("en", "ru"))
    p.add_argument("--voice")
    p.add_argument("--voice-conversion", choices=("chatterbox",))
    p.add_argument("--reference-audio", type=Path)
    p.add_argument("--reference-text-file", type=Path,
                   help="Exact transcript of the reference clip, required for Qwen")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    reference_audio = args.reference_audio or os.environ.get("FF_VOICE_REFERENCE")
    reference_text = (args.reference_text_file.read_text(encoding="utf8")
                      if args.reference_text_file
                      else os.environ.get("FF_VOICE_REFERENCE_TEXT"))
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf8"))
        cfg = manifest.get("tts", {})
        provider = args.provider or cfg.get("provider", "edge")
        voice = args.voice or cfg.get("voice")
        voice_conversion = args.voice_conversion or cfg.get("voice_conversion")
        language = args.language or manifest.get("language", "ru")
        lines = [scene["narration"] for scene in manifest["scenes"]]
        duration = [float(scene["duration"]) for scene in manifest["scenes"]]
        result = generate(lines, args.output, provider=provider, language=language,
                          voice=voice, durations=duration,
                          reference_audio=reference_audio, reference_text=reference_text,
                          voice_conversion=voice_conversion)
    else:
        if not args.provider:
            p.error("--provider required when using --text-file")
        result = generate(args.text_file.read_text(encoding="utf8"), args.output,
                          provider=args.provider, language=args.language or "en",
                          voice=args.voice, reference_audio=reference_audio,
                          reference_text=reference_text,
                          voice_conversion=args.voice_conversion)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
