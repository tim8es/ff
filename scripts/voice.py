"""Generate scene-aligned narration with Edge TTS; refuse silent/robotic fallbacks.

Requires outbound Internet and the unofficial edge-tts consumer endpoint.
It can change or become unavailable; failures intentionally block a release.
"""
import argparse
import asyncio
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

VOICES = {"ru": "ru-RU-DmitryNeural", "en": "en-US-GuyNeural"}


def media_duration(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, capture_output=True, check=True)
    return float(p.stdout.strip())


def script_hash(scenes):
    text = "\n".join(s["narration"].strip() for s in scenes)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_script(manifest):
    scenes = manifest.get("scenes", [])
    if not 1 <= len(scenes) <= 30:
        raise ValueError("Manifest must have 1–30 scenes")
    for i, scene in enumerate(scenes):
        if not scene.get("narration", "").strip():
            raise ValueError(f"scene {i}: missing narration")
        if not 0.3 <= float(scene.get("duration", 0)) <= 30:
            raise ValueError(f"scene {i}: invalid duration")
    return scenes


def compose_timeline(parts, durations, output):
    """Place each spoken clip at the beginning of its scene, with no overlap."""
    if len(parts) != len(durations) or not parts:
        raise ValueError("Audio clips must match scenes")
    total = sum(durations)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filters = []
    pos = 0
    for i, (path, duration) in enumerate(zip(parts, durations)):
        spoken = media_duration(path)
        # 150 ms speech lead-in and 100 ms tail prevent harsh transitions.
        if spoken > duration - 0.25:
            raise ValueError(
                f"Scene {i}: speech {spoken:.2f}s exceeds allotted "
                f"{duration:.2f}s; lengthen the scene or revise the text.")
        cmd += ["-i", str(path)]
        delay = round((pos + 0.15) * 1000)
        filters.append(
            f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,"
            f"adelay={delay}[s{i}]")
        pos += duration
    inputs = "".join(f"[s{i}]" for i in range(len(parts)))
    filters.append(
        f"{inputs}amix=inputs={len(parts)}:duration=longest:dropout_transition=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=9,apad,atrim=0:{total:.3f}[voice]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[voice]",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le",
            str(output)]
    subprocess.run(cmd, check=True)
    if not output.exists() or media_duration(output) < total - 0.1:
        raise RuntimeError("Narration export is incomplete")
    return total


async def synthesize(manifest_path, output, voice=None, rate="+0%"):
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("Install edge-tts: pip install -r scripts/requirements.txt") from exc
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    scenes = verify_script(manifest)
    language = manifest.get("language", "ru")
    if language not in VOICES:
        raise ValueError("Supported languages: ru, en")
    selected = voice or VOICES[language]
    if not selected.lower().startswith(language + "-"):
        raise ValueError(f"Voice {selected!r} does not match {language!r}")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    durations = [float(s["duration"]) for s in scenes]
    with tempfile.TemporaryDirectory(prefix="ff_voice_") as tmp:
        parts = []
        for i, scene in enumerate(scenes):
            part = Path(tmp) / f"{i:02}.mp3"
            try:
                await edge_tts.Communicate(
                    scene["narration"].strip(), voice=selected, rate=rate).save(str(part))
            except Exception as exc:
                raise RuntimeError(
                    f"Edge TTS unavailable for scene {i}; no fallback to eSpeak. "
                    "Retry later or select another approved neural voice.") from exc
            if not part.exists() or part.stat().st_size < 1000:
                raise RuntimeError(f"Scene {i}: empty or invalid TTS file")
            parts.append(part)
        compose_timeline(parts, durations, output)
    receipt = {
        "engine": "edge-tts", "voice": selected, "language": language,
        "script_sha256": script_hash(scenes),
        "scene_count": len(scenes),
        "duration": media_duration(output),
        "audio_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "status": "generated_not_auditioned",
    }
    receipt_path = output.with_suffix(".voice.json")
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--voice", help="Edge voice ID (e.g. ru-RU-DmitryNeural)")
    parser.add_argument("--rate", default="+0%")
    args = parser.parse_args()
    print(asyncio.run(synthesize(args.manifest, args.output, args.voice, args.rate)))


if __name__ == "__main__":
    main()
