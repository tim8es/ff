"""CPU-only voice cloning integration smoke with a SYNTHETIC Piper reference.

NEVER use this file or its artifact upload for a real person's private voice.
"""
import argparse
import json
from pathlib import Path

from scripts.tts import generate


def read(path):
    return (Path("examples") / path).read_text(encoding="utf8").strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("qwen", "conversion"), required=True)
    p.add_argument("--output-dir", type=Path, default=Path("out"))
    args = p.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    reference_text = read("clone_reference_script.txt")
    reference = out / "synthetic_reference.wav"
    generate(reference_text, reference, provider="piper", language="en")

    en = read("clone_english.txt")
    ru = read("clone_russian.txt")
    results = {}
    if args.mode == "qwen":
        for lang, text in (("en", en), ("ru", ru)):
            dest = out / f"qwen_clone_{lang}.wav"
            results[lang] = generate(
                text, dest, provider="qwen_clone", language=lang,
                reference_audio=reference, reference_text=reference_text)
    else:
        for lang, text, provider in (("en", en, "kokoro"), ("ru", ru, "piper")):
            dest = out / f"{provider}_chatterbox_{lang}.wav"
            results[lang] = generate(
                text, dest, provider=provider, language=lang,
                reference_audio=reference, voice_conversion="chatterbox")
    report = {
        "mode": args.mode,
        "test_voice": "synthetic Piper reference only; NOT a cloned human voice",
        "results": results,
    }
    (out / "smoke_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps({
        "mode": args.mode,
        "test_voice": report["test_voice"],
        "results": {k: {"duration": v["duration"], "engine": v["engine"],
                        "voice_conversion": v["voice_conversion"]} for k,v in results.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
