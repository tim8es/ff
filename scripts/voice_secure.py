"""Encrypt personal voice inputs and cloned outputs for FF public Actions.

The public repository stores ONLY Fernet authenticated ciphertext. The key must
be stored separately in the FF_VOICE_BUNDLE_KEY GitHub Actions secret.
"""
import argparse
import io
import os
import zipfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

REFERENCE = ("reference.wav", "reference.txt")
MAX_BUNDLE_BYTES = 20_000_000


def _key():
    value = os.environ.get("FF_VOICE_BUNDLE_KEY", "").strip().encode("ascii")
    if not value:
        raise RuntimeError("FF_VOICE_BUNDLE_KEY secret is required")
    try:
        Fernet(value)
    except (ValueError, TypeError) as e:
        raise ValueError("Invalid FF_VOICE_BUNDLE_KEY; expected Fernet key") from e
    return value


def _pack(entries):
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in entries.items():
            if Path(name).name != name or name in ("", ".", ".."):
                raise ValueError("Unsafe bundle entry name")
            z.writestr(name, content)
    return mem.getvalue()


def _decrypt(src, expected, directory):
    data = Path(src).read_bytes()
    if len(data) > MAX_BUNDLE_BYTES:
        raise ValueError("Encrypted bundle too large")
    try:
        plaintext = Fernet(_key()).decrypt(data)
    except InvalidToken as e:
        raise ValueError("Wrong key or altered encrypted bundle") from e
    with zipfile.ZipFile(io.BytesIO(plaintext)) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or not set(names).issubset(expected):
            raise ValueError("Unexpected entries in encrypted bundle")
        if not expected.issubset(names):
            raise ValueError("Required files missing in encrypted bundle")
        for item in z.infolist():
            if item.file_size > MAX_BUNDLE_BYTES:
                raise ValueError("File too large")
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            (target / name).write_bytes(z.read(name))


def pack(reference, transcript, destination):
    ref = Path(reference)
    transcript_text = Path(transcript).read_text(encoding="utf8").strip()
    if not ref.is_file() or not transcript_text:
        raise ValueError("Voice reference and exact transcript required")
    from scripts.tts_qwen import validate_reference
    validate_reference(ref, transcript_text)
    package = _pack({"reference.wav": ref.read_bytes(),
                     "reference.txt": transcript_text.encode("utf8")})
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(Fernet(_key()).encrypt(package))
    return output


def pack_results(src, dest):
    paths = sorted(p for p in Path(src).iterdir() if
                   p.suffix == ".wav" or p.name.endswith(".voice.json"))
    if len(paths) < 2:
        raise ValueError("Missing cloned speech WAVs")
    payload = _pack({p.name: p.read_bytes() for p in paths})
    output = Path(dest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(Fernet(_key()).encrypt(payload))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["pack-reference", "unpack-reference",
                                      "pack-results", "unpack-results"])
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--dest", type=Path, required=True)
    p.add_argument("--transcript", type=Path)
    args = p.parse_args()
    if args.action == "pack-reference":
        if args.transcript is None:
            p.error("--transcript is required to pack a reference")
        pack(args.source, args.transcript, args.dest)
    elif args.action == "unpack-reference":
        _decrypt(args.source, set(REFERENCE), args.dest)
    elif args.action == "pack-results":
        pack_results(args.source, args.dest)
    else:
        expected = {"qwen_ru.wav", "qwen_en.wav",
                    "qwen_ru.voice.json", "qwen_en.voice.json"}
        _decrypt(args.source, expected, args.dest)
    print("Encrypted voice bundle operation completed")


if __name__ == "__main__":
    main()
