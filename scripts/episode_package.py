"""Safe transfer of an episode from a chat client into an FF Actions runner.

Producer stages a base64-encoded ZIP as a text file on a temporary branch.
Package contains manifest.json and assets/<filename>.png/jpeg/webp only.
No personal audio, voice transcript, biometric reference or API keys belong here.
"""
import base64
import binascii
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from PIL import Image

MAX_ZIP_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED = 80 * 1024 * 1024
MAX_ENTRIES = 32
ASSET_EXTENSIONS = {".png", ".jpeg", ".jpg", ".webp"}


def unpack(bundle, destination):
    bundle = Path(bundle)
    if bundle.suffix != ".b64" or not bundle.is_file():
        raise ValueError("Expected a staged .zip.b64 text package")
    if bundle.stat().st_size > MAX_ZIP_BYTES * 1.4:
        raise ValueError("Staged package exceeds size limit")
    try:
        raw = base64.b64decode(bundle.read_bytes(), validate=False)
    except (ValueError, binascii.Error) as e:
        raise ValueError("Invalid base64 episode package") from e
    if len(raw) > MAX_ZIP_BYTES:
        raise ValueError("Decoded package exceeds size limit")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries = z.infolist()
        if not entries or len(entries) > MAX_ENTRIES:
            raise ValueError("Invalid number of package files")
        total = 0
        names = set()
        for entry in entries:
            name = entry.filename
            p = PurePosixPath(name)
            if (entry.is_dir() or name in names or "\\" in name
                    or name.startswith("/") or any(part in (".", "..") for part in p.parts)
                    or len(p.parts) not in (1, 2)):
                raise ValueError(f"Unsafe or duplicate archive path: {name}")
            allowed = name == "manifest.json" or (
                len(p.parts) == 2 and p.parts[0] == "assets"
                and p.suffix.lower() in ASSET_EXTENSIONS
                and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", p.name))
            if not allowed or ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError(f"Unexpected packaged file: {name}")
            total += entry.file_size
            if total > MAX_UNCOMPRESSED:
                raise ValueError("Episode package expands beyond size limit")
            names.add(name)
        if "manifest.json" not in names:
            raise ValueError("Missing manifest.json")
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            path = root / entry.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(entry))
    verify_assets(root)
    return root


def verify_assets(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf8"))
    scenes = manifest.get("scenes", [])
    refs = set()
    for i, scene in enumerate(scenes):
        image = scene.get("image")
        intent = scene.get("visual_asset")
        if not image or image != intent or not re.fullmatch(
                r"[A-Za-z0-9_.-]{1,100}\.(png|jpg|jpeg|webp)", image):
            raise ValueError(f"Scene {i}: image and visual_asset must match a safe asset filename")
        path = root / "assets" / image
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Scene {i}: missing or unsafe visual asset")
        with Image.open(path) as im:
            im.verify()
        refs.add(image)
    if len(refs) < 3:
        raise ValueError("Production requires three genuinely distinct asset files")
    return manifest
