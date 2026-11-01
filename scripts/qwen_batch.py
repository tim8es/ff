"""Generate Russian and English Qwen3 speech with ONE model load.

This is the CPU Actions entry point; individual episode rendering still uses
scripts.tts. Sensitive references are passed by local path, never logged.
"""
import argparse
import json
from pathlib import Path

from scripts.tts import generate
from scripts.tts_qwen import Qwen3VoiceCloner, SUPPORTED_MODEL_SIZES


def run_batch(*, model_size, reference, reference_text_file, ru, en, output_dir):
    reference = Path(reference)
    transcript = Path(reference_text_file).read_text(encoding="utf-8").strip()
    # Both languages must be provided; fail before a large model download.
    stories = {
        "ru": Path(ru).read_text(encoding="utf-8").strip(),
        "en": Path(en).read_text(encoding="utf-8").strip(),
    }
    if not all(stories.values()):
        raise ValueError("Both RU and EN texts must be non-empty")
    if model_size not in SUPPORTED_MODEL_SIZES:
        raise ValueError("Unsupported Qwen3 model size")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cloner = Qwen3VoiceCloner(reference, transcript, model_size=model_size)
    results = {}
    for language, text in stories.items():
        path = output_dir / f"qwen_{language}.wav"
        results[language] = generate(
            text, path, provider="qwen3_clone", language=language,
            reference=reference, reference_text=transcript, model_size=model_size,
            _cloner=cloner,
        )
    # No speaker transcript, recording path or embedding in this report.
    print(json.dumps({
        "model": cloner.model_id,
        "outputs": {lang: {"language": lang, "duration": item["duration"]}
                    for lang, item in results.items()},
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-size", choices=tuple(SUPPORTED_MODEL_SIZES), required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-text-file", type=Path, required=True)
    parser.add_argument("--ru", type=Path, required=True)
    parser.add_argument("--en", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run_batch(model_size=args.model_size, reference=args.reference,
              reference_text_file=args.reference_text_file,
              ru=args.ru, en=args.en, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
