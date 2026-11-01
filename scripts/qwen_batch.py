"""Generate bilingual Qwen3 speech with ONE model and a minimal performance report.

Public profile names contain no private audio. The reference is passed via a
trusted local path or environment, never written to the report or logs.
"""
import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from scripts.tts import generate
from scripts.tts_qwen import Qwen3VoiceCloner, SUPPORTED_MODEL_SIZES
from scripts.voice_profiles import VOICE_PROFILES, resolve_profile


def run_batch(*, model_size=None, profile=None, reference=None,
              reference_text_file=None, ru, en, output_dir):
    started = perf_counter()
    if profile:
        settings = resolve_profile(profile, model_size=model_size)
        model_size = settings["model_size"]
    if model_size not in SUPPORTED_MODEL_SIZES:
        raise ValueError("Choose --profile or a supported --model-size")
    reference = reference or os.environ.get("FF_VOICE_REFERENCE")
    reference_text_file = (reference_text_file or
                           os.environ.get("FF_VOICE_TRANSCRIPT_FILE"))
    if not reference or not reference_text_file:
        raise ValueError("Authorized private voice reference and transcript are required")
    reference = Path(reference)
    transcript = Path(reference_text_file).read_text(encoding="utf-8").strip()
    stories = {
        "ru": Path(ru).read_text(encoding="utf-8").strip(),
        "en": Path(en).read_text(encoding="utf-8").strip(),
    }
    if not all(stories.values()):
        raise ValueError("Both RU and EN texts must be non-empty")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cloner = Qwen3VoiceCloner(reference, transcript, model_size=model_size)
    phases = getattr(cloner, "timings", {}).copy()
    results = {}
    for language, story in stories.items():
        tick = perf_counter()
        path = output_dir / f"qwen_{language}.wav"
        results[language] = generate(
            story, path, provider="qwen3_clone", language=language,
            reference=reference, reference_text=transcript, model_size=model_size,
            _cloner=cloner,
        )
        phases[f"{language}_synthesis_and_audio_write_s"] = round(perf_counter() - tick, 3)

    phases["total_s"] = round(perf_counter() - started, 3)
    # ru_maxrss is KiB on the GitHub-hosted Linux runners.
    try:
        import resource
        phases["peak_process_rss_mib"] = round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except ImportError:
        phases["peak_process_rss_mib"] = None  # resource unavailable on Windows
    summary = {
        "model": cloner.model_id,
        "profile": profile,
        "phases": phases,
        "outputs": {
            lang: {"duration_s": result["duration"],
                   "audio_sha256": result["audio_sha256"]}
            for lang, result in results.items()
        },
    }
    (output_dir / "tts_performance.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    # Contains no sample path, reference text, embeddings or personal data.
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-size", choices=tuple(SUPPORTED_MODEL_SIZES))
    p.add_argument("--profile", choices=tuple(VOICE_PROFILES))
    p.add_argument("--reference", type=Path)
    p.add_argument("--reference-text-file", type=Path)
    p.add_argument("--ru", type=Path, required=True)
    p.add_argument("--en", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    run_batch(model_size=args.model_size, profile=args.profile,
              reference=args.reference,
              reference_text_file=args.reference_text_file,
              ru=args.ru, en=args.en, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
