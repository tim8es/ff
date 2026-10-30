"""Nonpersonal ChatterboxVC smoke for the public GitHub runner.

Reference voice is synthesized by Piper at runtime; never use personal voice
files, workflow inputs, secrets or public artifacts for biometric recordings.
"""
import json
from pathlib import Path

from scripts.tts import generate

TARGET = ("When the streetlights go dark, the old library window keeps "
          "glowing. Every morning, the neighbors wonder who stayed awake "
          "through the long and quiet night.")
ENGLISH = ("A single window stayed bright in the village library for forty "
           "years. When workers finally opened the locked room, they found "
           "an old lamp and a note that changed the story.")
RUSSIAN = ("На верхнем этаже старой библиотеки каждую ночь горел одинокий "
           "свет. Люди думали, что там кто-то живёт. Но однажды рабочие "
           "нашли лампу и записку, которая объяснила тайну.")


def main():
    folder = Path("out")
    folder.mkdir(parents=True, exist_ok=True)
    ref = folder / "synthetic_piper_reference.wav"
    generate(TARGET, ref, provider="piper", language="en")
    results = {}
    for provider, lang, text in (
        ("kokoro", "en", ENGLISH),
        ("piper", "ru", RUSSIAN),
    ):
        target = folder / f"{provider}_chatterbox_{lang}.wav"
        results[lang] = generate(
            text, target, provider=provider, language=lang,
            reference=ref, voice_conversion="chatterbox")
    (folder / "test_only_report.json").write_text(
        json.dumps({"reference": "synthetic Piper only; no human voice",
                    "outputs": results}, indent=2, ensure_ascii=False),
        encoding="utf8")
    for lang, receipt in results.items():
        print(f"{lang}: {receipt['engine']} + {receipt['voice_conversion']}, "
              f"{receipt['duration']:.2f}s")


if __name__ == "__main__":
    main()
