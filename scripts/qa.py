"""Fail-closed release gate for FF videos.

Checks metadata, every decoded frame, audio levels, narration provenance and a
signed semantic review. Automatic pixel checks cannot prove factual accuracy.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from scripts.voice import script_hash, verify_script


REVIEW_KEYS = (
    "speech_understandable", "facts_verified", "motion_matches_narration",
    "no_visual_artifacts", "text_inside_safe_areas", "hook_is_immediate",
    "pace_and_ending_work",
)


def probe(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def inspect_frames(path, fps, width, height):
    """Decode every frame at 64x114. Detect blanks/freezes and decode failures."""
    sw, sh = 64, 114
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-an",
           "-vf", f"scale={sw}:{sh}:flags=fast_bilinear,format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    count = frozen = worst_frozen = dark = 0
    previous = None
    size = sw * sh
    while True:
        block = p.stdout.read(size)
        if not block:
            break
        if len(block) != size:
            raise ValueError(f"Partial decoded frame at index {count}")
        count += 1
        mean = sum(block) / size
        dynamic = max(block) - min(block)
        if mean < 8 or dynamic < 12:
            dark += 1
        if block == previous:
            frozen += 1
            worst_frozen = max(worst_frozen, frozen + 1)
        else:
            frozen = 0
        previous = block
    p.stdout.close()
    err = p.stderr.read().decode("utf8", "replace")
    if p.wait() != 0:
        raise RuntimeError(f"Video decoding failed: {err[-1200:]}")
    if count < round(fps * 10):
        raise ValueError(f"Too few decoded frames: {count}")
    return {
        "decoded_frames": count,
        "blank_frames": dark,
        "longest_identical_run": worst_frozen,
        "expected_frames_approx": round(fps * count / fps),
    }


def audio_levels(path):
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-vn", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    matches = dict(re.findall(
        r"(mean_volume|max_volume):\s*(-?[\d.]+) dB", p.stderr))
    if len(matches) != 2:
        raise ValueError("Cannot measure speech/audio levels")
    return {key: float(value) for key, value in matches.items()}


def validate(manifest_path, video, voice, receipt, review):
    data = json.loads(Path(manifest_path).read_text(encoding="utf8"))
    scenes = verify_script(data)
    total = sum(float(s["duration"]) for s in scenes)
    errors = []
    if not 15 <= total <= 25 or not 5 <= len(scenes) <= 8:
        errors.append("Story must have 5–8 shots over 15–25 seconds")
    hosts = {
        urlparse(u).hostname for u in data.get("sources", [])
        if isinstance(u, str) and urlparse(u).scheme == "https"
    }
    if len(hosts - {None}) < 2:
        errors.append("At least 2 independently hosted evidence URLs required")
    for i, s in enumerate(scenes):
        if not s.get("visual_intent") or not s.get("narration"):
            errors.append(f"Scene {i}: narration/visual_intent missing")
        if not s.get("onscreen_text"):
            errors.append(f"Scene {i}: exact onscreen_text missing")
    if data.get("language") not in ("ru", "en"):
        errors.append("Explicit language: ru or en")
    if receipt and voice:
        if not Path(voice).is_file():
            errors.append("Narration file missing")
        else:
            meta = json.loads(Path(receipt).read_text(encoding="utf8"))
            if meta.get("neural") is not True or meta.get("engine", "").lower() in ("espeak", "espeak-ng"):
                errors.append("Release requires a neural TTS engine")
            if meta.get("language") != data.get("language"):
                errors.append("Narration language differs from manifest")
            if meta.get("script_sha256") != script_hash(scenes):
                errors.append("Narration transcript changed since recording")
            if meta.get("audio_sha256") != hashlib.sha256(
                    Path(voice).read_bytes()).hexdigest():
                errors.append("Narration audio does not match receipt")
    else:
        errors.append("Missing neural voice audio or provenance receipt")
    if review:
        judgments = json.loads(Path(review).read_text(encoding="utf8"))
        missing = [key for key in REVIEW_KEYS if judgments.get(key) is not True]
        if missing:
            errors.append("Unpassed content review: " + ", ".join(missing))
    else:
        errors.append("Semantic and audible review is required")
    metadata = probe(video)
    vs = next((s for s in metadata["streams"]
               if s["codec_type"] == "video"), None)
    a = next((s for s in metadata["streams"]
              if s["codec_type"] == "audio"), None)
    fps = 0
    if vs:
        numerator, denominator = map(int, vs["avg_frame_rate"].split("/"))
        fps = numerator / denominator if denominator else 0
        if vs["codec_name"] != "h264" or vs.get("pix_fmt") != "yuv420p":
            errors.append("Requires H.264 yuv420p")
        if vs["width"] * 16 != vs["height"] * 9 or fps < 23.9:
            errors.append("Requires vertical 9:16 at >=24 fps")
    else:
        errors.append("Video stream missing")
    if not a or a.get("codec_name") != "aac":
        errors.append("Required AAC audio stream missing")
    duration = float(metadata["format"]["duration"])
    if abs(duration - total) > 0.30:
        errors.append(f"Timeline mismatch: video {duration:.2f}s, script {total:.2f}s")
    frames = inspect_frames(video, fps or 24, vs["width"], vs["height"]) if vs else {}
    if frames.get("blank_frames", 0):
        errors.append(f"Blank/black frames: {frames['blank_frames']}")
    if frames.get("longest_identical_run", 0) > fps * 0.9:
        errors.append("Frozen sequence longer than 0.9 seconds")
    levels = audio_levels(video) if a else {}
    if levels:
        if levels["mean_volume"] < -35 or levels["max_volume"] < -19:
            errors.append("Audio too quiet, possibly silence")
        if levels["max_volume"] > -0.3:
            errors.append("Clipping risk in audio")
    return {
        "passed": not errors, "errors": errors,
        "video": str(video), "duration": duration,
        "frames": frames, "audio": levels,
        "review": str(review) if review else None,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", type=Path)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--voice", type=Path)
    p.add_argument("--receipt", type=Path)
    p.add_argument("--review", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    result = validate(args.manifest, args.video, args.voice, args.receipt, args.review)
    formatted = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(formatted, encoding="utf8")
    print(formatted)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
