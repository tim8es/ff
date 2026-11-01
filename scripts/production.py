"""Produce a review-required vertical MP4 on FF Actions.

Inputs are staged MANIFEST + ORIGINAL IMAGES, never a pre-claimed release.
The CPU runner does TTS, compositing and technical QA. Semantic review is
performed separately after the draft has been inspected and listened to.
"""
import argparse
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from scripts.episode_package import unpack, verify_assets
from scripts.qa import validate
from scripts.render import load_project, render_video
from scripts.tts import generate

OUTPUT_NAMES = (
    "final.mp4", "voice.wav", "voice.voice.json",
    "qa.json", "handoff.json", "manifest.json",
)


def build(*, workspace, bundle=None, demo=False, voice_mode="piper",
          encrypted_reference=None):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    if demo:
        if bundle:
            raise ValueError("Demo cannot use a staged episode package")
        from scripts.production_fixture import make_demo
        make_demo(workspace)
    elif bundle:
        unpack(bundle, workspace)
    else:
        raise ValueError("Supply --bundle or --demo")
    verify_assets(workspace)
    manifest_path = workspace / "manifest.json"
    manifest = load_project(manifest_path)
    narration = [scene["narration"] for scene in manifest["scenes"]]
    durations = [scene["duration"] for scene in manifest["scenes"]]
    language = manifest.get("language")
    audio = workspace / "voice.wav"

    if voice_mode == "owner":
        if not encrypted_reference:
            raise ValueError("Owner mode requires encrypted voice reference bundle")
        from scripts.voice_secure import _decrypt, REFERENCE
        _decrypt(encrypted_reference, set(REFERENCE), workspace / "_private_reference")
        private = workspace / "_private_reference"
        transcript = (private / "reference.txt").read_text(encoding="utf8")
        from scripts.voice_profiles import resolve_profile
        profile = resolve_profile("ff_owner", language=language)
        receipt = generate(
            narration, audio, provider=profile["provider"],
            model_size=profile["model_size"], language=language,
            durations=durations, reference=private / "reference.wav",
            reference_text=transcript)
    elif voice_mode == "piper":
        # Public smoke/draft only: no implicit impersonation of the FF owner.
        receipt = generate(
            narration, audio, provider="piper",
            language=language, durations=durations)
    else:
        raise ValueError("Unknown production voice_mode")

    mp4 = workspace / "final.mp4"
    render_video(manifest, workspace / "assets", mp4, audio=audio)
    qa = validate(manifest_path, mp4, audio, audio.with_suffix(".voice.json"),
                  review=None, technical_only=True)
    (workspace / "qa.json").write_text(json.dumps(qa, indent=2, ensure_ascii=False),
                                       encoding="utf8")
    if not qa["passed"] or qa["release_ready"]:
        raise RuntimeError(f"Production technical QA failed: {qa['errors']}")
    handoff = {
        "status": "TECHNICAL_PREVIEW_REVIEW_REQUIRED",
        "release_ready": False,
        "voice_mode": voice_mode,
        "provider": receipt["engine"],
        "language": language,
        "video_sha256": hashlib.sha256(mp4.read_bytes()).hexdigest(),
        "voice_sha256": receipt["audio_sha256"],
        "duration": qa["duration"],
        "qa_passed_technical": True,
        "required_review": (
            "speech_understandable", "facts_verified", "motion_matches_narration",
            "no_visual_artifacts", "text_inside_safe_areas",
            "hook_is_immediate", "pace_and_ending_work"),
    }
    (workspace / "handoff.json").write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf8")
    return handoff


def seal_private(workspace, output):
    """Seal all derived human voice files AND the MP4 before artifact upload."""
    from cryptography.fernet import Fernet
    from scripts.voice_secure import _key
    root = Path(workspace)
    files = [root / n for n in OUTPUT_NAMES]
    if any(not p.is_file() for p in files):
        raise ValueError("Cannot seal incomplete MP4 production output")
    with io.BytesIO() as mem:
        with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(f, f.name)
        encrypted = Fernet(_key()).encrypt(mem.getvalue())
    Path(output).write_bytes(encrypted)


def unseal_private(bundle, destination):
    """Recover a PRIVATE Actions result only in a trusted chat/local runtime."""
    from cryptography.fernet import Fernet
    from scripts.voice_secure import _key
    raw = Fernet(_key()).decrypt(Path(bundle).read_bytes())
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if set(z.namelist()) != set(OUTPUT_NAMES):
            raise ValueError("Invalid encrypted production artifact structure")
        for entry in z.infolist():
            (dest / entry.filename).write_bytes(z.read(entry))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build")
    build_cmd.add_argument("--workspace", type=Path, required=True)
    group = build_cmd.add_mutually_exclusive_group(required=True)
    group.add_argument("--bundle", type=Path)
    group.add_argument("--demo", action="store_true")
    build_cmd.add_argument("--voice-mode", choices=("piper", "owner"), default="piper")
    build_cmd.add_argument("--encrypted-reference", type=Path)
    seal = commands.add_parser("seal")
    seal.add_argument("--workspace", type=Path, required=True)
    seal.add_argument("--output", type=Path, required=True)
    unseal = commands.add_parser("unseal")
    unseal.add_argument("--bundle", type=Path, required=True)
    unseal.add_argument("--dest", type=Path, required=True)
    args = p.parse_args()
    if args.command == "build":
        print(json.dumps(build(workspace=args.workspace, bundle=args.bundle,
                               demo=args.demo, voice_mode=args.voice_mode,
                               encrypted_reference=args.encrypted_reference),
                         indent=2, ensure_ascii=False))
    elif args.command == "seal":
        seal_private(args.workspace, args.output)
        print("Encrypted owner-voice MP4 production package")
    else:
        unseal_private(args.bundle, args.dest)
        print("Decrypted private FF MP4 to trusted destination")


if __name__ == "__main__":
    main()
